"""Minimal warehouse operations API."""
from datetime import date
from fastapi import APIRouter,Depends,Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend_core.domain import EtlBatch
from ..deps import get_db_session,require_admin,row_dict
router=APIRouter(prefix="/api/v1/admin",dependencies=[Depends(require_admin)])

@router.get("/batches")
@router.get("/pipelines")
def batches(session:Session=Depends(get_db_session),status:str|None=None,limit:int=Query(50,le=200),cursor:str|None=None):
    stmt=select(EtlBatch)
    if status:stmt=stmt.where(EtlBatch.status==status)
    rows=session.scalars(stmt.order_by(EtlBatch.started_at.desc()).limit(limit)).all()
    cols=["id","source_code","interface_name","status","data_date","started_at","finished_at","fetched_count","loaded_count","rejected_count","error_message"]
    return {"items":[row_dict(r,cols) for r in rows],"next_cursor":None}

@router.post("/sync",status_code=202)
def trigger(session:Session=Depends(get_db_session)):
    batch=EtlBatch(source_code="artificial_analysis",interface_name="language/models/free",status="pending",data_date=date.today())
    session.add(batch);session.flush()
    return {"batch_id":batch.id,"run_id":batch.id,"status":"pending"}
