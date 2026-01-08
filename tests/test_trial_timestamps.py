"""Tests for trial timestamp tracking and performance analysis."""

from datetime import datetime, timedelta, timezone

import pytest

from src.trial_runner.trial import TrialConfig, TrialResult, TrialArtifacts


class TestTrialTimestamps:
    """Test trial timestamp tracking for execution time analysis."""

    def test_trial_result_has_timestamp_fields(self):
        """Verify TrialResult has start_time and end_time fields."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=10.5,
            artifacts=artifacts,
            start_time="2024-01-08T12:00:00+00:00",
            end_time="2024-01-08T12:00:10+00:00",
        )

        assert hasattr(result, "start_time")
        assert hasattr(result, "end_time")
        assert result.start_time == "2024-01-08T12:00:00+00:00"
        assert result.end_time == "2024-01-08T12:00:10+00:00"

    def test_timestamp_fields_default_to_empty_string(self):
        """Verify timestamp fields default to empty string."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=10.5,
            artifacts=artifacts,
        )

        assert result.start_time == ""
        assert result.end_time == ""

    def test_timestamps_in_iso8601_format(self):
        """Verify timestamps use ISO 8601 format."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        # ISO 8601 format: YYYY-MM-DDTHH:MM:SS+00:00
        start = datetime.now(timezone.utc).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(seconds=10)).isoformat()

        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=10.5,
            artifacts=artifacts,
            start_time=start,
            end_time=end,
        )

        # Verify format can be parsed back
        parsed_start = datetime.fromisoformat(result.start_time)
        parsed_end = datetime.fromisoformat(result.end_time)

        assert isinstance(parsed_start, datetime)
        assert isinstance(parsed_end, datetime)
        assert parsed_end > parsed_start

    def test_timestamps_serialized_to_dict(self):
        """Verify timestamps are included in to_dict() output."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=10.5,
            artifacts=artifacts,
            start_time="2024-01-08T12:00:00+00:00",
            end_time="2024-01-08T12:00:10+00:00",
        )

        result_dict = result.to_dict()

        assert "start_time" in result_dict
        assert "end_time" in result_dict
        assert result_dict["start_time"] == "2024-01-08T12:00:00+00:00"
        assert result_dict["end_time"] == "2024-01-08T12:00:10+00:00"

    def test_timestamps_enable_performance_analysis(self):
        """Verify timestamps can be used for performance analysis."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        # Create results for multiple trials with different durations
        results = []
        for i in range(3):
            start = datetime(2024, 1, 8, 12, 0, i * 10, tzinfo=timezone.utc)
            end = start + timedelta(seconds=5 + i * 2)

            result = TrialResult(
                config=config,
                success=True,
                return_code=0,
                runtime_seconds=5.0 + i * 2,
                artifacts=artifacts,
                start_time=start.isoformat(),
                end_time=end.isoformat(),
            )
            results.append(result)

        # Performance analysis: calculate durations from timestamps
        durations = []
        for result in results:
            start = datetime.fromisoformat(result.start_time)
            end = datetime.fromisoformat(result.end_time)
            duration = (end - start).total_seconds()
            durations.append(duration)

        assert durations == [5.0, 7.0, 9.0]

        # Can compute statistics
        avg_duration = sum(durations) / len(durations)
        assert avg_duration == pytest.approx(7.0)


class TestTrialDurationCalculation:
    """Test duration calculation from timestamps."""

    def test_calculate_duration_from_valid_timestamps(self):
        """Test calculating duration from valid start and end timestamps."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=10.5,
            artifacts=artifacts,
            start_time="2024-01-08T12:00:00+00:00",
            end_time="2024-01-08T12:00:10+00:00",
        )

        duration = result.calculate_duration_seconds()

        assert duration == pytest.approx(10.0)

    def test_calculate_duration_returns_none_if_timestamps_missing(self):
        """Test that duration calculation returns None if timestamps are missing."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        # Missing timestamps
        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=10.5,
            artifacts=artifacts,
        )

        duration = result.calculate_duration_seconds()
        assert duration is None

    def test_calculate_duration_handles_invalid_timestamps(self):
        """Test that duration calculation handles invalid timestamp formats gracefully."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        # Invalid timestamp format
        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=10.5,
            artifacts=artifacts,
            start_time="invalid",
            end_time="also-invalid",
        )

        duration = result.calculate_duration_seconds()
        assert duration is None

    def test_duration_calculation_with_fractional_seconds(self):
        """Test duration calculation with fractional seconds."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=10.5,
            artifacts=artifacts,
            start_time="2024-01-08T12:00:00.000000+00:00",
            end_time="2024-01-08T12:00:10.500000+00:00",
        )

        duration = result.calculate_duration_seconds()
        assert duration == pytest.approx(10.5)

    def test_duration_calculation_cross_midnight(self):
        """Test duration calculation across midnight boundary."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=3600.0,
            artifacts=artifacts,
            start_time="2024-01-08T23:30:00+00:00",
            end_time="2024-01-09T00:30:00+00:00",
        )

        duration = result.calculate_duration_seconds()
        assert duration == pytest.approx(3600.0)


class TestTimestampPerformanceAnalysis:
    """Test using timestamps for performance analysis scenarios."""

    def test_compare_multiple_trials_by_execution_time(self):
        """Test comparing multiple trials by execution time."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        # Create trials with different execution times
        trials = []
        for i in range(5):
            start = datetime(2024, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
            # Vary execution time: 5s, 7s, 11s, 17s, 25s
            # Formula: 5 + i + i*i = 5, 5+1+1=7, 5+2+4=11, 5+3+9=17, 5+4+16=25
            duration = 5 + i + i * i
            end = start + timedelta(seconds=duration)

            trial = TrialResult(
                config=config,
                success=True,
                return_code=0,
                runtime_seconds=duration,
                artifacts=artifacts,
                start_time=start.isoformat(),
                end_time=end.isoformat(),
            )
            trials.append(trial)

        # Sort by duration
        sorted_trials = sorted(
            trials, key=lambda t: t.calculate_duration_seconds() or 0
        )

        durations = [t.calculate_duration_seconds() for t in sorted_trials]
        assert durations == [5.0, 7.0, 11.0, 17.0, 25.0]

    def test_identify_slow_trials(self):
        """Test identifying trials that exceed performance threshold."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        # Create trials with various execution times
        trials = []
        durations = [5.0, 12.0, 8.0, 25.0, 9.0, 30.0]

        for i, duration in enumerate(durations):
            start = datetime(2024, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
            end = start + timedelta(seconds=duration)

            trial = TrialResult(
                config=config,
                success=True,
                return_code=0,
                runtime_seconds=duration,
                artifacts=artifacts,
                start_time=start.isoformat(),
                end_time=end.isoformat(),
            )
            trials.append(trial)

        # Identify trials exceeding 15 second threshold
        threshold = 15.0
        slow_trials = [
            t for t in trials if (t.calculate_duration_seconds() or 0) > threshold
        ]

        assert len(slow_trials) == 2
        assert all((t.calculate_duration_seconds() or 0) > 15.0 for t in slow_trials)

    def test_stage_performance_summary(self):
        """Test computing stage-level performance summary from trial timestamps."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        # Create 10 trials with varying execution times
        trials = []
        for i in range(10):
            start = datetime(2024, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
            duration = 10.0 + i * 2  # 10, 12, 14, ..., 28 seconds
            end = start + timedelta(seconds=duration)

            trial = TrialResult(
                config=config,
                success=True,
                return_code=0,
                runtime_seconds=duration,
                artifacts=artifacts,
                start_time=start.isoformat(),
                end_time=end.isoformat(),
            )
            trials.append(trial)

        # Compute performance summary
        durations = [t.calculate_duration_seconds() for t in trials]
        durations = [d for d in durations if d is not None]

        summary = {
            "min_duration": min(durations),
            "max_duration": max(durations),
            "avg_duration": sum(durations) / len(durations),
            "total_duration": sum(durations),
        }

        assert summary["min_duration"] == pytest.approx(10.0)
        assert summary["max_duration"] == pytest.approx(28.0)
        assert summary["avg_duration"] == pytest.approx(19.0)
        assert summary["total_duration"] == pytest.approx(190.0)
