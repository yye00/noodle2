"""Analysis tools for Noodle 2 Study results."""

from src.analysis.diagnosis import (
    CompleteDiagnosisReport,
    CongestionDiagnosis,
    DiagnosisSummary,
    TimingDiagnosis,
    diagnose_congestion,
    diagnose_timing,
    generate_complete_diagnosis,
)
from src.analysis.path_comparison import (
    PathComparisonResult,
    PathIdentity,
    PathSlackEvolution,
    compare_timing_paths,
    generate_path_comparison_report,
)

__all__ = [
    # Path comparison
    "PathComparisonResult",
    "PathIdentity",
    "PathSlackEvolution",
    "compare_timing_paths",
    "generate_path_comparison_report",
    # Auto-diagnosis
    "diagnose_timing",
    "diagnose_congestion",
    "generate_complete_diagnosis",
    "TimingDiagnosis",
    "CongestionDiagnosis",
    "DiagnosisSummary",
    "CompleteDiagnosisReport",
]
