"""Nine-table analytical warehouse schema."""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import JSON, DECIMAL, BigInteger, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base, MYSQL_TABLE_KWARGS, TimestampMixin, UUIDMixin, utcnow

class EtlBatch(UUIDMixin, Base):
    __tablename__="etl_batch"; __table_args__=MYSQL_TABLE_KWARGS
    source_code: Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    interface_name: Mapped[str]=mapped_column(String(128),nullable=False)
    status: Mapped[str]=mapped_column(String(16),nullable=False,default="running")
    data_date: Mapped[date]=mapped_column(Date,nullable=False)
    started_at: Mapped[datetime]=mapped_column(DateTime,nullable=False,default=utcnow)
    finished_at: Mapped[datetime|None]=mapped_column(DateTime)
    fetched_count: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    loaded_count: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    rejected_count: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    request_params: Mapped[dict|None]=mapped_column(JSON)
    error_message: Mapped[str|None]=mapped_column(Text)

class OdsAaModel(UUIDMixin, Base):
    __tablename__="ods_aa_model"; __table_args__=(UniqueConstraint("batch_id","aa_model_id",name="uq_ods_aa_model_batch"),MYSQL_TABLE_KWARGS)
    batch_id: Mapped[str]=mapped_column(String(36),ForeignKey("etl_batch.id"),nullable=False,index=True)
    aa_model_id: Mapped[str]=mapped_column(String(256),nullable=False)
    model_slug: Mapped[str|None]=mapped_column(String(256))
    model_name: Mapped[str]=mapped_column(String(256),nullable=False)
    creator_name: Mapped[str|None]=mapped_column(String(128))
    release_date: Mapped[date|None]=mapped_column(Date)
    pricing: Mapped[dict|None]=mapped_column(JSON)
    performance: Mapped[dict|None]=mapped_column(JSON)
    evaluations: Mapped[dict|None]=mapped_column(JSON)
    raw_payload: Mapped[dict]=mapped_column(JSON,nullable=False)
    record_hash: Mapped[str]=mapped_column(String(64),nullable=False)
    collected_at: Mapped[datetime]=mapped_column(DateTime,nullable=False,default=utcnow)
    data_date: Mapped[date]=mapped_column(Date,nullable=False)

class OdsAaEvaluation(UUIDMixin, Base):
    __tablename__="ods_aa_evaluation"; __table_args__=(UniqueConstraint("batch_id","aa_model_id","evaluation_name",name="uq_ods_aa_eval_batch"),MYSQL_TABLE_KWARGS)
    batch_id: Mapped[str]=mapped_column(String(36),ForeignKey("etl_batch.id"),nullable=False,index=True)
    aa_model_id: Mapped[str]=mapped_column(String(256),nullable=False)
    model_slug: Mapped[str|None]=mapped_column(String(256))
    model_name: Mapped[str]=mapped_column(String(256),nullable=False)
    creator_name: Mapped[str|None]=mapped_column(String(128))
    evaluation_name: Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    score: Mapped[Decimal]=mapped_column(DECIMAL(18,6),nullable=False)
    raw_payload: Mapped[dict|None]=mapped_column(JSON)
    collected_at: Mapped[datetime]=mapped_column(DateTime,nullable=False,default=utcnow)
    data_date: Mapped[date]=mapped_column(Date,nullable=False)

class OdsOpenrouterModel(UUIDMixin, Base):
    __tablename__="ods_openrouter_model"; __table_args__=(UniqueConstraint("batch_id","openrouter_model_id",name="uq_ods_or_batch"),MYSQL_TABLE_KWARGS)
    batch_id: Mapped[str]=mapped_column(String(36),ForeignKey("etl_batch.id"),nullable=False,index=True)
    openrouter_model_id: Mapped[str]=mapped_column(String(256),nullable=False)
    model_name: Mapped[str]=mapped_column(String(256),nullable=False)
    description: Mapped[str|None]=mapped_column(Text)
    context_length: Mapped[int|None]=mapped_column(BigInteger)
    max_output_tokens: Mapped[int|None]=mapped_column(BigInteger)
    architecture: Mapped[dict|None]=mapped_column(JSON)
    supported_parameters: Mapped[list|None]=mapped_column(JSON)
    pricing: Mapped[dict|None]=mapped_column(JSON)
    raw_payload: Mapped[dict]=mapped_column(JSON,nullable=False)
    record_hash: Mapped[str]=mapped_column(String(64),nullable=False)
    collected_at: Mapped[datetime]=mapped_column(DateTime,nullable=False,default=utcnow)
    data_date: Mapped[date]=mapped_column(Date,nullable=False)

class DwdModel(UUIDMixin, TimestampMixin, Base):
    __tablename__="dwd_model"; __table_args__=(UniqueConstraint("model_key",name="uq_dwd_model_key"),MYSQL_TABLE_KWARGS)
    model_key: Mapped[str]=mapped_column(String(128),nullable=False)
    model_name: Mapped[str]=mapped_column(String(256),nullable=False,index=True)
    model_family: Mapped[str|None]=mapped_column(String(128)); model_version: Mapped[str|None]=mapped_column(String(128))
    vendor_name: Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    vendor_country: Mapped[str|None]=mapped_column(String(64)); region_group: Mapped[str|None]=mapped_column(String(16))
    release_date: Mapped[date|None]=mapped_column(Date); openness: Mapped[str|None]=mapped_column(String(32)); license_name: Mapped[str|None]=mapped_column(String(128))
    total_parameters_b: Mapped[Decimal|None]=mapped_column(DECIMAL(14,4)); active_parameters_b: Mapped[Decimal|None]=mapped_column(DECIMAL(14,4))
    parameter_scale: Mapped[str|None]=mapped_column(String(32)); architecture_type: Mapped[str|None]=mapped_column(String(128))
    context_window: Mapped[int|None]=mapped_column(BigInteger); max_output_tokens: Mapped[int|None]=mapped_column(BigInteger)
    input_modalities: Mapped[list|None]=mapped_column(JSON); output_modalities: Mapped[list|None]=mapped_column(JSON)
    supports_reasoning: Mapped[bool|None]=mapped_column(); supports_tool_calling: Mapped[bool|None]=mapped_column(); supports_structured_output: Mapped[bool|None]=mapped_column()
    tags: Mapped[list|None]=mapped_column(JSON)
    aa_model_id: Mapped[str|None]=mapped_column(String(256),index=True); openrouter_model_id: Mapped[str|None]=mapped_column(String(256),index=True)
    attribute_sources: Mapped[dict|None]=mapped_column(JSON)

class DwdModelEvaluation(UUIDMixin, Base):
    __tablename__="dwd_model_evaluation"; __table_args__=MYSQL_TABLE_KWARGS
    model_id: Mapped[str]=mapped_column(String(36),ForeignKey("dwd_model.id"),nullable=False,index=True)
    evaluation_platform: Mapped[str]=mapped_column(String(128),nullable=False); evaluator: Mapped[str|None]=mapped_column(String(128))
    benchmark_name: Mapped[str]=mapped_column(String(128),nullable=False,index=True); benchmark_version: Mapped[str|None]=mapped_column(String(64))
    capability_category: Mapped[str|None]=mapped_column(String(64)); score: Mapped[Decimal]=mapped_column(DECIMAL(18,6),nullable=False)
    score_unit: Mapped[str|None]=mapped_column(String(32)); ranking: Mapped[int|None]=mapped_column(Integer)
    test_conditions: Mapped[dict|None]=mapped_column(JSON); evaluated_at: Mapped[datetime|None]=mapped_column(DateTime)
    source_table: Mapped[str]=mapped_column(String(64),nullable=False); source_record_id: Mapped[str]=mapped_column(String(36),nullable=False)
    batch_id: Mapped[str]=mapped_column(String(36),ForeignKey("etl_batch.id"),nullable=False); data_date: Mapped[date]=mapped_column(Date,nullable=False,index=True)

class DwdModelPrice(UUIDMixin, Base):
    __tablename__="dwd_model_price"; __table_args__=MYSQL_TABLE_KWARGS
    model_id: Mapped[str]=mapped_column(String(36),ForeignKey("dwd_model.id"),nullable=False,index=True)
    service_provider: Mapped[str]=mapped_column(String(128),nullable=False); billing_unit: Mapped[str]=mapped_column(String(64),nullable=False,default="per_million_tokens")
    currency: Mapped[str]=mapped_column(String(8),nullable=False,default="USD")
    input_price: Mapped[Decimal|None]=mapped_column(DECIMAL(18,8)); output_price: Mapped[Decimal|None]=mapped_column(DECIMAL(18,8))
    cache_read_price: Mapped[Decimal|None]=mapped_column(DECIMAL(18,8)); cache_write_price: Mapped[Decimal|None]=mapped_column(DECIMAL(18,8))
    pricing_conditions: Mapped[dict|None]=mapped_column(JSON); effective_from: Mapped[datetime|None]=mapped_column(DateTime); effective_to: Mapped[datetime|None]=mapped_column(DateTime)
    source_table: Mapped[str]=mapped_column(String(64),nullable=False); source_record_id: Mapped[str]=mapped_column(String(36),nullable=False)
    batch_id: Mapped[str]=mapped_column(String(36),ForeignKey("etl_batch.id"),nullable=False); data_date: Mapped[date]=mapped_column(Date,nullable=False,index=True)

class DwdModelPerformance(UUIDMixin, Base):
    __tablename__="dwd_model_performance"; __table_args__=MYSQL_TABLE_KWARGS
    model_id: Mapped[str]=mapped_column(String(36),ForeignKey("dwd_model.id"),nullable=False,index=True)
    evaluation_platform: Mapped[str]=mapped_column(String(128),nullable=False); evaluator: Mapped[str|None]=mapped_column(String(128)); service_provider: Mapped[str|None]=mapped_column(String(128))
    output_tokens_per_second: Mapped[Decimal|None]=mapped_column(DECIMAL(18,4)); time_to_first_token_ms: Mapped[Decimal|None]=mapped_column(DECIMAL(18,4)); end_to_end_latency_ms: Mapped[Decimal|None]=mapped_column(DECIMAL(18,4))
    test_conditions: Mapped[dict|None]=mapped_column(JSON); measured_at: Mapped[datetime|None]=mapped_column(DateTime)
    source_table: Mapped[str]=mapped_column(String(64),nullable=False); source_record_id: Mapped[str]=mapped_column(String(36),nullable=False)
    batch_id: Mapped[str]=mapped_column(String(36),ForeignKey("etl_batch.id"),nullable=False); data_date: Mapped[date]=mapped_column(Date,nullable=False,index=True)

class AdsModelWide(UUIDMixin, Base):
    __tablename__="ads_model_wide"; __table_args__=(UniqueConstraint("snapshot_date","model_id",name="uq_ads_date_model"),MYSQL_TABLE_KWARGS)
    snapshot_date: Mapped[date]=mapped_column(Date,nullable=False,index=True); model_id: Mapped[str]=mapped_column(String(36),ForeignKey("dwd_model.id"),nullable=False,index=True)
    model_key: Mapped[str]=mapped_column(String(128),nullable=False); model_name: Mapped[str]=mapped_column(String(256),nullable=False); vendor_name: Mapped[str]=mapped_column(String(128),nullable=False)
    vendor_country: Mapped[str|None]=mapped_column(String(64)); region_group: Mapped[str|None]=mapped_column(String(16)); release_date: Mapped[date|None]=mapped_column(Date)
    openness: Mapped[str|None]=mapped_column(String(32)); parameter_scale: Mapped[str|None]=mapped_column(String(32))
    context_window: Mapped[int|None]=mapped_column(BigInteger); max_output_tokens: Mapped[int|None]=mapped_column(BigInteger)
    input_modalities: Mapped[list|None]=mapped_column(JSON); output_modalities: Mapped[list|None]=mapped_column(JSON); tags: Mapped[list|None]=mapped_column(JSON)
    headline_scores: Mapped[dict|None]=mapped_column(JSON); selected_service_provider: Mapped[str|None]=mapped_column(String(128))
    input_price: Mapped[Decimal|None]=mapped_column(DECIMAL(18,8)); output_price: Mapped[Decimal|None]=mapped_column(DECIMAL(18,8)); cache_read_price: Mapped[Decimal|None]=mapped_column(DECIMAL(18,8))
    output_tokens_per_second: Mapped[Decimal|None]=mapped_column(DECIMAL(18,4)); time_to_first_token_ms: Mapped[Decimal|None]=mapped_column(DECIMAL(18,4))
    source_summary: Mapped[dict|None]=mapped_column(JSON); quality_score: Mapped[Decimal|None]=mapped_column(DECIMAL(5,2)); refreshed_at: Mapped[datetime]=mapped_column(DateTime,nullable=False,default=utcnow)
