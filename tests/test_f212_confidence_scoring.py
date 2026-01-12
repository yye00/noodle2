"""Tests for F212: Timing diagnosis confidence scoring."""

import pytest

from src.analysis.diagnosis import diagnose_timing
from src.controller.types import TimingMetrics, TimingPath


class TestTimingDiagnosisConfidenceScoringF212:
    """
    Test suite for Feature F212: Confidence scoring for timing diagnosis.

    Steps from feature_list.json:
    1. Run timing diagnosis
    2. Verify confidence score is included (0.0 to 1.0)
    3. Verify high confidence (>0.8) for clear wire-dominated paths
    4. Verify lower confidence for mixed bottlenecks
    5. Use confidence to prioritize ECO selection
    """

    def test_step_1_run_timing_diagnosis(self) -> None:
        """Step 1: Run timing diagnosis."""
        # Create timing metrics with failing paths
        metrics = TimingMetrics(
            wns_ps=-2500,
            tns_ps=-15000,
            failing_endpoints=12,
            top_paths=[
                TimingPath(slack_ps=-2500, startpoint="CLK", endpoint="FF_1/D"),
                TimingPath(slack_ps=-2300, startpoint="CLK", endpoint="FF_2/D"),
                TimingPath(slack_ps=-2100, startpoint="CLK", endpoint="FF_3/D"),
            ],
        )

        # Run diagnosis
        diagnosis = diagnose_timing(metrics, path_count=3)

        # Verify diagnosis completed
        assert diagnosis is not None
        assert diagnosis.wns_ps == -2500

    def test_step_2_verify_confidence_score_included(self) -> None:
        """Step 2: Verify confidence score is included (0.0 to 1.0)."""
        metrics = TimingMetrics(
            wns_ps=-2000,
            tns_ps=-10000,
            failing_endpoints=8,
            top_paths=[
                TimingPath(slack_ps=-2000, startpoint="CLK", endpoint="FF_1/D"),
                TimingPath(slack_ps=-1800, startpoint="CLK", endpoint="FF_2/D"),
            ],
        )

        diagnosis = diagnose_timing(metrics, path_count=2)

        # Verify confidence field exists
        assert hasattr(diagnosis, "confidence")
        assert diagnosis.confidence is not None

        # Verify confidence is in valid range [0.0, 1.0]
        assert 0.0 <= diagnosis.confidence <= 1.0, \
            f"Confidence {diagnosis.confidence} is out of range [0.0, 1.0]"

    def test_step_3_verify_high_confidence_for_wire_dominated(self) -> None:
        """Step 3: Verify high confidence (>0.8) for clear wire-dominated paths."""
        # Create metrics with many wire-dominated paths (very negative slack)
        # Heuristic: abs(slack) > 1500 → wire-dominated
        wire_dominated_paths = [
            TimingPath(slack_ps=-2000 - i*100, startpoint="CLK", endpoint=f"FF_{i}/D")
            for i in range(10)
        ]

        metrics = TimingMetrics(
            wns_ps=-2000,
            tns_ps=-25000,
            failing_endpoints=10,
            top_paths=wire_dominated_paths,
        )

        # Use wire_delay_threshold=0.65 (default)
        # If 10/10 paths are wire-dominated, confidence should be 1.0 (100%)
        diagnosis = diagnose_timing(metrics, path_count=10, wire_delay_threshold=0.65)

        # Verify classification
        assert diagnosis.dominant_issue.value == "wire_dominated"

        # Verify high confidence (>0.8 as specified in requirements)
        assert diagnosis.confidence > 0.8, \
            f"Expected confidence > 0.8 for clear wire-dominated, got {diagnosis.confidence}"

        # For 100% wire-dominated paths, confidence should be very high
        assert diagnosis.confidence >= 0.9, \
            f"Expected confidence >= 0.9 for 100% wire-dominated paths, got {diagnosis.confidence}"

    def test_step_4_verify_lower_confidence_for_mixed_bottlenecks(self) -> None:
        """Step 4: Verify lower confidence for mixed bottlenecks."""
        # Create metrics with mixed paths (some wire, some cell dominated)
        # Mix of very negative slack (wire) and moderate negative slack (cell)
        mixed_paths = [
            TimingPath(slack_ps=-2000, startpoint="CLK", endpoint="FF_1/D"),  # Wire-dominated
            TimingPath(slack_ps=-1800, startpoint="CLK", endpoint="FF_2/D"),  # Wire-dominated
            TimingPath(slack_ps=-1600, startpoint="CLK", endpoint="FF_3/D"),  # Wire-dominated
            TimingPath(slack_ps=-1000, startpoint="CLK", endpoint="FF_4/D"),  # Cell-dominated
            TimingPath(slack_ps=-900, startpoint="CLK", endpoint="FF_5/D"),   # Cell-dominated
            TimingPath(slack_ps=-800, startpoint="CLK", endpoint="FF_6/D"),   # Cell-dominated
        ]

        metrics = TimingMetrics(
            wns_ps=-2000,
            tns_ps=-8100,
            failing_endpoints=6,
            top_paths=mixed_paths,
        )

        diagnosis = diagnose_timing(metrics, path_count=6, wire_delay_threshold=0.65)

        # Verify classification as MIXED (50% wire, 50% cell)
        assert diagnosis.dominant_issue.value == "mixed"

        # Verify lower confidence than wire-dominated case
        # For MIXED: confidence = 0.5 + abs(wire_ratio - 0.5)
        # With 50% wire ratio: confidence = 0.5 + 0.0 = 0.5
        assert diagnosis.confidence < 0.8, \
            f"Expected lower confidence for mixed bottlenecks, got {diagnosis.confidence}"

        # Should still be >= 0.5 for mixed classification
        assert diagnosis.confidence >= 0.5, \
            f"Expected confidence >= 0.5 for mixed, got {diagnosis.confidence}"

    def test_step_5_confidence_prioritizes_eco_selection(self) -> None:
        """Step 5: Use confidence to prioritize ECO selection."""
        # High confidence wire-dominated diagnosis
        wire_metrics = TimingMetrics(
            wns_ps=-2500,
            tns_ps=-20000,
            failing_endpoints=10,
            top_paths=[
                TimingPath(slack_ps=-2000 - i*100, startpoint="CLK", endpoint=f"FF_{i}/D")
                for i in range(10)
            ],
        )

        wire_diagnosis = diagnose_timing(wire_metrics, path_count=10)

        # Verify high confidence leads to specific ECO recommendations
        assert wire_diagnosis.confidence > 0.8
        assert len(wire_diagnosis.suggested_ecos) > 0

        # Wire-dominated should suggest buffer insertion
        eco_names = [eco.eco for eco in wire_diagnosis.suggested_ecos]
        assert "insert_buffers" in eco_names, \
            "High-confidence wire-dominated diagnosis should suggest buffer insertion"

        # Low confidence mixed diagnosis
        # Use balanced paths to get mixed classification
        mixed_metrics = TimingMetrics(
            wns_ps=-1800,
            tns_ps=-12000,
            failing_endpoints=6,
            top_paths=[
                TimingPath(slack_ps=-1800, startpoint="CLK", endpoint="FF_1/D"),  # Wire
                TimingPath(slack_ps=-1700, startpoint="CLK", endpoint="FF_2/D"),  # Wire
                TimingPath(slack_ps=-1600, startpoint="CLK", endpoint="FF_3/D"),  # Wire
                TimingPath(slack_ps=-1000, startpoint="CLK", endpoint="FF_4/D"),  # Cell
                TimingPath(slack_ps=-900, startpoint="CLK", endpoint="FF_5/D"),   # Cell
                TimingPath(slack_ps=-800, startpoint="CLK", endpoint="FF_6/D"),   # Cell
            ],
        )

        mixed_diagnosis = diagnose_timing(mixed_metrics, path_count=6)

        # Lower confidence should still provide ECO suggestions but with less certainty
        assert mixed_diagnosis.confidence < 0.8
        assert len(mixed_diagnosis.suggested_ecos) > 0

        # Mixed diagnosis (50% wire, 50% cell) should have different ECO priorities
        # Implementation may suggest both buffer and cell optimization
        assert mixed_diagnosis.dominant_issue.value == "mixed"

    # Additional confidence scoring tests

    def test_confidence_calculation_for_wire_dominated(self) -> None:
        """Verify confidence calculation for wire-dominated paths."""
        # 8 out of 10 paths wire-dominated
        paths = (
            [TimingPath(slack_ps=-2000, startpoint="CLK", endpoint=f"FF_{i}/D") for i in range(8)] +
            [TimingPath(slack_ps=-1000, startpoint="CLK", endpoint=f"FF_{i}/D") for i in range(8, 10)]
        )

        metrics = TimingMetrics(
            wns_ps=-2000,
            tns_ps=-18000,
            failing_endpoints=10,
            top_paths=paths,
        )

        diagnosis = diagnose_timing(metrics, path_count=10, wire_delay_threshold=0.65)

        # Wire ratio = 8/10 = 0.8 >= 0.65 (threshold)
        # Should be classified as wire-dominated
        assert diagnosis.dominant_issue.value == "wire_dominated"

        # Confidence for wire-dominated = wire_ratio = 0.8
        assert diagnosis.confidence == 0.8

    def test_confidence_calculation_for_cell_dominated(self) -> None:
        """Verify confidence calculation for cell-dominated paths."""
        # 2 out of 10 paths wire-dominated (8 cell-dominated)
        paths = (
            [TimingPath(slack_ps=-2000, startpoint="CLK", endpoint=f"FF_{i}/D") for i in range(2)] +
            [TimingPath(slack_ps=-1000, startpoint="CLK", endpoint=f"FF_{i}/D") for i in range(2, 10)]
        )

        metrics = TimingMetrics(
            wns_ps=-2000,
            tns_ps=-12000,
            failing_endpoints=10,
            top_paths=paths,
        )

        diagnosis = diagnose_timing(metrics, path_count=10, wire_delay_threshold=0.65)

        # Wire ratio = 2/10 = 0.2 <= (1 - 0.65) = 0.35
        # Should be classified as cell-dominated
        assert diagnosis.dominant_issue.value == "cell_dominated"

        # Confidence for cell-dominated = 1.0 - wire_ratio = 1.0 - 0.2 = 0.8
        assert diagnosis.confidence == 0.8

    def test_confidence_calculation_for_mixed(self) -> None:
        """Verify confidence calculation for mixed bottlenecks."""
        # 5 out of 10 paths wire-dominated (exactly balanced)
        paths = (
            [TimingPath(slack_ps=-2000, startpoint="CLK", endpoint=f"FF_{i}/D") for i in range(5)] +
            [TimingPath(slack_ps=-1000, startpoint="CLK", endpoint=f"FF_{i}/D") for i in range(5, 10)]
        )

        metrics = TimingMetrics(
            wns_ps=-2000,
            tns_ps=-15000,
            failing_endpoints=10,
            top_paths=paths,
        )

        diagnosis = diagnose_timing(metrics, path_count=10, wire_delay_threshold=0.65)

        # Wire ratio = 5/10 = 0.5
        # Not wire-dominated (0.5 < 0.65)
        # Not cell-dominated (0.5 > 0.35)
        # Should be classified as mixed
        assert diagnosis.dominant_issue.value == "mixed"

        # Confidence for mixed = 0.5 + abs(0.5 - 0.5) = 0.5
        assert diagnosis.confidence == 0.5

    def test_confidence_range_for_mixed_with_slight_bias(self) -> None:
        """Verify confidence range for mixed classification with slight bias."""
        # 6 out of 10 paths wire-dominated (slightly wire-biased)
        paths = (
            [TimingPath(slack_ps=-2000, startpoint="CLK", endpoint=f"FF_{i}/D") for i in range(6)] +
            [TimingPath(slack_ps=-1000, startpoint="CLK", endpoint=f"FF_{i}/D") for i in range(6, 10)]
        )

        metrics = TimingMetrics(
            wns_ps=-2000,
            tns_ps=-16000,
            failing_endpoints=10,
            top_paths=paths,
        )

        diagnosis = diagnose_timing(metrics, path_count=10, wire_delay_threshold=0.65)

        # Wire ratio = 6/10 = 0.6
        # 0.6 < 0.65 (wire threshold) and 0.6 > 0.35 (cell threshold)
        # Should be mixed
        assert diagnosis.dominant_issue.value == "mixed"

        # Confidence = 0.5 + abs(0.6 - 0.5) = 0.5 + 0.1 = 0.6
        assert diagnosis.confidence == pytest.approx(0.6, abs=0.01)

    def test_zero_confidence_for_no_paths(self) -> None:
        """Verify confidence is 0.0 when no paths can be analyzed."""
        metrics = TimingMetrics(
            wns_ps=-1000,
            tns_ps=-5000,
            failing_endpoints=3,
            top_paths=[],  # No paths to analyze
        )

        diagnosis = diagnose_timing(metrics, path_count=20)

        # Should be classified as UNKNOWN
        assert diagnosis.dominant_issue.value == "unknown"

        # Confidence should be 0.0 when no data
        assert diagnosis.confidence == 0.0

    def test_confidence_in_serialized_output(self) -> None:
        """Verify confidence is included in serialized JSON output."""
        metrics = TimingMetrics(
            wns_ps=-2000,
            tns_ps=-12000,
            failing_endpoints=8,
            top_paths=[
                TimingPath(slack_ps=-2000, startpoint="CLK", endpoint="FF_1/D"),
                TimingPath(slack_ps=-1800, startpoint="CLK", endpoint="FF_2/D"),
            ],
        )

        diagnosis = diagnose_timing(metrics, path_count=2)
        diagnosis_dict = diagnosis.to_dict()

        # Verify confidence is in serialized output
        assert "confidence" in diagnosis_dict
        assert isinstance(diagnosis_dict["confidence"], float)
        assert 0.0 <= diagnosis_dict["confidence"] <= 1.0
