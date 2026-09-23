"""Fetch current sources and execute ODS -> DWD -> ADS."""
from __future__ import annotations
import argparse,re,sys
from datetime import date,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend_core.config import get_settings
from backend_core.db import create_db_engine,make_session_factory
from ingestion.adapters.artificial_analysis import AAClient
from ingestion.adapters.openrouter import fetch_openrouter_models
from ingestion.warehouse_pipeline import build_dwd,load_aa,load_openrouter,refresh_ads

MAINSTREAM_VENDORS={
    "openai","anthropic","google","google deepmind","meta","xai","mistral","mistral ai",
    "deepseek","alibaba","alibaba cloud","qwen","zhipu","zhipu ai","glm",
    "moonshot","moonshot ai","kimi","minimax","baidu","bytedance","bytedance seed",
}

def _norm(value):
    return re.sub(r"[^a-z0-9]+"," ",str(value).lower()).strip()

def recent_mainstream_aa(rows,*,today=None,days=90):
    cutoff=(today or date.today())-timedelta(days=days); end=today or date.today(); result=[]
    for row in rows:
        creator=_norm((row.get("model_creator") or {}).get("name"))
        try: released=date.fromisoformat(str(row.get("release_date") or "")[:10])
        except ValueError: continue
        if cutoff<=released<=end and any(v==creator or v in creator for v in MAINSTREAM_VENDORS):
            result.append(row)
    return result

def matching_openrouter(rows,aa_rows):
    names={_norm(row.get("name")) for row in aa_rows}
    names|={_norm(row.get("slug")) for row in aa_rows}
    result=[]
    for row in rows:
        display=str(row.get("name") or "").split(": ",1)[-1]
        model_id=str(row.get("id") or "").split("/",1)[-1]
        if _norm(display) in names or _norm(model_id) in names:
            result.append(row)
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--dry-run",action="store_true");args=parser.parse_args()
    settings=get_settings()
    aa_all=AAClient(api_key=settings.aa_api_key,base_url=settings.aa_base_url).fetch_models()
    aa_rows=recent_mainstream_aa(aa_all)
    try:or_rows=matching_openrouter(fetch_openrouter_models(),aa_rows)
    except Exception as exc:
        print(f"OpenRouter unavailable: {type(exc).__name__}");or_rows=[]
    if args.dry_run:
        print(f"AA: {len(aa_all)} fetched, {len(aa_rows)} recent mainstream; OpenRouter matched: {len(or_rows)}");return 0
    engine=create_db_engine(settings.database_url);session=make_session_factory(engine)()
    try:
        aa_batch=load_aa(session,aa_rows);or_batch=load_openrouter(session,or_rows) if or_rows else None
        models=build_dwd(session,aa_batch,or_batch);wide=refresh_ads(session)
        session.commit();print(f"AA batch {aa_batch.id}: {aa_batch.loaded_count} ODS rows")
        if or_batch:print(f"OpenRouter batch {or_batch.id}: {or_batch.loaded_count} ODS rows")
        print(f"DWD models: {models}; ADS rows: {wide}");return 0
    except Exception:
        session.rollback();raise
    finally:session.close();engine.dispose()
if __name__=="__main__":sys.exit(main())
