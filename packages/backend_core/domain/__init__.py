"""All domain models — imported here so Base.metadata covers every table."""

from .registry import (
    ModelAlias,
    ModelEndpoint,
    ModelFamily,
    ModelRelease,
    ModelVariant,
    Provider,
    Source,
)
from .benchmark import (
    Benchmark,
    BenchmarkCapabilityMap,
    BenchmarkMetric,
    BenchmarkVersion,
    Capability,
)
from .evaluation import Evaluation, EvaluationRun
from .observation import (
    Evidence,
    EvidenceLink,
    FieldObservation,
    ModelPerformance,
    ModelPricing,
)
from .operations import (
    AdminAuditLog,
    CapabilityScoreSnapshot,
    EntityResolutionQueue,
    GeneratedInsight,
    GeneratedInsightEvidence,
    ModelEvent,
    NormalizationRun,
    NormalizedEvaluation,
    PipelineRun,
    PipelineStageRun,
    SourceSnapshot,
)

__all__ = [
    "ModelAlias", "ModelEndpoint", "ModelFamily", "ModelRelease", "ModelVariant",
    "Provider", "Source",
    "Benchmark", "BenchmarkCapabilityMap", "BenchmarkMetric", "BenchmarkVersion",
    "Capability",
    "Evaluation", "EvaluationRun",
    "Evidence", "EvidenceLink", "FieldObservation", "ModelPerformance", "ModelPricing",
    "AdminAuditLog", "CapabilityScoreSnapshot", "EntityResolutionQueue",
    "GeneratedInsight", "GeneratedInsightEvidence", "ModelEvent",
    "NormalizationRun", "NormalizedEvaluation", "PipelineRun", "PipelineStageRun",
    "SourceSnapshot",
]
