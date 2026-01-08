"""Structured telemetry emission for Noodle 2.

Telemetry is emitted across three axes:
- Study: Overall execution metrics and summary
- Stage: Per-stage aggregates and trial summaries
- Case: Per-case tracking across stages
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.trial_runner.trial import TrialResult


@dataclass
class CaseTelemetry:
    """Telemetry data for a single case across its lifecycle."""

    case_id: str
    base_case: str
    stage_index: int
    derived_index: int
    trials: list[dict[str, Any]] = field(default_factory=list)
    best_wns_ps: float | None = None
    best_tns_ps: float | None = None
    total_trials: int = 0
    successful_trials: int = 0
    failed_trials: int = 0
    total_runtime_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_trial(self, trial: "TrialResult") -> None:
        """Add a trial result to this case's telemetry."""
        self.total_trials += 1
        self.total_runtime_seconds += trial.runtime_seconds

        if trial.success:
            self.successful_trials += 1
        else:
            self.failed_trials += 1

        # Track trial summary
        trial_summary = {
            "trial_index": trial.config.trial_index,
            "success": trial.success,
            "return_code": trial.return_code,
            "runtime_seconds": trial.runtime_seconds,
            "metrics": trial.metrics,
        }

        if trial.failure:
            trial_summary["failure"] = trial.failure.to_dict()

        self.trials.append(trial_summary)

        # Update best metrics
        if trial.success and "wns_ps" in trial.metrics:
            wns = trial.metrics["wns_ps"]
            if self.best_wns_ps is None or wns > self.best_wns_ps:
                self.best_wns_ps = wns

        if trial.success and "tns_ps" in trial.metrics:
            tns = trial.metrics["tns_ps"]
            if self.best_tns_ps is None or tns > self.best_tns_ps:
                self.best_tns_ps = tns

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "case_id": self.case_id,
            "base_case": self.base_case,
            "stage_index": self.stage_index,
            "derived_index": self.derived_index,
            "trials": self.trials,
            "best_wns_ps": self.best_wns_ps,
            "best_tns_ps": self.best_tns_ps,
            "total_trials": self.total_trials,
            "successful_trials": self.successful_trials,
            "failed_trials": self.failed_trials,
            "total_runtime_seconds": self.total_runtime_seconds,
            "metadata": self.metadata,
        }


@dataclass
class StageTelemetry:
    """Telemetry data for a single stage."""

    stage_index: int
    stage_name: str
    trial_budget: int
    survivor_count: int
    trials_executed: int = 0
    successful_trials: int = 0
    failed_trials: int = 0
    survivors: list[str] = field(default_factory=list)
    total_runtime_seconds: float = 0.0
    cases_processed: list[str] = field(default_factory=list)
    failure_types: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_trial_result(self, trial: "TrialResult") -> None:
        """Add a trial result to stage telemetry."""
        self.trials_executed += 1
        self.total_runtime_seconds += trial.runtime_seconds

        if trial.success:
            self.successful_trials += 1
        else:
            self.failed_trials += 1
            # Track failure types
            if trial.failure:
                failure_type = trial.failure.failure_type.value
                self.failure_types[failure_type] = self.failure_types.get(failure_type, 0) + 1

        # Track unique cases
        case_id = trial.config.case_name
        if case_id not in self.cases_processed:
            self.cases_processed.append(case_id)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "stage_index": self.stage_index,
            "stage_name": self.stage_name,
            "trial_budget": self.trial_budget,
            "survivor_count": self.survivor_count,
            "trials_executed": self.trials_executed,
            "successful_trials": self.successful_trials,
            "failed_trials": self.failed_trials,
            "success_rate": self.successful_trials / self.trials_executed if self.trials_executed > 0 else 0.0,
            "survivors": self.survivors,
            "total_runtime_seconds": self.total_runtime_seconds,
            "cases_processed": self.cases_processed,
            "failure_types": self.failure_types,
            "metadata": self.metadata,
        }


@dataclass
class StudyTelemetry:
    """Telemetry data for an entire study."""

    study_name: str
    safety_domain: str
    total_stages: int
    stages_completed: int = 0
    total_trials: int = 0
    successful_trials: int = 0
    failed_trials: int = 0
    total_runtime_seconds: float = 0.0
    final_survivors: list[str] = field(default_factory=list)
    aborted: bool = False
    abort_reason: str | None = None
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_stage_telemetry(self, stage_telemetry: StageTelemetry) -> None:
        """Add stage telemetry to study aggregate."""
        self.stages_completed += 1
        self.total_trials += stage_telemetry.trials_executed
        self.successful_trials += stage_telemetry.successful_trials
        self.failed_trials += stage_telemetry.failed_trials
        self.total_runtime_seconds += stage_telemetry.total_runtime_seconds

    def finalize(self, final_survivors: list[str], aborted: bool = False, abort_reason: str | None = None) -> None:
        """Finalize study telemetry."""
        self.end_time = time.time()
        self.final_survivors = final_survivors
        self.aborted = aborted
        self.abort_reason = abort_reason

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "study_name": self.study_name,
            "safety_domain": self.safety_domain,
            "total_stages": self.total_stages,
            "stages_completed": self.stages_completed,
            "total_trials": self.total_trials,
            "successful_trials": self.successful_trials,
            "failed_trials": self.failed_trials,
            "success_rate": self.successful_trials / self.total_trials if self.total_trials > 0 else 0.0,
            "total_runtime_seconds": self.total_runtime_seconds,
            "final_survivors": self.final_survivors,
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "metadata": self.metadata,
        }

        if self.end_time:
            result["wall_clock_seconds"] = self.end_time - self.start_time

        return result


class TelemetryEmitter:
    """
    Emits structured telemetry across Study, Stage, and Case axes.

    Directory structure:
        telemetry/{study_name}/
            study_telemetry.json          # Study-level aggregate
            stage_{i}_telemetry.json      # Per-stage telemetry
            cases/
                {case_id}_telemetry.json  # Per-case telemetry
    """

    def __init__(self, study_name: str, telemetry_root: str | Path = "telemetry") -> None:
        """
        Initialize telemetry emitter.

        Args:
            study_name: Name of the study
            telemetry_root: Root directory for telemetry files
        """
        self.study_name = study_name
        self.telemetry_root = Path(telemetry_root)
        self.study_dir = self.telemetry_root / study_name
        self.cases_dir = self.study_dir / "cases"

        # Create directories
        self.study_dir.mkdir(parents=True, exist_ok=True)
        self.cases_dir.mkdir(parents=True, exist_ok=True)

        # Telemetry tracking
        self.case_telemetry: dict[str, CaseTelemetry] = {}

    def emit_study_telemetry(self, study_telemetry: StudyTelemetry) -> Path:
        """
        Emit study-level telemetry.

        Args:
            study_telemetry: Study telemetry data

        Returns:
            Path to the written telemetry file
        """
        telemetry_file = self.study_dir / "study_telemetry.json"
        with telemetry_file.open("w") as f:
            json.dump(study_telemetry.to_dict(), f, indent=2)
        return telemetry_file

    def emit_stage_telemetry(self, stage_telemetry: StageTelemetry) -> Path:
        """
        Emit stage-level telemetry.

        Args:
            stage_telemetry: Stage telemetry data

        Returns:
            Path to the written telemetry file
        """
        telemetry_file = self.study_dir / f"stage_{stage_telemetry.stage_index}_telemetry.json"
        with telemetry_file.open("w") as f:
            json.dump(stage_telemetry.to_dict(), f, indent=2)
        return telemetry_file

    def emit_case_telemetry(self, case_telemetry: CaseTelemetry) -> Path:
        """
        Emit case-level telemetry.

        Args:
            case_telemetry: Case telemetry data

        Returns:
            Path to the written telemetry file
        """
        # Sanitize case_id for filename (replace / with _)
        safe_case_id = case_telemetry.case_id.replace("/", "_")
        telemetry_file = self.cases_dir / f"{safe_case_id}_telemetry.json"

        with telemetry_file.open("w") as f:
            json.dump(case_telemetry.to_dict(), f, indent=2)
        return telemetry_file

    def get_or_create_case_telemetry(self, case_id: str, base_case: str, stage_index: int, derived_index: int) -> CaseTelemetry:
        """
        Get or create case telemetry for tracking.

        Args:
            case_id: Case identifier
            base_case: Base case name
            stage_index: Current stage index
            derived_index: Derived case index

        Returns:
            CaseTelemetry object for this case
        """
        if case_id not in self.case_telemetry:
            self.case_telemetry[case_id] = CaseTelemetry(
                case_id=case_id,
                base_case=base_case,
                stage_index=stage_index,
                derived_index=derived_index,
            )
        return self.case_telemetry[case_id]

    def flush_all_case_telemetry(self) -> list[Path]:
        """
        Flush all tracked case telemetry to disk.

        Returns:
            List of paths to written telemetry files
        """
        paths = []
        for case_telemetry in self.case_telemetry.values():
            path = self.emit_case_telemetry(case_telemetry)
            paths.append(path)
        return paths
