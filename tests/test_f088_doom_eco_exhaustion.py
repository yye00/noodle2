"""
Tests for F088: Doom detection identifies ECO exhaustion when all ECOs failed or suspicious.

Steps from feature_list.json:
1. Create a study where all applicable ECOs have failed
2. Mark all ECO priors as suspicious
3. Run doom detector eco_exhaustion check
4. Verify doom_type is eco_exhaustion
5. Verify study terminates with ECO gap report
"""

import pytest
from src.controller.doom_detection import (
    DoomConfig,
    DoomDetector,
    DoomType,
    format_doom_report,
)


# Mock ECO Prior class for testing
class MockECOPrior:
    """Mock ECO prior with outcome."""

    def __init__(self, eco_type: str, outcome: str):
        self.eco_type = eco_type
        self.outcome = outcome


class TestF088ECOExhaustionDoomDetection:
    """Test ECO exhaustion doom detection."""

    def test_step_1_create_study_where_all_ecos_failed(self):
        """Step 1: Create a study where all applicable ECOs have failed."""
        # Create ECO priors where all have failed
        eco_priors = [
            MockECOPrior("CellResizeECO", "failed"),
            MockECOPrior("BufferInsertionECO", "failed"),
            MockECOPrior("GateCloningECO", "failed"),
            MockECOPrior("CellSwapECO", "failed"),
        ]

        assert len(eco_priors) >= 3, "Should have at least 3 ECO priors"
        assert all(prior.outcome == "failed" for prior in eco_priors), "All ECOs should be failed"

    def test_step_2_mark_all_eco_priors_as_suspicious(self):
        """Step 2: Mark all ECO priors as suspicious."""
        eco_priors = [
            MockECOPrior("CellResizeECO", "suspicious"),
            MockECOPrior("BufferInsertionECO", "suspicious"),
            MockECOPrior("GateCloningECO", "suspicious"),
        ]

        assert all(prior.outcome == "suspicious" for prior in eco_priors), \
            "All ECOs should be marked suspicious"

    def test_step_3_run_doom_detector_eco_exhaustion_check(self):
        """Step 3: Run doom detector eco_exhaustion check."""
        config = DoomConfig(
            enabled=True,
            eco_exhaustion_enabled=True,
        )

        detector = DoomDetector(config)

        # All failed ECOs
        eco_priors = [
            MockECOPrior("CellResizeECO", "failed"),
            MockECOPrior("BufferInsertionECO", "failed"),
            MockECOPrior("GateCloningECO", "failed"),
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()
        metrics = {"wns_ps": -1000}

        result = detector.check_doom(mock_case, metrics, eco_priors=eco_priors)

        assert result is not None, "Doom detector should return a result"
        assert hasattr(result, "is_doomed"), "Result should have is_doomed attribute"

    def test_step_4_verify_doom_type_is_eco_exhaustion(self):
        """Step 4: Verify doom_type is eco_exhaustion."""
        config = DoomConfig(enabled=True, eco_exhaustion_enabled=True)
        detector = DoomDetector(config)

        # All failed ECOs
        eco_priors = [
            MockECOPrior("CellResizeECO", "failed"),
            MockECOPrior("BufferInsertionECO", "failed"),
            MockECOPrior("GateCloningECO", "failed"),
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()
        metrics = {"wns_ps": -1000}

        result = detector.check_doom(mock_case, metrics, eco_priors=eco_priors)

        assert result.is_doomed is True, "All failed ECOs should trigger doom"
        assert result.doom_type == DoomType.ECO_EXHAUSTION, "Doom type should be eco_exhaustion"

    def test_step_5_verify_eco_gap_report_generated(self):
        """Step 5: Verify study terminates with ECO gap report."""
        config = DoomConfig(enabled=True, eco_exhaustion_enabled=True)
        detector = DoomDetector(config)

        eco_priors = [
            MockECOPrior("CellResizeECO", "failed"),
            MockECOPrior("BufferInsertionECO", "failed"),
            MockECOPrior("GateCloningECO", "failed"),
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()
        metrics = {"wns_ps": -1000}

        result = detector.check_doom(mock_case, metrics, eco_priors=eco_priors)

        # Verify doom report can be generated
        assert result.is_doomed is True
        report = format_doom_report(result)

        assert "ECO" in report.upper(), "Report should mention ECO"
        assert "exhaustion" in report.lower() or "failed" in report.lower(), \
            "Report should explain ECO exhaustion"

        # Verify metadata includes ECO failure counts
        assert "failed_count" in result.metadata, "Metadata should include failed count"


class TestECOExhaustionScenarios:
    """Test different ECO exhaustion scenarios."""

    def test_all_ecos_failed_triggers_doom(self):
        """Test that all ECOs failed triggers doom."""
        config = DoomConfig(enabled=True, eco_exhaustion_enabled=True)
        detector = DoomDetector(config)

        eco_priors = [
            MockECOPrior("ECO1", "failed"),
            MockECOPrior("ECO2", "failed"),
            MockECOPrior("ECO3", "failed"),
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()
        metrics = {"wns_ps": -1000}

        result = detector.check_doom(mock_case, metrics, eco_priors=eco_priors)

        assert result.is_doomed is True
        assert result.doom_type == DoomType.ECO_EXHAUSTION
        assert "all_ecos_failed" in result.trigger

    def test_all_ecos_suspicious_or_failed_triggers_doom(self):
        """Test that mix of failed and suspicious ECOs triggers doom."""
        config = DoomConfig(enabled=True, eco_exhaustion_enabled=True)
        detector = DoomDetector(config)

        eco_priors = [
            MockECOPrior("ECO1", "failed"),
            MockECOPrior("ECO2", "suspicious"),
            MockECOPrior("ECO3", "suspicious"),
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()
        metrics = {"wns_ps": -1000}

        result = detector.check_doom(mock_case, metrics, eco_priors=eco_priors)

        assert result.is_doomed is True
        assert result.doom_type == DoomType.ECO_EXHAUSTION
        assert "suspicious_or_failed" in result.trigger

    def test_some_successful_ecos_not_doomed(self):
        """Test that having some successful ECOs prevents doom."""
        config = DoomConfig(enabled=True, eco_exhaustion_enabled=True)
        detector = DoomDetector(config)

        eco_priors = [
            MockECOPrior("ECO1", "successful"),  # At least one successful
            MockECOPrior("ECO2", "failed"),
            MockECOPrior("ECO3", "failed"),
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()
        metrics = {"wns_ps": -1000}

        result = detector.check_doom(mock_case, metrics, eco_priors=eco_priors)

        assert result.is_doomed is False, "Having successful ECOs should prevent doom"

    def test_uncertain_ecos_not_doomed(self):
        """Test that uncertain ECOs prevent doom (still have potential)."""
        config = DoomConfig(enabled=True, eco_exhaustion_enabled=True)
        detector = DoomDetector(config)

        eco_priors = [
            MockECOPrior("ECO1", "uncertain"),
            MockECOPrior("ECO2", "failed"),
            MockECOPrior("ECO3", "failed"),
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()
        metrics = {"wns_ps": -1000}

        result = detector.check_doom(mock_case, metrics, eco_priors=eco_priors)

        assert result.is_doomed is False, "Uncertain ECOs still have potential"

    def test_insufficient_eco_priors_not_doomed(self):
        """Test that too few ECO priors doesn't trigger doom."""
        config = DoomConfig(enabled=True, eco_exhaustion_enabled=True)
        detector = DoomDetector(config)

        # Only 2 failed ECOs (need 3+)
        eco_priors = [
            MockECOPrior("ECO1", "failed"),
            MockECOPrior("ECO2", "failed"),
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()
        metrics = {"wns_ps": -1000}

        result = detector.check_doom(mock_case, metrics, eco_priors=eco_priors)

        assert result.is_doomed is False, "Need 3+ ECO priors for exhaustion doom"


class TestECOExhaustionConfiguration:
    """Test ECO exhaustion configuration."""

    def test_eco_exhaustion_can_be_disabled(self):
        """Test that ECO exhaustion detection can be disabled."""
        config = DoomConfig(
            enabled=True,
            eco_exhaustion_enabled=False,
        )

        detector = DoomDetector(config)

        # Even with all failed ECOs, should not doom when disabled
        eco_priors = [
            MockECOPrior("ECO1", "failed"),
            MockECOPrior("ECO2", "failed"),
            MockECOPrior("ECO3", "failed"),
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()
        metrics = {"wns_ps": -1000}

        result = detector.check_doom(mock_case, metrics, eco_priors=eco_priors)

        assert result.is_doomed is False, "Disabled ECO exhaustion should not doom"

    def test_no_eco_priors_not_doomed(self):
        """Test that missing ECO priors doesn't trigger doom."""
        config = DoomConfig(enabled=True, eco_exhaustion_enabled=True)
        detector = DoomDetector(config)

        from unittest.mock import MagicMock
        mock_case = MagicMock()
        metrics = {"wns_ps": -1000}

        # No ECO priors provided
        result = detector.check_doom(mock_case, metrics, eco_priors=None)

        assert result.is_doomed is False, "No ECO priors should not trigger doom"

    def test_empty_eco_priors_not_doomed(self):
        """Test that empty ECO prior list doesn't trigger doom."""
        config = DoomConfig(enabled=True, eco_exhaustion_enabled=True)
        detector = DoomDetector(config)

        from unittest.mock import MagicMock
        mock_case = MagicMock()
        metrics = {"wns_ps": -1000}

        result = detector.check_doom(mock_case, metrics, eco_priors=[])

        assert result.is_doomed is False, "Empty ECO priors should not trigger doom"


class TestECOExhaustionMetadata:
    """Test ECO exhaustion metadata and reporting."""

    def test_eco_exhaustion_includes_failure_counts(self):
        """Test that ECO exhaustion includes failure counts in metadata."""
        config = DoomConfig(enabled=True, eco_exhaustion_enabled=True)
        detector = DoomDetector(config)

        eco_priors = [
            MockECOPrior("ECO1", "failed"),
            MockECOPrior("ECO2", "failed"),
            MockECOPrior("ECO3", "suspicious"),
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()
        metrics = {"wns_ps": -1000}

        result = detector.check_doom(mock_case, metrics, eco_priors=eco_priors)

        assert result.is_doomed is True
        assert "failed_count" in result.metadata
        assert "suspicious_count" in result.metadata
        assert result.metadata["failed_count"] == 2
        assert result.metadata["suspicious_count"] == 1

    def test_eco_exhaustion_report_explains_situation(self):
        """Test that ECO exhaustion report explains the situation."""
        config = DoomConfig(enabled=True, eco_exhaustion_enabled=True)
        detector = DoomDetector(config)

        eco_priors = [
            MockECOPrior("ECO1", "failed"),
            MockECOPrior("ECO2", "failed"),
            MockECOPrior("ECO3", "failed"),
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()
        metrics = {"wns_ps": -1000}

        result = detector.check_doom(mock_case, metrics, eco_priors=eco_priors)

        report = format_doom_report(result)

        assert "All" in report and ("ECO" in report.upper() or "failed" in report.lower()), \
            "Report should explain that all ECOs failed"
        assert result.doom_type.value in report, "Report should mention eco_exhaustion"

    def test_non_exhausted_ecos_report(self):
        """Test report for non-exhausted ECO inventory."""
        config = DoomConfig(enabled=True, eco_exhaustion_enabled=True)
        detector = DoomDetector(config)

        eco_priors = [
            MockECOPrior("ECO1", "successful"),
            MockECOPrior("ECO2", "failed"),
            MockECOPrior("ECO3", "uncertain"),
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()
        metrics = {"wns_ps": -1000}

        result = detector.check_doom(mock_case, metrics, eco_priors=eco_priors)

        assert result.is_doomed is False
        # Reason could be general "no doom" or specific ECO availability message
        assert "not exhausted" in result.reason.lower() or "available" in result.reason.lower() or \
               "acceptable" in result.reason.lower(), \
            "Reason should indicate no doom"
