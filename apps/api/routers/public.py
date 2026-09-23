"""Read-only analytical APIs backed by ADS and DWD."""
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import func,select
from sqlalchemy.orm import Session
from backend_core.domain import AdsModelWide,DwdModel,DwdModelEvaluation,EtlBatch
from ..deps import get_db_session,jsonable
router=APIRouter()

def _latest(session): return session.scalar(select(func.max(AdsModelWide.snapshot_date)))
def _item(row):
    modes=set((row.input_modalities or [])+(row.output_modalities or [])); tags=set(row.tags or [])
    return {"id":row.model_id,"slug":row.model_key,"canonical_name":row.model_name,
      "release_date":row.release_date,"provider":row.vendor_name.lower().replace(" ","-"),"provider_name":row.vendor_name,
      "description":None,"default_variant_id":row.model_id,
      "variant":{"id":row.model_id,"name":"standard","context_window":row.context_window,"max_output_tokens":row.max_output_tokens,
        **{f"supports_{m}":m in modes for m in ("text","image","audio","video")},
        "supports_reasoning":"reasoning" in tags,"supports_tool_calling":"tool_calling" in tags,"supports_structured_output":"structured_output" in tags},
      "endpoint":None,"capability_source":"OpenRouter" if row.input_modalities else None,
      "pricing":{"input_price_per_million":row.input_price,"output_price_per_million":row.output_price,
        "cached_input_price":row.cache_read_price,"currency":"USD","provider_name":row.selected_service_provider,"observed_at":row.refreshed_at}
        if row.input_price is not None or row.output_price is not None else None,
      "performance":{"tokens_per_second":row.output_tokens_per_second,"time_to_first_token_ms":row.time_to_first_token_ms,
        "provider_name":"Artificial Analysis","measured_at":row.refreshed_at} if row.output_tokens_per_second is not None else None,
      "evaluations":[{"benchmark_slug":k,"benchmark_name":k,"score":v,"source":"Artificial Analysis","observed_at":row.refreshed_at}
        for k,v in (row.headline_scores or {}).items()]}

@router.get("/health")
def health(session:Session=Depends(get_db_session)): return {"status":"ok","db":"ok" if session.scalar(select(1))==1 else "error"}

@router.get("/api/v1/status")
def status(session:Session=Depends(get_db_session)):
    batch=session.scalar(select(EtlBatch).order_by(EtlBatch.started_at.desc()).limit(1))
    count=session.scalar(select(func.count()).select_from(DwdModelEvaluation))
    return {"latest_snapshot_time":batch.finished_at if batch else None,
      "latest_pipeline":{"id":batch.id,"type":batch.source_code,"status":batch.status,"finished_at":batch.finished_at} if batch else None,
      "evaluation_count":count,"current_evaluation_count":count,"pending_resolution_count":0}

@router.get("/api/v1/models")
def models(session:Session=Depends(get_db_session),provider:str|None=None,q:str|None=None,cursor:str|None=None,
           limit:int=Query(20,ge=1,le=100),include_summary:bool=False,status:str|None=None):
    day=_latest(session)
    if day is None:return {"items":[],"next_cursor":None}
    stmt=select(AdsModelWide).where(AdsModelWide.snapshot_date==day)
    if provider:stmt=stmt.where(AdsModelWide.vendor_name==provider)
    if q:stmt=stmt.where(AdsModelWide.model_name.like(f"%{q}%"))
    if cursor:stmt=stmt.where(AdsModelWide.id>cursor)
    rows=session.scalars(stmt.order_by(AdsModelWide.id).limit(limit+1)).all(); more=len(rows)>limit; rows=rows[:limit]
    return jsonable({"items":[_item(r) for r in rows],"next_cursor":rows[-1].id if more else None})

@router.get("/api/v1/models/{model_key}")
def model_detail(model_key:str,session:Session=Depends(get_db_session)):
    row=session.scalar(select(AdsModelWide).where(AdsModelWide.snapshot_date==_latest(session),AdsModelWide.model_key==model_key))
    if not row:raise HTTPException(404,f"model '{model_key}' not found")
    return jsonable(_item(row))

@router.get("/api/v1/models/{model_key}/evaluations")
def evaluations(model_key:str,session:Session=Depends(get_db_session),benchmark:str|None=None,limit:int=Query(100,le=500),include_history:bool=False,cursor:str|None=None):
    model=session.scalar(select(DwdModel).where(DwdModel.model_key==model_key))
    if not model:raise HTTPException(404,f"model '{model_key}' not found")
    stmt=select(DwdModelEvaluation).where(DwdModelEvaluation.model_id==model.id)
    if benchmark:stmt=stmt.where(DwdModelEvaluation.benchmark_name==benchmark)
    rows=session.scalars(stmt.order_by(DwdModelEvaluation.data_date.desc()).limit(limit)).all()
    return jsonable({"items":[{"id":r.id,"benchmark_slug":r.benchmark_name,"score":r.score,"evaluation_date":r.evaluated_at,
      "source":r.evaluation_platform,"test_conditions":r.test_conditions} for r in rows],"next_cursor":None})

@router.get("/api/v1/benchmarks")
def benchmarks(session:Session=Depends(get_db_session),limit:int=Query(100,le=500),cursor:str|None=None):
    rows=session.execute(select(DwdModelEvaluation.benchmark_name,func.count()).group_by(DwdModelEvaluation.benchmark_name).limit(limit)).all()
    return {"items":[{"id":n,"slug":n,"name":n,"category":None,"version_count":1,"result_count":c} for n,c in rows],"next_cursor":None}

@router.get("/api/v1/benchmarks/{name}")
def benchmark(name:str,session:Session=Depends(get_db_session)):
    count=session.scalar(select(func.count()).select_from(DwdModelEvaluation).where(DwdModelEvaluation.benchmark_name==name))
    if not count:raise HTTPException(404,f"benchmark '{name}' not found")
    return {"id":name,"slug":name,"name":name,"category":None,"versions":[{"version":"source","metrics":[{"slug":name,"name":"Score","unit":"source_native","score_direction":"higher_better"}]}],"capabilities":[]}

@router.get("/api/v1/compare/models")
def compare(items:str,session:Session=Depends(get_db_session)):
    ids=[x.split("@",1)[0] for x in items.split(",") if x]
    if not 2<=len(ids)<=5:raise HTTPException(422,"compare requires 2 to 5 items")
    rows=session.scalars(select(AdsModelWide).where(AdsModelWide.snapshot_date==_latest(session),AdsModelWide.model_id.in_(ids))).all()
    return jsonable({"items":[_item(r) for r in rows]})
