"""Stage performance tracking and summary generation.

Tracks stage execution metrics including throughput, compute time, and resource usage.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class StagePerformanceSummary:
    """
    Performance summary for a single Stage execution.

    Tracks:
    - Stage start and end times
    - Total trials executed
    - Throughput (trials/sec)
    - Total compute time across all trials
    - Resource utilization (CPU, memory if available)
    """

    stage_index: int
    stage_name: str
    start_time: str | None = None  # ISO 8601 timestamp
    end_time: str | None = None  # ISO 8601 timestamp (None if stage still running)
    trials_completed: int = 0
    trials_failed: int = 0
    trials_total: int = 0
    total_compute_time_seconds: float = 0.0  # Sum of all trial execution times
    total_cpu_time_seconds: float = 0.0  # Sum of CPU time from all trials
    peak_memory_mb: float = 0.0  # Maximum memory usage across all trials
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float | None:
        """
        Calculate stage duration in seconds.

        Returns:
            Duration in seconds, or None if stage has not ended or not started
        """
        if self.start_time is None or self.end_time is None:
            return None

        start = datetime.fromisoformat(self.start_time)
        end = datetime.fromisoformat(self.end_time)
        return (end - start).total_seconds()

    @property
    def throughput_trials_per_sec(self) -> float | None:
        """
        Calculate throughput in trials per second.

        Returns:
            Trials per second, or None if stage has not ended or duration is zero
        """
        duration = self.duration_seconds
        if duration is None or duration == 0:
            return None

        return self.trials_completed / duration

    @property
    def success_rate(self) -> float:
        """
        Calculate trial success rate.

        Returns:
            Success rate as a fraction (0.0 to 1.0)
        """
        if self.trials_total == 0:
            return 0.0

        return self.trials_completed / self.trials_total

    @property
    def avg_trial_time_seconds(self) -> float | None:
        """
        Calculate average trial execution time.

        Returns:
            Average trial time in seconds, or None if no trials completed
        """
        if self.trials_completed == 0:
            return None

        return self.total_compute_time_seconds / self.trials_completed

    def start(self) -> None:
        """Mark stage start time."""
        self.start_time = datetime.now(timezone.utc).isoformat()

    def end(self) -> None:
        """Mark stage end time."""
        self.end_time = datetime.now(timezone.utc).isoformat()

    def record_trial_completion(
        self,
        success: bool,
        execution_time_seconds: float,
        cpu_time_seconds: float | None = None,
        peak_memory_mb: float | None = None,
    ) -> None:
        """
        Record completion of a trial.

        Args:
            success: Whether trial succeeded
            execution_time_seconds: Wall-clock execution time
            cpu_time_seconds: CPU time consumed (optional)
            peak_memory_mb: Peak memory usage in MB (optional)
        """
        self.trials_total += 1

        if success:
            self.trials_completed += 1
        else:
            self.trials_failed += 1

        self.total_compute_time_seconds += execution_time_seconds

        if cpu_time_seconds is not None:
            self.total_cpu_time_seconds += cpu_time_seconds

        if peak_memory_mb is not None:
            self.peak_memory_mb = max(self.peak_memory_mb, peak_memory_mb)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "stage_index": self.stage_index,
            "stage_name": self.stage_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "trials": {
                "total": self.trials_total,
                "completed": self.trials_completed,
                "failed": self.trials_failed,
                "success_rate": self.success_rate,
            },
            "performance": {
                "throughput_trials_per_sec": self.throughput_trials_per_sec,
                "total_compute_time_seconds": self.total_compute_time_seconds,
                "avg_trial_time_seconds": self.avg_trial_time_seconds,
                "total_cpu_time_seconds": self.total_cpu_time_seconds,
                "peak_memory_mb": self.peak_memory_mb,
            },
            "metadata": self.metadata,
        }

    def save_json(self, output_path: Path) -> None:
        """
        Save performance summary to JSON file.

        Args:
            output_path: Path to output JSON file
        """
        import json

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def save_txt(self, output_path: Path) -> None:
        """
        Save performance summary to human-readable text file.

        Args:
            output_path: Path to output text file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.write(str(self))

    def _generate_progress_bar(self, completed: int, total: int, width: int = 50) -> str:
        """Generate ASCII progress bar.

        Args:
            completed: Number of completed items
            total: Total number of items
            width: Width of progress bar in characters (default: 50)

        Returns:
            Formatted progress bar string with percentage
        """
        if total == 0:
            return "[" + " " * width + "] 0.0%"

        percentage = (completed / total) * 100
        filled = int((completed / total) * width)
        bar = "█" * filled + "░" * (width - filled)

        return f"[{bar}] {percentage:.1f}%"

    def __str__(self) -> str:
        """Generate human-readable performance summary with visual progress indicators."""
        lines = []

        # Header
        lines.append("=" * 80)
        lines.append(f"STAGE PERFORMANCE SUMMARY - {self.stage_name}")
        lines.append("=" * 80)
        lines.append(f"Stage Index: {self.stage_index}")
        lines.append("")

        # Timing
        lines.append("Timing:")
        lines.append(f"  Start Time: {self.start_time}")
        lines.append(f"  End Time: {self.end_time or 'In Progress'}")
        if self.duration_seconds is not None:
            lines.append(f"  Duration: {self.duration_seconds:.2f} seconds")
        lines.append("")

        # Trial Counts with Visual Progress Bar
        lines.append("Trials:")
        lines.append(f"  Total: {self.trials_total}")
        lines.append(f"  Completed: {self.trials_completed}")
        lines.append(f"  Failed: {self.trials_failed}")
        lines.append(f"  Success Rate: {self.success_rate * 100:.1f}%")

        # Add visual progress bar for trial completion
        if self.trials_total > 0:
            lines.append("")
            lines.append("  Progress:")
            progress_bar = self._generate_progress_bar(self.trials_completed, self.trials_total)
            lines.append(f"    {progress_bar}")
            lines.append(f"    {self.trials_completed}/{self.trials_total} trials completed")

        lines.append("")

        # Performance Metrics
        lines.append("Performance:")
        if self.throughput_trials_per_sec is not None:
            lines.append(f"  Throughput: {self.throughput_trials_per_sec:.2f} trials/sec")
        else:
            lines.append("  Throughput: N/A (stage in progress)")

        lines.append(f"  Total Compute Time: {self.total_compute_time_seconds:.2f} seconds")

        if self.avg_trial_time_seconds is not None:
            lines.append(f"  Avg Trial Time: {self.avg_trial_time_seconds:.2f} seconds")

        if self.total_cpu_time_seconds > 0:
            lines.append(f"  Total CPU Time: {self.total_cpu_time_seconds:.2f} seconds")

        if self.peak_memory_mb > 0:
            lines.append(f"  Peak Memory: {self.peak_memory_mb:.1f} MB")

        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)


@dataclass
class StudyPerformanceSummary:
    """
    Aggregate performance summary for an entire Study.

    Combines performance data from all stages.
    """

    study_name: str
    stage_summaries: list[StagePerformanceSummary] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_trials(self) -> int:
        """Total trials across all stages."""
        return sum(stage.trials_total for stage in self.stage_summaries)

    @property
    def total_completed(self) -> int:
        """Total completed trials across all stages."""
        return sum(stage.trials_completed for stage in self.stage_summaries)

    @property
    def total_failed(self) -> int:
        """Total failed trials across all stages."""
        return sum(stage.trials_failed for stage in self.stage_summaries)

    @property
    def total_compute_time_seconds(self) -> float:
        """Total compute time across all stages."""
        return sum(stage.total_compute_time_seconds for stage in self.stage_summaries)

    @property
    def total_cpu_time_seconds(self) -> float:
        """Total CPU time across all stages."""
        return sum(stage.total_cpu_time_seconds for stage in self.stage_summaries)

    @property
    def overall_success_rate(self) -> float:
        """Overall success rate across all stages."""
        if self.total_trials == 0:
            return 0.0

        return self.total_completed / self.total_trials

    def add_stage(self, stage_summary: StagePerformanceSummary) -> None:
        """Add a stage performance summary."""
        self.stage_summaries.append(stage_summary)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "study_name": self.study_name,
            "totals": {
                "trials": self.total_trials,
                "completed": self.total_completed,
                "failed": self.total_failed,
                "success_rate": self.overall_success_rate,
                "total_compute_time_seconds": self.total_compute_time_seconds,
                "total_cpu_time_seconds": self.total_cpu_time_seconds,
            },
            "stages": [stage.to_dict() for stage in self.stage_summaries],
            "metadata": self.metadata,
        }

    def save_json(self, output_path: Path) -> None:
        """Save to JSON file."""
        import json

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def save_txt(self, output_path: Path) -> None:
        """Save to human-readable text file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.write(str(self))

    def __str__(self) -> str:
        """Generate human-readable study performance summary."""
        lines = []

        # Header
        lines.append("=" * 80)
        lines.append(f"STUDY PERFORMANCE SUMMARY - {self.study_name}")
        lines.append("=" * 80)
        lines.append("")

        # Overall Stats
        lines.append("Overall Statistics:")
        lines.append(f"  Total Trials: {self.total_trials}")
        lines.append(f"  Completed: {self.total_completed}")
        lines.append(f"  Failed: {self.total_failed}")
        lines.append(f"  Success Rate: {self.overall_success_rate * 100:.1f}%")
        lines.append(f"  Total Compute Time: {self.total_compute_time_seconds:.2f} seconds")
        if self.total_cpu_time_seconds > 0:
            lines.append(f"  Total CPU Time: {self.total_cpu_time_seconds:.2f} seconds")
        lines.append("")

        # Per-Stage Summary
        lines.append("Per-Stage Performance:")
        lines.append("-" * 80)

        for stage in self.stage_summaries:
            lines.append(f"\nStage {stage.stage_index}: {stage.stage_name}")
            lines.append(f"  Trials: {stage.trials_completed}/{stage.trials_total} completed")
            if stage.throughput_trials_per_sec is not None:
                lines.append(f"  Throughput: {stage.throughput_trials_per_sec:.2f} trials/sec")
            lines.append(f"  Compute Time: {stage.total_compute_time_seconds:.2f} seconds")
            if stage.avg_trial_time_seconds is not None:
                lines.append(f"  Avg Trial Time: {stage.avg_trial_time_seconds:.2f} seconds")

        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)
