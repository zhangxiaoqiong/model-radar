"""Load AA/OpenRouter into ODS, conform DWD, and rebuild the ADS snapshot."""
from __future__ import annotations
import hashlib, json, re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from backend_core.db import new_uuid, utcnow
from backend_core.domain import (
    AdsModelWide, DwdModel, DwdModelEvaluation, DwdModelPerformance, DwdModelPrice,
    EtlBatch, OdsAaEvaluation, OdsAaModel, OdsOpenrouterModel,
)

def _hash(row): return hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
def _key(value): return re.sub(r"[^a-z0-9]+","-",str(value).lower()).strip("-")
def _num(value, multiplier=1):
    try:
        if value in (None,""): return None
        n=Decimal(str(value))*multiplier
        return n if n.is_finite() else None
    except (InvalidOperation,ValueError,TypeError): return None
def _day(value):
    try: return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError: return None

def _batch(session, source, interface, count, data_date):
    item=EtlBatch(id=new_uuid(),source_code=source,interface_name=interface,status="running",
                  data_date=data_date,started_at=utcnow(),fetched_count=count)
    session.add(item); session.flush(); return item

def load_aa(session: Session, rows: list[dict], *, data_date: date|None=None) -> EtlBatch:
    day=data_date or date.today(); batch=_batch(session,"artificial_analysis","language/models/free",len(rows),day)
    loaded=rejected=0
    try:
        for row in rows:
            external=str(row.get("id") or row.get("slug") or "").strip()
            name=str(row.get("name") or row.get("slug") or "").strip()
            if not external or not name: rejected+=1; continue
            creator=row.get("model_creator") or {}; creator_name=str(creator.get("name") or "").strip() or None
            ods=OdsAaModel(batch_id=batch.id,aa_model_id=external,model_slug=row.get("slug"),
                model_name=name,creator_name=creator_name,release_date=_day(row.get("release_date")),
                pricing=row.get("pricing"),performance=row.get("performance"),
                evaluations=row.get("evaluations"),raw_payload=row,record_hash=_hash(row),data_date=day)
            session.add(ods); session.flush(); loaded+=1
            evaluations=row.get("evaluations") or {}
            if isinstance(evaluations,dict):
                for metric,value in evaluations.items():
                    score=_num(value)
                    if score is None: continue
                    session.add(OdsAaEvaluation(batch_id=batch.id,aa_model_id=external,
                        model_slug=row.get("slug"),model_name=name,creator_name=creator_name,
                        evaluation_name=str(metric),score=score,
                        raw_payload={"value":value},data_date=day))
        batch.loaded_count=loaded; batch.rejected_count=rejected; batch.status="success"; batch.finished_at=utcnow()
        session.flush(); return batch
    except Exception as exc:
        batch.status="failed"; batch.error_message=f"{type(exc).__name__}: {exc}"; batch.finished_at=utcnow(); raise

def load_openrouter(session: Session, rows: list[dict], *, data_date: date|None=None) -> EtlBatch:
    day=data_date or date.today(); batch=_batch(session,"openrouter","api/v1/models",len(rows),day)
    loaded=rejected=0
    try:
        for row in rows:
            external=str(row.get("id") or "").strip(); name=str(row.get("name") or external).strip()
            if not external: rejected+=1; continue
            architecture=row.get("architecture") or {}; top=row.get("top_provider") or {}
            session.add(OdsOpenrouterModel(batch_id=batch.id,openrouter_model_id=external,
                model_name=name,description=row.get("description"),context_length=row.get("context_length"),
                max_output_tokens=top.get("max_completion_tokens"),architecture=architecture,
                supported_parameters=row.get("supported_parameters"),pricing=row.get("pricing"),
                raw_payload=row,record_hash=_hash(row),data_date=day)); loaded+=1
        batch.loaded_count=loaded; batch.rejected_count=rejected; batch.status="success"; batch.finished_at=utcnow()
        session.flush(); return batch
    except Exception as exc:
        batch.status="failed"; batch.error_message=f"{type(exc).__name__}: {exc}"; batch.finished_at=utcnow(); raise

def build_dwd(session: Session, aa_batch: EtlBatch, or_batch: EtlBatch|None=None) -> int:
    # A batch is immutable. Rebuilding its downstream slice is idempotent.
    model_by_aa={}
    aa_rows=session.scalars(select(OdsAaModel).where(OdsAaModel.batch_id==aa_batch.id)).all()
    for row in aa_rows:
        key=f"{_key(row.creator_name or 'unknown')}:{_key(row.model_slug or row.model_name)}"
        model=session.scalar(select(DwdModel).where(DwdModel.model_key==key))
        if model is None:
            model=DwdModel(model_key=key,model_name=row.model_name,vendor_name=row.creator_name or "Unknown")
            session.add(model); session.flush()
        model.model_name=row.model_name; model.vendor_name=row.creator_name or model.vendor_name
        model.release_date=row.release_date; model.aa_model_id=row.aa_model_id
        model.attribute_sources={"identity":"ods_aa_model","aa_record_id":row.id}
        model_by_aa[row.aa_model_id]=model
    session.flush()

    if or_batch:
        models=session.scalars(select(DwdModel)).all()
        by_name={_key(m.model_name):m for m in models}
        for row in session.scalars(select(OdsOpenrouterModel).where(OdsOpenrouterModel.batch_id==or_batch.id)):
            short_name=row.model_name.split(": ",1)[-1]
            model=by_name.get(_key(short_name))
            if not model: continue
            arch=row.architecture or {}; params=set(row.supported_parameters or [])
            model.openrouter_model_id=row.openrouter_model_id
            model.context_window=row.context_length or model.context_window
            model.max_output_tokens=row.max_output_tokens or model.max_output_tokens
            model.input_modalities=arch.get("input_modalities")
            model.output_modalities=arch.get("output_modalities")
            model.architecture_type=arch.get("modality")
            model.supports_reasoning=bool({"reasoning","reasoning_effort","include_reasoning"}&params)
            model.supports_tool_calling="tools" in params
            model.supports_structured_output=bool({"structured_outputs","response_format"}&params)
            model.attribute_sources={**(model.attribute_sources or {}),"capabilities":"ods_openrouter_model","openrouter_record_id":row.id}
    session.flush()

    eval_rows=session.scalars(select(OdsAaEvaluation).where(OdsAaEvaluation.batch_id==aa_batch.id)).all()
    for row in eval_rows:
        model=model_by_aa.get(row.aa_model_id)
        if model:
            session.add(DwdModelEvaluation(model_id=model.id,evaluation_platform="Artificial Analysis",
                evaluator="Artificial Analysis",benchmark_name=row.evaluation_name,score=row.score,
                source_table="ods_aa_evaluation",source_record_id=row.id,batch_id=aa_batch.id,data_date=row.data_date))
    for row in aa_rows:
        model=model_by_aa[row.aa_model_id]; pricing=row.pricing or {}; perf=row.performance or {}
        ip=_num(pricing.get("price_1m_input_tokens")); op=_num(pricing.get("price_1m_output_tokens")); cp=_num(pricing.get("price_1m_cache_hit_tokens"))
        if any(x is not None for x in (ip,op,cp)):
            session.add(DwdModelPrice(model_id=model.id,service_provider="Artificial Analysis reference",
                input_price=ip,output_price=op,cache_read_price=cp,source_table="ods_aa_model",
                source_record_id=row.id,batch_id=aa_batch.id,data_date=row.data_date))
        speed=_num(perf.get("median_output_tokens_per_second")); ttft=_num(perf.get("median_time_to_first_token_seconds"),1000); latency=_num(perf.get("median_end_to_end_response_time_seconds"),1000)
        if any(x is not None for x in (speed,ttft,latency)):
            session.add(DwdModelPerformance(model_id=model.id,evaluation_platform="Artificial Analysis",
                evaluator="Artificial Analysis",output_tokens_per_second=speed,time_to_first_token_ms=ttft,
                end_to_end_latency_ms=latency,source_table="ods_aa_model",source_record_id=row.id,
                batch_id=aa_batch.id,data_date=row.data_date))
    session.flush(); return len(model_by_aa)

def refresh_ads(session: Session, *, snapshot_date: date|None=None) -> int:
    day=snapshot_date or date.today(); session.execute(delete(AdsModelWide).where(AdsModelWide.snapshot_date==day))
    count=0
    for model in session.scalars(select(DwdModel)):
        evaluations=session.scalars(select(DwdModelEvaluation).where(DwdModelEvaluation.model_id==model.id).order_by(DwdModelEvaluation.data_date.desc())).all()
        scores={}
        for item in evaluations: scores.setdefault(item.benchmark_name,float(item.score))
        price=session.scalar(select(DwdModelPrice).where(DwdModelPrice.model_id==model.id).order_by(DwdModelPrice.data_date.desc()).limit(1))
        perf=session.scalar(select(DwdModelPerformance).where(DwdModelPerformance.model_id==model.id).order_by(DwdModelPerformance.data_date.desc()).limit(1))
        populated=sum(v is not None for v in [model.release_date,model.context_window,model.input_modalities,price,perf,bool(scores)])
        session.add(AdsModelWide(snapshot_date=day,model_id=model.id,model_key=model.model_key,
            model_name=model.model_name,vendor_name=model.vendor_name,vendor_country=model.vendor_country,
            region_group=model.region_group,release_date=model.release_date,openness=model.openness,
            parameter_scale=model.parameter_scale,context_window=model.context_window,
            max_output_tokens=model.max_output_tokens,input_modalities=model.input_modalities,
            output_modalities=model.output_modalities,tags=model.tags,headline_scores=scores,
            selected_service_provider=price.service_provider if price else None,
            input_price=price.input_price if price else None,output_price=price.output_price if price else None,
            cache_read_price=price.cache_read_price if price else None,
            output_tokens_per_second=perf.output_tokens_per_second if perf else None,
            time_to_first_token_ms=perf.time_to_first_token_ms if perf else None,
            source_summary=model.attribute_sources,quality_score=Decimal(populated*100/6)))
        count+=1
    session.flush(); return count
