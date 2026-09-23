from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from backend_core.db import Base
from backend_core.domain import AdsModelWide, DwdModelEvaluation, OdsAaModel, OdsOpenrouterModel
from ingestion.warehouse_pipeline import build_dwd, load_aa, load_openrouter, refresh_ads

def test_ods_dwd_ads_flow():
    engine=create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        aa=load_aa(session,[{"id":"aa-1","slug":"model-one","name":"Model One",
            "model_creator":{"name":"Vendor"},"release_date":"2026-09-01",
            "pricing":{"price_1m_input_tokens":1,"price_1m_output_tokens":4},
            "performance":{"median_output_tokens_per_second":80},
            "evaluations":{"intelligence_index":72.5}}])
        router=load_openrouter(session,[{"id":"vendor/model-one","name":"Vendor: Model One",
            "context_length":128000,"architecture":{"input_modalities":["text","image"],"output_modalities":["text"]},
            "supported_parameters":["tools"]}])
        assert build_dwd(session,aa,router)==1
        assert refresh_ads(session)==1
        assert session.scalar(select(func.count()).select_from(OdsAaModel))==1
        assert session.scalar(select(func.count()).select_from(OdsOpenrouterModel))==1
        assert session.scalar(select(func.count()).select_from(DwdModelEvaluation))==1
        wide=session.scalar(select(AdsModelWide))
        assert wide.context_window==128000
        assert float(wide.headline_scores["intelligence_index"])==72.5
