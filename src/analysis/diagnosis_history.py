"""Diagnosis history tracking across stages.

This module tracks diagnosis reports across multiple stages of a study,
enabling trend analysis, issue resolution tracking, and informed decision
making in later stages.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.analysis.diagnosis import (
    CompleteDiagnosisReport,
    IssueType,
)


@dataclass
class StageDiagnosisEntry:
    """Single diagnosis entry for a stage."""

    stage_name: str
    timestamp: str
    wns_ps: int | None
    hot_ratio: float | None
    primary_issue: str | None  # IssueType value
    recommended_strategy: str | None
    eco_suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "stage_name": self.stage_name,
            "timestamp": self.timestamp,
        }

        if self.wns_ps is not None:
            result["wns_ps"] = self.wns_ps

        if self.hot_ratio is not None:
            result["hot_ratio"] = self.hot_ratio

        if self.primary_issue is not None:
            result["primary_issue"] = self.primary_issue

        if self.recommended_strategy is not None:
            result["recommended_strategy"] = self.recommended_strategy

        if self.eco_suggestions:
            result["eco_suggestions"] = self.eco_suggestions

        return result


@dataclass
class IssueResolution:
    """Tracks resolution of an issue across stages."""

    issue_type: str  # "timing" or "congestion"
    initial_stage: str
    initial_severity: float  # WNS or hot_ratio
    resolved_stage: str | None
    final_severity: float | None
    stages_to_resolve: int | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "issue_type": self.issue_type,
            "initial_stage": self.initial_stage,
            "initial_severity": self.initial_severity,
        }

        if self.resolved_stage is not None:
            result["resolved_stage"] = self.resolved_stage

        if self.final_severity is not None:
            result["final_severity"] = self.final_severity

        if self.stages_to_resolve is not None:
            result["stages_to_resolve"] = self.stages_to_resolve

        return result


@dataclass
class DiagnosisTrend:
    """Trend information for a metric across stages."""

    metric_name: str
    stages: list[str]
    values: list[float | int]
    trend: str  # "improving", "worsening", "stable"
    improvement_pct: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "metric_name": self.metric_name,
            "stages": self.stages,
            "values": self.values,
            "trend": self.trend,
        }

        if self.improvement_pct is not None:
            result["improvement_pct"] = self.improvement_pct

        return result


@dataclass
class DiagnosisHistory:
    """Complete diagnosis history across all stages."""

    study_name: str
    stages: list[StageDiagnosisEntry] = field(default_factory=list)
    issue_resolutions: list[IssueResolution] = field(default_factory=list)
    trends: list[DiagnosisTrend] = field(default_factory=list)

    def add_stage_diagnosis(
        self,
        stage_name: str,
        diagnosis_report: CompleteDiagnosisReport,
    ) -> None:
        """
        Add diagnosis for a stage.

        Args:
            stage_name: Name of the stage
            diagnosis_report: Complete diagnosis report for the stage
        """
        # Extract key metrics
        wns_ps = None
        if diagnosis_report.timing_diagnosis:
            wns_ps = diagnosis_report.timing_diagnosis.wns_ps

        hot_ratio = None
        if diagnosis_report.congestion_diagnosis:
            hot_ratio = diagnosis_report.congestion_diagnosis.hot_ratio

        primary_issue = None
        recommended_strategy = None
        eco_suggestions: list[str] = []

        if diagnosis_report.diagnosis_summary:
            primary_issue = diagnosis_report.diagnosis_summary.primary_issue.value
            recommended_strategy = diagnosis_report.diagnosis_summary.recommended_strategy

            # Extract ECO names from suggestions
            eco_suggestions = [
                eco.eco
                for eco in diagnosis_report.diagnosis_summary.eco_priority_queue[:5]
            ]

        # Create entry
        entry = StageDiagnosisEntry(
            stage_name=stage_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            wns_ps=wns_ps,
            hot_ratio=hot_ratio,
            primary_issue=primary_issue,
            recommended_strategy=recommended_strategy,
            eco_suggestions=eco_suggestions,
        )

        self.stages.append(entry)

        # Update trends
        self._update_trends()

        # Track issue resolutions
        self._track_issue_resolutions()

    def _update_trends(self) -> None:
        """Update trend information based on stage history."""
        if len(self.stages) < 2:
            # Need at least 2 stages for trends
            return

        self.trends = []

        # WNS trend (if available)
        wns_stages = [s.stage_name for s in self.stages if s.wns_ps is not None]
        wns_values = [s.wns_ps for s in self.stages if s.wns_ps is not None]

        if len(wns_values) >= 2:
            trend = self._calculate_trend(wns_values, lower_is_better=False)
            improvement_pct = None
            if wns_values[0] != 0:
                improvement_pct = ((wns_values[-1] - wns_values[0]) / abs(wns_values[0])) * 100

            self.trends.append(
                DiagnosisTrend(
                    metric_name="wns_ps",
                    stages=wns_stages,
                    values=wns_values,
                    trend=trend,
                    improvement_pct=improvement_pct,
                )
            )

        # Hot ratio trend (if available)
        hot_stages = [s.stage_name for s in self.stages if s.hot_ratio is not None]
        hot_values = [s.hot_ratio for s in self.stages if s.hot_ratio is not None]

        if len(hot_values) >= 2:
            trend = self._calculate_trend(hot_values, lower_is_better=True)
            improvement_pct = None
            if hot_values[0] != 0:
                improvement_pct = ((hot_values[0] - hot_values[-1]) / hot_values[0]) * 100

            self.trends.append(
                DiagnosisTrend(
                    metric_name="hot_ratio",
                    stages=hot_stages,
                    values=hot_values,
                    trend=trend,
                    improvement_pct=improvement_pct,
                )
            )

    def _calculate_trend(
        self,
        values: list[float | int],
        lower_is_better: bool,
    ) -> str:
        """Calculate trend direction from values."""
        if len(values) < 2:
            return "stable"

        first = values[0]
        last = values[-1]

        # Calculate relative change
        if isinstance(first, int):
            threshold = abs(first) * 0.1  # 10% threshold for integers
        else:
            threshold = abs(first) * 0.05  # 5% threshold for floats

        diff = last - first

        if abs(diff) < threshold:
            return "stable"

        if lower_is_better:
            # For metrics like hot_ratio, lower is better
            return "improving" if diff < 0 else "worsening"
        else:
            # For metrics like WNS (negative values), higher is better
            return "improving" if diff > 0 else "worsening"

    def _track_issue_resolutions(self) -> None:
        """Track issue resolutions based on stage history."""
        if len(self.stages) < 2:
            return

        self.issue_resolutions = []

        # Track timing issue resolution
        timing_stages = [
            (s.stage_name, s.wns_ps)
            for s in self.stages
            if s.wns_ps is not None
        ]

        if timing_stages:
            first_stage, first_wns = timing_stages[0]

            # Check if timing issue was present initially
            if first_wns < 0:
                # Find when it was resolved (WNS >= 0)
                resolved_stage = None
                final_wns = first_wns
                stages_to_resolve = None

                for i, (stage, wns) in enumerate(timing_stages[1:], start=1):
                    final_wns = wns
                    if wns >= 0 and resolved_stage is None:
                        resolved_stage = stage
                        stages_to_resolve = i
                        break

                self.issue_resolutions.append(
                    IssueResolution(
                        issue_type="timing",
                        initial_stage=first_stage,
                        initial_severity=float(first_wns),
                        resolved_stage=resolved_stage,
                        final_severity=float(final_wns),
                        stages_to_resolve=stages_to_resolve,
                    )
                )

        # Track congestion issue resolution
        congestion_stages = [
            (s.stage_name, s.hot_ratio)
            for s in self.stages
            if s.hot_ratio is not None
        ]

        if congestion_stages:
            first_stage, first_hot = congestion_stages[0]

            # Check if congestion issue was present initially
            if first_hot > 0.15:  # Threshold for congestion issue
                # Find when it was resolved (hot_ratio < 0.15)
                resolved_stage = None
                final_hot = first_hot
                stages_to_resolve = None

                for i, (stage, hot) in enumerate(congestion_stages[1:], start=1):
                    final_hot = hot
                    if hot < 0.15 and resolved_stage is None:
                        resolved_stage = stage
                        stages_to_resolve = i
                        break

                self.issue_resolutions.append(
                    IssueResolution(
                        issue_type="congestion",
                        initial_stage=first_stage,
                        initial_severity=first_hot,
                        resolved_stage=resolved_stage,
                        final_severity=final_hot,
                        stages_to_resolve=stages_to_resolve,
                    )
                )

    def get_latest_diagnosis(self) -> StageDiagnosisEntry | None:
        """Get the most recent diagnosis entry."""
        if not self.stages:
            return None
        return self.stages[-1]

    def get_stage_diagnosis(self, stage_name: str) -> StageDiagnosisEntry | None:
        """Get diagnosis for a specific stage."""
        for entry in self.stages:
            if entry.stage_name == stage_name:
                return entry
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "study_name": self.study_name,
            "stages": [s.to_dict() for s in self.stages],
        }

        if self.issue_resolutions:
            result["issue_resolutions"] = [
                r.to_dict() for r in self.issue_resolutions
            ]

        if self.trends:
            result["trends"] = [t.to_dict() for t in self.trends]

        return result

    def save(self, output_dir: Path) -> Path:
        """
        Save diagnosis history to JSON file.

        Args:
            output_dir: Directory to save diagnosis_history.json

        Returns:
            Path to saved file
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "diagnosis_history.json"

        with open(output_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

        return output_path

    @classmethod
    def load(cls, file_path: Path) -> "DiagnosisHistory":
        """
        Load diagnosis history from JSON file.

        Args:
            file_path: Path to diagnosis_history.json

        Returns:
            Loaded DiagnosisHistory object
        """
        with open(file_path) as f:
            data = json.load(f)

        history = cls(study_name=data["study_name"])

        # Load stages
        for stage_data in data.get("stages", []):
            entry = StageDiagnosisEntry(
                stage_name=stage_data["stage_name"],
                timestamp=stage_data["timestamp"],
                wns_ps=stage_data.get("wns_ps"),
                hot_ratio=stage_data.get("hot_ratio"),
                primary_issue=stage_data.get("primary_issue"),
                recommended_strategy=stage_data.get("recommended_strategy"),
                eco_suggestions=stage_data.get("eco_suggestions", []),
            )
            history.stages.append(entry)

        # Load issue resolutions
        for res_data in data.get("issue_resolutions", []):
            resolution = IssueResolution(
                issue_type=res_data["issue_type"],
                initial_stage=res_data["initial_stage"],
                initial_severity=res_data["initial_severity"],
                resolved_stage=res_data.get("resolved_stage"),
                final_severity=res_data.get("final_severity"),
                stages_to_resolve=res_data.get("stages_to_resolve"),
            )
            history.issue_resolutions.append(resolution)

        # Load trends
        for trend_data in data.get("trends", []):
            trend = DiagnosisTrend(
                metric_name=trend_data["metric_name"],
                stages=trend_data["stages"],
                values=trend_data["values"],
                trend=trend_data["trend"],
                improvement_pct=trend_data.get("improvement_pct"),
            )
            history.trends.append(trend)

        return history


def create_diagnosis_history(study_name: str) -> DiagnosisHistory:
    """
    Create a new diagnosis history tracker.

    Args:
        study_name: Name of the study

    Returns:
        New DiagnosisHistory object
    """
    return DiagnosisHistory(study_name=study_name)
