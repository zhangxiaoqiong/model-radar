"""Ingestion package: external source adapters, normalizers, sync pipeline."""

from .entity_resolution import MatchResult, match_external_model, normalize_name, similarity
from .normalizers import normalize_aa_evaluation
from .pipeline import run_sync_pipeline
from .snapshot_store import store_snapshot

__all__ = [
    "MatchResult",
    "match_external_model",
    "normalize_name",
    "similarity",
    "normalize_aa_evaluation",
    "run_sync_pipeline",
    "store_snapshot",
]
