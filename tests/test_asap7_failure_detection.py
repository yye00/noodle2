"""Tests for ASAP7-specific failure mode detection."""

import tempfile
from pathlib import Path

import pytest

from src.controller.failure import (
    FailureClassification,
    FailureClassifier,
    FailureSeverity,
    FailureType,
)


class TestASAP7RoutingTrackInferenceFailure:
    """Test detection of ASAP7 routing track inference failure."""

    def test_detect_routing_track_inference_failure(self):
        """Verify routing track inference failure is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            # Simulate ASAP7 failure output when routing layers not specified
            stderr = """
[ERROR] Failed to infer routing track information
[ERROR] Cannot determine routing layers for technology
[ERROR] Routing failed to initialize
"""
            stdout = "Processing ASAP7 design..."

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout=stdout,
                stderr=stderr,
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            assert classification.failure_type == FailureType.CONFIGURATION_ERROR
            assert "routing track" in classification.reason.lower() or "routing layer" in classification.reason.lower()

    def test_classify_as_configuration_error_not_tool_error(self):
        """Verify ASAP7 routing failure is classified as configuration error, not tool error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            stderr = "[ERROR] Failed to infer routing track information for ASAP7"
            stdout = "Processing ASAP7 design..."

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout=stdout,
                stderr=stderr,
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            # Should be CONFIGURATION_ERROR, not TOOL_CRASH or ROUTING_FAILED
            assert classification.failure_type == FailureType.CONFIGURATION_ERROR
            assert classification.failure_type != FailureType.TOOL_CRASH
            assert classification.failure_type != FailureType.ROUTING_FAILED

    def test_emit_clear_diagnostic_with_required_fix(self):
        """Verify clear diagnostic message explains the required fix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            stderr = "[ERROR] Cannot infer routing tracks for ASAP7 PDK"
            stdout = "Processing ASAP7 design..."

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout=stdout,
                stderr=stderr,
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            # Diagnostic should mention the fix
            reason_lower = classification.reason.lower()
            assert any(
                keyword in reason_lower
                for keyword in ["set_routing_layers", "routing layer", "metal2-metal9", "workaround"]
            ), f"Diagnostic should mention required fix, got: {classification.reason}"

    def test_failure_is_deterministic_and_reproducible(self):
        """Verify failure detection is deterministic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            stderr = "[ERROR] Failed to infer routing track information"
            stdout = "ASAP7 processing"

            # Run classification multiple times
            classification1 = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout=stdout,
                stderr=stderr,
                artifacts_dir=artifacts_dir,
            )

            classification2 = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout=stdout,
                stderr=stderr,
                artifacts_dir=artifacts_dir,
            )

            # Should be deterministic - same inputs produce same classification
            assert classification1 is not None
            assert classification2 is not None
            assert classification1.failure_type == classification2.failure_type
            assert classification1.reason == classification2.reason

    def test_asap7_site_inference_failure_detected(self):
        """Verify ASAP7 site inference failure is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            stderr = "[ERROR] Cannot determine floorplan site for ASAP7"
            stdout = "Initializing floorplan..."

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout=stdout,
                stderr=stderr,
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            assert classification.failure_type == FailureType.CONFIGURATION_ERROR
            assert "site" in classification.reason.lower() or "floorplan" in classification.reason.lower()

    def test_asap7_pin_access_failure_detected(self):
        """Verify ASAP7 pin access failure is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            stderr = "[ERROR] Pin placement failed: cannot access pins on layer"
            stdout = "ASAP7 pin placement..."

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout=stdout,
                stderr=stderr,
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            assert classification.failure_type == FailureType.CONFIGURATION_ERROR

    def test_diagnostic_mentions_asap7_workarounds(self):
        """Verify diagnostic mentions ASAP7-specific workarounds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            stderr = "[ERROR] Routing track inference failed for ASAP7"
            stdout = "Processing..."

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout=stdout,
                stderr=stderr,
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            # Should mention ASAP7 or workarounds
            combined_text = (classification.reason + " " + classification.log_excerpt).lower()
            assert "asap7" in combined_text or "workaround" in combined_text

    def test_non_asap7_routing_failure_not_classified_as_config_error(self):
        """Verify non-ASAP7 routing failures are not misclassified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            # Generic routing failure without ASAP7 indicators
            stderr = "[ERROR] Routing failed: congestion overflow"
            stdout = "Processing Nangate45 design..."

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout=stdout,
                stderr=stderr,
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            # Should be ROUTING_FAILED, not CONFIGURATION_ERROR
            assert classification.failure_type == FailureType.ROUTING_FAILED

    def test_severity_is_appropriate(self):
        """Verify ASAP7 configuration error has appropriate severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            stderr = "[ERROR] Cannot infer routing tracks for ASAP7"
            stdout = "Processing..."

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout=stdout,
                stderr=stderr,
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            # Configuration errors should be HIGH severity (requires intervention)
            # but not CRITICAL (not catastrophic like OOM/segfault)
            assert classification.severity == FailureSeverity.HIGH

    def test_failure_is_not_recoverable_without_intervention(self):
        """Verify ASAP7 config failure requires intervention (not auto-recoverable)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            stderr = "[ERROR] Routing track inference failed for ASAP7"
            stdout = "Processing..."

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout=stdout,
                stderr=stderr,
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            # Requires adding workarounds to TCL script - not auto-recoverable
            assert not classification.recoverable


class TestASAP7FailurePatternMatching:
    """Test pattern matching for various ASAP7 failure modes."""

    @pytest.mark.parametrize(
        "error_message",
        [
            "[ERROR] Failed to infer routing track information",
            "[ERROR] Cannot determine routing tracks",
            "[ERROR] Routing layer inference failed",
            "Error: Unable to infer routing track spacing for ASAP7",
            "ERROR: Routing track configuration missing",
        ],
    )
    def test_various_routing_track_error_patterns(self, error_message):
        """Verify various routing track error patterns are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout="ASAP7 processing",
                stderr=error_message,
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            assert classification.failure_type == FailureType.CONFIGURATION_ERROR

    @pytest.mark.parametrize(
        "error_message",
        [
            "[ERROR] Cannot determine floorplan site",
            "[ERROR] Site specification missing for ASAP7",
            "Error: Unable to infer site dimensions",
            "ERROR: Floorplan site not specified",
        ],
    )
    def test_various_site_error_patterns(self, error_message):
        """Verify various site error patterns are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout="ASAP7 floorplan",
                stderr=error_message,
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            assert classification.failure_type == FailureType.CONFIGURATION_ERROR


class TestASAP7FailureClassifierIntegration:
    """Test integration of ASAP7 failure detection with broader failure classification."""

    def test_asap7_failure_detected_before_generic_routing_failure(self):
        """Verify ASAP7-specific detection takes precedence over generic routing failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            # Contains both "routing" and "failed", but also ASAP7-specific pattern
            stderr = "[ERROR] Routing failed: Cannot infer routing tracks for ASAP7"
            stdout = "Processing..."

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout=stdout,
                stderr=stderr,
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            # Should be CONFIGURATION_ERROR (ASAP7-specific), not ROUTING_FAILED
            assert classification.failure_type == FailureType.CONFIGURATION_ERROR

    def test_asap7_failure_provides_actionable_fix(self):
        """Verify ASAP7 failure provides actionable fix in diagnostic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            stderr = "[ERROR] Routing track inference failed for ASAP7"
            stdout = "Processing..."

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout=stdout,
                stderr=stderr,
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            reason = classification.reason.lower()

            # Should be actionable - tell user what to do
            # Check for keywords indicating a fix
            actionable_keywords = [
                "add",
                "specify",
                "set_routing_layers",
                "metal",
                "workaround",
                "require",
                "need",
            ]

            assert any(
                keyword in reason for keyword in actionable_keywords
            ), f"Diagnostic should be actionable, got: {classification.reason}"

    def test_error_log_excerpt_included(self):
        """Verify error log excerpt is included for debugging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            stderr = "[ERROR] Routing track inference failed for ASAP7\n[INFO] Context line 1\n[INFO] Context line 2"
            stdout = "Processing..."

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout=stdout,
                stderr=stderr,
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            assert classification.log_excerpt  # Should have log excerpt
            assert "routing" in classification.log_excerpt.lower()
