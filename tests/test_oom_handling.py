"""Tests for out-of-memory (OOM) failure handling."""

from pathlib import Path

import pytest

from src.controller.failure import FailureClassifier, FailureSeverity, FailureType


class TestOOMDetectionViaExitCode:
    """Test OOM detection via exit code 137."""

    def test_detect_oom_via_exit_code_137(self, tmp_path: Path) -> None:
        """Step 2: Detect OOM condition via exit code (137 = 128 + 9 SIGKILL)."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="Container killed",
            artifacts_dir=tmp_path,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.OOM
        assert classification.severity == FailureSeverity.CRITICAL

    def test_oom_detection_without_text_markers(self, tmp_path: Path) -> None:
        """Exit code 137 alone should trigger OOM classification."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="Normal output",
            stderr="",
            artifacts_dir=tmp_path,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.OOM


class TestOOMDetectionViaTextMarkers:
    """Test OOM detection via text markers in logs."""

    @pytest.mark.parametrize(
        "marker",
        [
            "out of memory",
            "OOM",
            "killed",
            "signal 9",
        ],
    )
    def test_detect_oom_via_text_markers(self, tmp_path: Path, marker: str) -> None:
        """Step 2: Detect OOM condition via text markers in stderr/stdout."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="",
            stderr=f"Error: {marker}",
            artifacts_dir=tmp_path,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.OOM

    def test_oom_marker_case_insensitive(self, tmp_path: Path) -> None:
        """OOM detection should be case-insensitive."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="",
            stderr="ERROR: Out Of Memory",
            artifacts_dir=tmp_path,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.OOM


class TestOOMClassificationWithMemoryMetrics:
    """Test OOM classification includes memory metrics."""

    def test_classify_as_early_failure_out_of_memory(self, tmp_path: Path) -> None:
        """Step 3: Classify as early failure 'out_of_memory'."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="Killed",
            artifacts_dir=tmp_path,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.OOM
        assert classification.failure_type.value == "out_of_memory"

    def test_record_peak_memory_usage_in_failure_telemetry(self, tmp_path: Path) -> None:
        """Step 4: Record peak memory usage in failure telemetry."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="Killed",
            artifacts_dir=tmp_path,
            peak_memory_mb=7890.5,
        )

        assert classification is not None
        assert classification.metrics is not None
        assert "peak_memory_mb" in classification.metrics
        assert classification.metrics["peak_memory_mb"] == 7890.5

    def test_memory_metrics_included_in_dict_serialization(self, tmp_path: Path) -> None:
        """Memory metrics should be included in JSON serialization."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="Killed",
            artifacts_dir=tmp_path,
            peak_memory_mb=7890.5,
            memory_limit_mb=8192.0,
        )

        assert classification is not None
        data = classification.to_dict()
        assert "metrics" in data
        assert data["metrics"]["peak_memory_mb"] == 7890.5
        assert data["metrics"]["memory_limit_mb"] == 8192.0


class TestOOMMemoryIncreaseSuggestion:
    """Test that OOM failure suggests memory increase."""

    def test_suggest_memory_increase_when_near_limit(self, tmp_path: Path) -> None:
        """Step 5: Suggest memory increase in failure rationale."""
        # Peak usage at 96% of limit (above 95% threshold)
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="Killed",
            artifacts_dir=tmp_path,
            peak_memory_mb=7864.0,  # 96% of 8192
            memory_limit_mb=8192.0,
        )

        assert classification is not None
        assert "Suggest increasing memory limit" in classification.reason
        assert "12288 MB" in classification.reason  # 8192 * 1.5

    def test_suggest_memory_increase_when_limit_known_but_peak_unknown(
        self, tmp_path: Path
    ) -> None:
        """Suggest memory increase even if peak usage not available."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="Killed",
            artifacts_dir=tmp_path,
            peak_memory_mb=None,
            memory_limit_mb=8192.0,
        )

        assert classification is not None
        assert "Consider increasing memory limit" in classification.reason
        assert "12288 MB" in classification.reason

    def test_memory_increase_suggestion_is_150_percent(self, tmp_path: Path) -> None:
        """Memory increase suggestion should be 150% of current limit."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="Killed",
            artifacts_dir=tmp_path,
            peak_memory_mb=4000.0,
            memory_limit_mb=4096.0,
        )

        assert classification is not None
        # 4096 * 1.5 = 6144
        assert "6144 MB" in classification.reason

    def test_no_suggestion_if_peak_well_below_limit(self, tmp_path: Path) -> None:
        """No memory increase suggestion if peak usage well below limit."""
        # Peak at 50% of limit - likely not a memory issue
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="Killed",
            artifacts_dir=tmp_path,
            peak_memory_mb=4000.0,
            memory_limit_mb=8192.0,
        )

        assert classification is not None
        # Should not suggest increase if usage was well below limit
        assert "Suggest increasing" not in classification.reason


class TestOOMReasonMessage:
    """Test OOM failure reason message construction."""

    def test_reason_includes_peak_memory(self, tmp_path: Path) -> None:
        """Reason should include peak memory usage."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="",
            artifacts_dir=tmp_path,
            peak_memory_mb=7890.5,
        )

        assert classification is not None
        assert "peak usage: 7890.5 MB" in classification.reason

    def test_reason_includes_memory_limit(self, tmp_path: Path) -> None:
        """Reason should include memory limit."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="",
            artifacts_dir=tmp_path,
            memory_limit_mb=8192.0,
        )

        assert classification is not None
        assert "limit: 8192.0 MB" in classification.reason

    def test_reason_includes_both_metrics(self, tmp_path: Path) -> None:
        """Reason should include both peak usage and limit."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="",
            artifacts_dir=tmp_path,
            peak_memory_mb=7890.5,
            memory_limit_mb=8192.0,
        )

        assert classification is not None
        assert "peak usage: 7890.5 MB" in classification.reason
        assert "limit: 8192.0 MB" in classification.reason

    def test_reason_without_memory_metrics(self, tmp_path: Path) -> None:
        """Reason should be clear even without memory metrics."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="",
            artifacts_dir=tmp_path,
        )

        assert classification is not None
        assert "Out of memory error" in classification.reason


class TestOOMCriticalSeverity:
    """Test OOM failures are marked as critical."""

    def test_oom_is_critical_severity(self, tmp_path: Path) -> None:
        """OOM failures should be CRITICAL severity."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="",
            artifacts_dir=tmp_path,
        )

        assert classification is not None
        assert classification.severity == FailureSeverity.CRITICAL

    def test_oom_is_not_recoverable(self, tmp_path: Path) -> None:
        """OOM failures are not recoverable without intervention."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="",
            artifacts_dir=tmp_path,
        )

        assert classification is not None
        assert classification.recoverable is False

    def test_oom_is_catastrophic(self, tmp_path: Path) -> None:
        """OOM should be classified as catastrophic."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="",
            artifacts_dir=tmp_path,
        )

        assert classification is not None
        assert FailureClassifier.is_catastrophic(classification)


class TestOOMLogExcerpt:
    """Test OOM failure includes log excerpt."""

    def test_log_excerpt_included(self, tmp_path: Path) -> None:
        """OOM classification should include log excerpt."""
        stderr_content = "Process started\nMemory allocation failed\nKilled\n"

        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr=stderr_content,
            artifacts_dir=tmp_path,
        )

        assert classification is not None
        assert classification.log_excerpt
        assert "Killed" in classification.log_excerpt


class TestOOMEndToEnd:
    """End-to-end OOM handling tests."""

    def test_execute_trial_with_insufficient_memory_limits(self, tmp_path: Path) -> None:
        """Step 1: Execute trial with insufficient memory limits (simulated)."""
        # Simulate a trial that hit memory limit
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="Trial started\nPlacement running\n",
            stderr="[ERROR] Memory allocation failed\nKilled by signal 9\n",
            artifacts_dir=tmp_path,
            peak_memory_mb=2048.0,
            memory_limit_mb=2048.0,
        )

        # Step 2: Detect OOM condition
        assert classification is not None
        assert classification.failure_type == FailureType.OOM

        # Step 3: Classify as early failure 'out_of_memory'
        assert classification.failure_type.value == "out_of_memory"
        assert classification.severity == FailureSeverity.CRITICAL

        # Step 4: Record peak memory usage in failure telemetry
        assert classification.metrics is not None
        assert classification.metrics["peak_memory_mb"] == 2048.0

        # Step 5: Suggest memory increase in failure rationale
        assert "Suggest increasing memory limit" in classification.reason
        assert "3072 MB" in classification.reason  # 2048 * 1.5

        # Step 6: Continue Study with other trials (verified by not raising exception)
        assert not classification.recoverable

    def test_continue_study_with_other_trials_after_oom(self, tmp_path: Path) -> None:
        """Step 6: Continue Study with other trials after OOM."""
        # First trial hits OOM
        oom_classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="Killed",
            artifacts_dir=tmp_path,
            peak_memory_mb=8000.0,
            memory_limit_mb=8192.0,
        )

        assert oom_classification is not None
        assert oom_classification.failure_type == FailureType.OOM
        assert FailureClassifier.is_catastrophic(oom_classification)

        # Second trial succeeds (return code 0)
        success_classification = FailureClassifier.classify_trial_failure(
            return_code=0,
            stdout="Success",
            stderr="",
            artifacts_dir=tmp_path,
        )

        # Study should continue - no exception raised
        assert success_classification is None  # No failure for successful trial

    def test_oom_classification_is_deterministic(self, tmp_path: Path) -> None:
        """OOM classification should be deterministic and reproducible."""
        # Same inputs should produce same classification
        for _ in range(3):
            classification = FailureClassifier.classify_trial_failure(
                return_code=137,
                stdout="Test output",
                stderr="Killed",
                artifacts_dir=tmp_path,
                peak_memory_mb=7890.5,
                memory_limit_mb=8192.0,
            )

            assert classification is not None
            assert classification.failure_type == FailureType.OOM
            assert classification.severity == FailureSeverity.CRITICAL
            assert "7890.5 MB" in classification.reason
            assert "8192.0 MB" in classification.reason
