"""Tests for stage performance tracking and summary generation."""

import json
import tempfile
import time
from pathlib import Path

import pytest

from src.telemetry.stage_performance import (
    StagePerformanceSummary,
    StudyPerformanceSummary,
)


class TestStagePerformanceSummary:
    """Test stage performance tracking."""

    def test_create_stage_performance_summary(self):
        """Test creating stage performance summary."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        assert summary.stage_index == 0
        assert summary.stage_name == "exploration"
        assert summary.trials_total == 0
        assert summary.trials_completed == 0
        assert summary.trials_failed == 0

    def test_track_stage_start_time(self):
        """Test tracking stage start time."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        summary.start()

        assert summary.start_time
        # Verify ISO 8601 format
        assert "T" in summary.start_time

    def test_track_stage_end_time(self):
        """Test tracking stage end time."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        summary.start()
        time.sleep(0.01)  # Small delay to ensure distinct timestamps
        summary.end()

        assert summary.end_time
        assert "T" in summary.end_time
        # End time should be after start time
        assert summary.end_time > summary.start_time

    def test_record_trial_completion_success(self):
        """Test recording successful trial completion."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        summary.record_trial_completion(
            success=True,
            execution_time_seconds=5.2,
            cpu_time_seconds=4.8,
            peak_memory_mb=256.0,
        )

        assert summary.trials_total == 1
        assert summary.trials_completed == 1
        assert summary.trials_failed == 0
        assert summary.total_compute_time_seconds == 5.2
        assert summary.total_cpu_time_seconds == 4.8
        assert summary.peak_memory_mb == 256.0

    def test_record_trial_completion_failure(self):
        """Test recording failed trial completion."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        summary.record_trial_completion(
            success=False,
            execution_time_seconds=2.1,
        )

        assert summary.trials_total == 1
        assert summary.trials_completed == 0
        assert summary.trials_failed == 1
        assert summary.total_compute_time_seconds == 2.1

    def test_count_completed_trials(self):
        """Test counting completed trials."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        # Record 5 successful, 2 failed
        for _ in range(5):
            summary.record_trial_completion(success=True, execution_time_seconds=1.0)

        for _ in range(2):
            summary.record_trial_completion(success=False, execution_time_seconds=1.0)

        assert summary.trials_total == 7
        assert summary.trials_completed == 5
        assert summary.trials_failed == 2

    def test_calculate_throughput(self):
        """Test calculating throughput (trials/sec)."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        summary.start()

        # Record trials
        for _ in range(10):
            summary.record_trial_completion(success=True, execution_time_seconds=0.5)

        time.sleep(0.1)  # Ensure measurable duration
        summary.end()

        throughput = summary.throughput_trials_per_sec
        assert throughput is not None
        assert throughput > 0
        # Should have completed 10 trials in a short time
        assert throughput > 1.0

    def test_throughput_none_before_stage_ends(self):
        """Test throughput is None before stage ends."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        summary.start()
        summary.record_trial_completion(success=True, execution_time_seconds=1.0)

        # Throughput should be None because stage hasn't ended
        assert summary.throughput_trials_per_sec is None

    def test_sum_total_compute_time(self):
        """Test summing total compute time across all trials."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        # Record trials with varying execution times
        summary.record_trial_completion(success=True, execution_time_seconds=5.0)
        summary.record_trial_completion(success=True, execution_time_seconds=3.0)
        summary.record_trial_completion(success=False, execution_time_seconds=1.0)

        assert summary.total_compute_time_seconds == 9.0

    def test_calculate_average_trial_time(self):
        """Test calculating average trial execution time."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        summary.record_trial_completion(success=True, execution_time_seconds=6.0)
        summary.record_trial_completion(success=True, execution_time_seconds=4.0)

        avg = summary.avg_trial_time_seconds
        assert avg is not None
        assert avg == 5.0  # (6 + 4) / 2

    def test_avg_trial_time_none_if_no_completed_trials(self):
        """Test average trial time is None if no trials completed."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        assert summary.avg_trial_time_seconds is None

        # Record only failed trial
        summary.record_trial_completion(success=False, execution_time_seconds=1.0)
        assert summary.avg_trial_time_seconds is None

    def test_track_peak_memory(self):
        """Test tracking peak memory across trials."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        summary.record_trial_completion(
            success=True, execution_time_seconds=1.0, peak_memory_mb=128.0
        )
        summary.record_trial_completion(
            success=True, execution_time_seconds=1.0, peak_memory_mb=256.0
        )
        summary.record_trial_completion(
            success=True, execution_time_seconds=1.0, peak_memory_mb=192.0
        )

        # Should track maximum
        assert summary.peak_memory_mb == 256.0

    def test_calculate_success_rate(self):
        """Test calculating trial success rate."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        # 7 successful, 3 failed = 70% success rate
        for _ in range(7):
            summary.record_trial_completion(success=True, execution_time_seconds=1.0)

        for _ in range(3):
            summary.record_trial_completion(success=False, execution_time_seconds=1.0)

        assert summary.success_rate == 0.7


class TestStagePerformanceSerialization:
    """Test stage performance summary serialization."""

    def test_to_dict_includes_all_fields(self):
        """Test to_dict includes all performance fields."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
            metadata={"key": "value"},
        )

        summary.start()
        summary.record_trial_completion(success=True, execution_time_seconds=5.0)
        summary.end()

        data = summary.to_dict()

        assert data["stage_index"] == 0
        assert data["stage_name"] == "exploration"
        assert "start_time" in data
        assert "end_time" in data
        assert "duration_seconds" in data
        assert "trials" in data
        assert "performance" in data
        assert data["metadata"]["key"] == "value"

    def test_to_dict_trials_section(self):
        """Test to_dict trials section."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        summary.record_trial_completion(success=True, execution_time_seconds=1.0)
        summary.record_trial_completion(success=True, execution_time_seconds=1.0)
        summary.record_trial_completion(success=False, execution_time_seconds=1.0)

        data = summary.to_dict()
        trials = data["trials"]

        assert trials["total"] == 3
        assert trials["completed"] == 2
        assert trials["failed"] == 1
        assert trials["success_rate"] == 2.0 / 3.0

    def test_to_dict_performance_section(self):
        """Test to_dict performance section."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        summary.start()
        summary.record_trial_completion(
            success=True,
            execution_time_seconds=5.0,
            cpu_time_seconds=4.5,
            peak_memory_mb=256.0,
        )
        summary.record_trial_completion(
            success=True,
            execution_time_seconds=3.0,
            cpu_time_seconds=2.8,
            peak_memory_mb=128.0,
        )
        summary.end()

        data = summary.to_dict()
        perf = data["performance"]

        assert perf["total_compute_time_seconds"] == 8.0
        assert perf["total_cpu_time_seconds"] == 7.3
        assert perf["peak_memory_mb"] == 256.0
        assert perf["avg_trial_time_seconds"] == 4.0
        assert perf["throughput_trials_per_sec"] is not None

    def test_save_json(self):
        """Test saving performance summary to JSON."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        summary.start()
        summary.record_trial_completion(success=True, execution_time_seconds=5.0)
        summary.end()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "stage_performance.json"
            summary.save_json(output_path)

            assert output_path.exists()

            # Verify JSON is valid
            with open(output_path) as f:
                data = json.load(f)
                assert data["stage_name"] == "exploration"
                assert data["trials"]["total"] == 1

    def test_save_txt(self):
        """Test saving performance summary to text."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        summary.start()
        summary.record_trial_completion(success=True, execution_time_seconds=5.0)
        summary.end()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "stage_performance.txt"
            summary.save_txt(output_path)

            assert output_path.exists()

            # Verify text content
            content = output_path.read_text()
            assert "STAGE PERFORMANCE SUMMARY" in content
            assert "exploration" in content


class TestStagePerformanceHumanReadable:
    """Test human-readable stage performance formatting."""

    def test_str_has_header(self):
        """Test string representation has header."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        output = str(summary)

        assert "STAGE PERFORMANCE SUMMARY - exploration" in output
        assert "Stage Index: 0" in output

    def test_str_includes_timing(self):
        """Test string representation includes timing information."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        summary.start()
        summary.end()

        output = str(summary)

        assert "Timing:" in output
        assert "Start Time:" in output
        assert "End Time:" in output
        assert "Duration:" in output

    def test_str_includes_trial_counts(self):
        """Test string representation includes trial counts."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        summary.record_trial_completion(success=True, execution_time_seconds=1.0)
        summary.record_trial_completion(success=True, execution_time_seconds=1.0)
        summary.record_trial_completion(success=False, execution_time_seconds=1.0)

        output = str(summary)

        assert "Trials:" in output
        assert "Total: 3" in output
        assert "Completed: 2" in output
        assert "Failed: 1" in output
        assert "Success Rate:" in output

    def test_str_includes_performance_metrics(self):
        """Test string representation includes performance metrics."""
        summary = StagePerformanceSummary(
            stage_index=0,
            stage_name="exploration",
        )

        summary.start()
        summary.record_trial_completion(
            success=True,
            execution_time_seconds=5.0,
            cpu_time_seconds=4.5,
            peak_memory_mb=256.0,
        )
        summary.end()

        output = str(summary)

        assert "Performance:" in output
        assert "Throughput:" in output
        assert "Total Compute Time:" in output
        assert "Avg Trial Time:" in output
        assert "Total CPU Time:" in output
        assert "Peak Memory:" in output


class TestStudyPerformanceSummary:
    """Test study-level performance aggregation."""

    def test_create_study_performance_summary(self):
        """Test creating study performance summary."""
        summary = StudyPerformanceSummary(study_name="test_study")

        assert summary.study_name == "test_study"
        assert len(summary.stage_summaries) == 0

    def test_add_stage_summary(self):
        """Test adding stage summaries to study."""
        study = StudyPerformanceSummary(study_name="test_study")

        stage0 = StagePerformanceSummary(stage_index=0, stage_name="exploration")
        stage1 = StagePerformanceSummary(stage_index=1, stage_name="refinement")

        study.add_stage(stage0)
        study.add_stage(stage1)

        assert len(study.stage_summaries) == 2

    def test_aggregate_total_trials(self):
        """Test aggregating total trials across stages."""
        study = StudyPerformanceSummary(study_name="test_study")

        stage0 = StagePerformanceSummary(stage_index=0, stage_name="exploration")
        stage0.record_trial_completion(success=True, execution_time_seconds=1.0)
        stage0.record_trial_completion(success=True, execution_time_seconds=1.0)

        stage1 = StagePerformanceSummary(stage_index=1, stage_name="refinement")
        stage1.record_trial_completion(success=True, execution_time_seconds=1.0)

        study.add_stage(stage0)
        study.add_stage(stage1)

        assert study.total_trials == 3
        assert study.total_completed == 3

    def test_aggregate_compute_time(self):
        """Test aggregating compute time across stages."""
        study = StudyPerformanceSummary(study_name="test_study")

        stage0 = StagePerformanceSummary(stage_index=0, stage_name="exploration")
        stage0.record_trial_completion(success=True, execution_time_seconds=5.0)

        stage1 = StagePerformanceSummary(stage_index=1, stage_name="refinement")
        stage1.record_trial_completion(success=True, execution_time_seconds=3.0)

        study.add_stage(stage0)
        study.add_stage(stage1)

        assert study.total_compute_time_seconds == 8.0

    def test_overall_success_rate(self):
        """Test calculating overall success rate."""
        study = StudyPerformanceSummary(study_name="test_study")

        stage0 = StagePerformanceSummary(stage_index=0, stage_name="exploration")
        stage0.record_trial_completion(success=True, execution_time_seconds=1.0)
        stage0.record_trial_completion(success=True, execution_time_seconds=1.0)
        stage0.record_trial_completion(success=False, execution_time_seconds=1.0)

        stage1 = StagePerformanceSummary(stage_index=1, stage_name="refinement")
        stage1.record_trial_completion(success=True, execution_time_seconds=1.0)

        study.add_stage(stage0)
        study.add_stage(stage1)

        # 3 completed out of 4 total = 75%
        assert study.overall_success_rate == 0.75

    def test_study_to_dict(self):
        """Test study performance summary to_dict."""
        study = StudyPerformanceSummary(study_name="test_study")

        stage0 = StagePerformanceSummary(stage_index=0, stage_name="exploration")
        stage0.record_trial_completion(success=True, execution_time_seconds=5.0)

        study.add_stage(stage0)

        data = study.to_dict()

        assert data["study_name"] == "test_study"
        assert "totals" in data
        assert "stages" in data
        assert len(data["stages"]) == 1

    def test_study_save_json(self):
        """Test saving study performance to JSON."""
        study = StudyPerformanceSummary(study_name="test_study")

        stage0 = StagePerformanceSummary(stage_index=0, stage_name="exploration")
        stage0.record_trial_completion(success=True, execution_time_seconds=5.0)

        study.add_stage(stage0)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "study_performance.json"
            study.save_json(output_path)

            assert output_path.exists()

            with open(output_path) as f:
                data = json.load(f)
                assert data["study_name"] == "test_study"

    def test_study_str_representation(self):
        """Test study performance human-readable format."""
        study = StudyPerformanceSummary(study_name="test_study")

        stage0 = StagePerformanceSummary(stage_index=0, stage_name="exploration")
        stage0.start()
        stage0.record_trial_completion(success=True, execution_time_seconds=5.0)
        stage0.end()

        study.add_stage(stage0)

        output = str(study)

        assert "STUDY PERFORMANCE SUMMARY - test_study" in output
        assert "Overall Statistics:" in output
        assert "Per-Stage Performance:" in output
        assert "Stage 0: exploration" in output


class TestStagePerformanceIntegration:
    """Test stage performance integration with Study execution."""

    def test_multi_stage_performance_tracking(self):
        """Test tracking performance across multiple stages."""
        study = StudyPerformanceSummary(study_name="multi_stage_study")

        # Stage 0: Exploration (10 trials, 2 failures)
        stage0 = StagePerformanceSummary(stage_index=0, stage_name="exploration")
        stage0.start()
        for _ in range(8):
            stage0.record_trial_completion(success=True, execution_time_seconds=2.0)
        for _ in range(2):
            stage0.record_trial_completion(success=False, execution_time_seconds=1.0)
        stage0.end()

        # Stage 1: Refinement (3 trials, all successful)
        stage1 = StagePerformanceSummary(stage_index=1, stage_name="refinement")
        stage1.start()
        for _ in range(3):
            stage1.record_trial_completion(success=True, execution_time_seconds=5.0)
        stage1.end()

        study.add_stage(stage0)
        study.add_stage(stage1)

        # Verify aggregation
        assert study.total_trials == 13
        assert study.total_completed == 11
        assert study.total_failed == 2
        assert study.total_compute_time_seconds == (8 * 2.0 + 2 * 1.0 + 3 * 5.0)

    def test_write_performance_summary_to_artifacts(self):
        """Test writing performance summary to stage artifacts."""
        summary = StagePerformanceSummary(stage_index=0, stage_name="exploration")

        summary.start()
        for _ in range(5):
            summary.record_trial_completion(success=True, execution_time_seconds=3.0)
        summary.end()

        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir) / "artifacts" / "stage_0"
            artifacts_dir.mkdir(parents=True)

            # Write both JSON and TXT
            summary.save_json(artifacts_dir / "performance_summary.json")
            summary.save_txt(artifacts_dir / "performance_summary.txt")

            # Verify both files exist
            assert (artifacts_dir / "performance_summary.json").exists()
            assert (artifacts_dir / "performance_summary.txt").exists()

    def test_performance_summary_enables_resource_planning(self):
        """Test performance summary enables resource budget planning."""
        study = StudyPerformanceSummary(study_name="planning_study")

        # Simulate 3 stages with realistic metrics
        stage0 = StagePerformanceSummary(stage_index=0, stage_name="exploration")
        stage0.start()
        for _ in range(20):
            stage0.record_trial_completion(
                success=True,
                execution_time_seconds=10.0,
                cpu_time_seconds=9.5,
                peak_memory_mb=512.0,
            )
        stage0.end()

        study.add_stage(stage0)

        # Use metrics for planning
        data = study.to_dict()
        totals = data["totals"]

        # Verify we can extract planning information
        assert totals["total_compute_time_seconds"] == 200.0
        assert totals["total_cpu_time_seconds"] == 190.0

        # From stage data, extract throughput and avg time
        stage0_data = data["stages"][0]
        throughput = stage0_data["performance"]["throughput_trials_per_sec"]
        avg_time = stage0_data["performance"]["avg_trial_time_seconds"]

        assert throughput is not None
        assert avg_time == 10.0

        # Can estimate resources for future stages:
        # If avg trial = 10s and throughput = X trials/sec,
        # then for N trials we need roughly N * 10s compute time
