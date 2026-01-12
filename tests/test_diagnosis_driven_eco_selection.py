"""Tests for F209: Combined diagnosis drives ECO selection with priority queue."""

import pytest

from src.analysis.diagnosis import (
    IssueType,
    generate_complete_diagnosis,
)
from src.controller.diagnosis_driven_eco_selector import (
    DiagnosisDrivenECOSelector,
    ECOApplication,
    select_ecos_from_diagnosis,
)
from src.controller.types import CongestionMetrics, TimingMetrics, TimingPath


class TestDiagnosisDrivenECOSelectionF209:
    """
    Test suite for Feature F209: Combined diagnosis drives ECO selection.

    Steps from feature_list.json:
    1. Generate combined diagnosis with ECO priority queue
    2. Apply ECOs in priority order
    3. Verify highest priority ECO addresses primary issue
    4. Verify ECO selection respects diagnosis recommendations
    5. Track ECO effectiveness against diagnosis predictions
    """

    def test_step_1_generate_diagnosis_with_priority_queue(self) -> None:
        """Step 1: Generate combined diagnosis with ECO priority queue."""
        # Create metrics with timing issues (wire-dominated)
        timing_metrics = TimingMetrics(
            wns_ps=-2000,
            tns_ps=-40000,
            failing_endpoints=200,
            top_paths=[
                TimingPath(
                    slack_ps=-2000,
                    startpoint="input_A",
                    endpoint="reg_out",
                    path_group="clk",
                    path_type="max",
                ),
            ],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=300,
            hot_ratio=0.30,
            max_overflow=150,
            layer_metrics={"metal3": 150},
        )

        # Generate diagnosis
        diagnosis_report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        # Verify diagnosis summary has ECO priority queue
        assert diagnosis_report.diagnosis_summary is not None
        assert diagnosis_report.diagnosis_summary.eco_priority_queue is not None
        assert len(diagnosis_report.diagnosis_summary.eco_priority_queue) > 0

        # Verify ECOs are ordered by priority
        priorities = [
            eco.priority for eco in diagnosis_report.diagnosis_summary.eco_priority_queue
        ]
        assert priorities == sorted(priorities), "ECOs should be ordered by priority"

    def test_step_2_apply_ecos_in_priority_order(self) -> None:
        """Step 2: Apply ECOs in priority order."""
        # Generate diagnosis
        timing_metrics = TimingMetrics(
            wns_ps=-1500,
            tns_ps=-30000,
            failing_endpoints=150,
            top_paths=[
                TimingPath(
                    slack_ps=-1500,
                    startpoint="input_A",
                    endpoint="reg_out",
                    path_group="clk",
                ),
            ],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=400,
            hot_ratio=0.40,
            max_overflow=200,
            layer_metrics={"metal3": 200},
        )

        diagnosis_report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        # Create ECO selector
        selector = DiagnosisDrivenECOSelector(diagnosis_report)

        # Select ECOs in priority order
        applied_ecos: list[str] = []
        eco_applications: list[ECOApplication] = []

        # Apply first 3 ECOs in priority order
        for i in range(min(3, len(diagnosis_report.diagnosis_summary.eco_priority_queue))):  # type: ignore
            eco = selector.select_next_eco(applied_ecos)
            assert eco is not None, f"Should have ECO at position {i}"

            # Verify this is the correct priority
            assert eco.priority == i + 1, f"ECO {i} should have priority {i + 1}"

            # Record application
            eco_app = selector.create_eco_application_record(
                eco=eco,
                applied=True,
                success=True,
                effectiveness_notes=f"Applied ECO {eco.eco} at priority {eco.priority}",
            )
            eco_applications.append(eco_app)
            applied_ecos.append(eco.eco)

        # Verify we applied ECOs in priority order
        assert len(eco_applications) == 3
        assert [app.priority for app in eco_applications] == [1, 2, 3]

    def test_step_3_highest_priority_eco_addresses_primary_issue(self) -> None:
        """Step 3: Verify highest priority ECO addresses primary issue."""
        # Create timing-dominant scenario
        timing_metrics = TimingMetrics(
            wns_ps=-2500,  # Severe timing
            tns_ps=-50000,
            failing_endpoints=300,
            top_paths=[
                TimingPath(
                    slack_ps=-2500,
                    startpoint="input_A",
                    endpoint="reg_out",
                    path_group="clk",
                ),
            ],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=200,
            hot_ratio=0.20,  # Moderate congestion
            max_overflow=100,
            layer_metrics={"metal3": 100},
        )

        diagnosis_report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        # Primary issue should be timing due to severity
        assert diagnosis_report.diagnosis_summary is not None
        assert diagnosis_report.diagnosis_summary.primary_issue == IssueType.TIMING

        # Create selector
        selector = DiagnosisDrivenECOSelector(diagnosis_report)

        # Get highest priority ECO (priority=1)
        highest_priority_eco = selector.get_eco_by_priority(1)
        assert highest_priority_eco is not None, "Should have priority 1 ECO"

        # Verify it addresses the primary issue (timing)
        addresses_primary = selector.verify_eco_addresses_primary_issue(highest_priority_eco)
        assert addresses_primary, "Highest priority ECO should address primary issue"
        assert highest_priority_eco.addresses == "timing"

    def test_step_4_eco_selection_respects_diagnosis_recommendations(self) -> None:
        """Step 4: Verify ECO selection respects diagnosis recommendations."""
        # Create congestion-dominant scenario
        timing_metrics = TimingMetrics(
            wns_ps=-500,  # Minor timing issue
            tns_ps=-5000,
            failing_endpoints=25,
            top_paths=[
                TimingPath(
                    slack_ps=-500,
                    startpoint="input_A",
                    endpoint="reg_out",
                    path_group="clk",
                ),
            ],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=750,
            hot_ratio=0.75,  # Severe congestion
            max_overflow=500,
            layer_metrics={"metal3": 500},
        )

        diagnosis_report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        # Primary issue should be congestion
        assert diagnosis_report.diagnosis_summary is not None
        assert diagnosis_report.diagnosis_summary.primary_issue == IssueType.CONGESTION
        assert diagnosis_report.diagnosis_summary.recommended_strategy in [
            "congestion_first",
            "congestion_only",
        ]

        # Create selector
        selector = DiagnosisDrivenECOSelector(diagnosis_report)

        # Get ECOs for primary issue
        congestion_ecos = selector.get_ecos_for_issue("congestion")
        assert len(congestion_ecos) > 0, "Should have ECOs for congestion"

        # Verify that congestion ECOs appear early in priority queue
        # (within first half of queue)
        queue = diagnosis_report.diagnosis_summary.eco_priority_queue
        half_point = len(queue) // 2 if len(queue) > 0 else 1

        primary_ecos_in_top_half = sum(
            1 for eco in queue[:half_point] if eco.addresses == "congestion"
        )
        assert (
            primary_ecos_in_top_half > 0
        ), "Primary issue ECOs should appear early in queue"

    def test_step_5_track_eco_effectiveness(self) -> None:
        """Step 5: Track ECO effectiveness against diagnosis predictions."""
        # Generate diagnosis
        timing_metrics = TimingMetrics(
            wns_ps=-1800,
            tns_ps=-36000,
            failing_endpoints=180,
            top_paths=[
                TimingPath(
                    slack_ps=-1800,
                    startpoint="input_A",
                    endpoint="reg_out",
                    path_group="clk",
                ),
            ],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=350,
            hot_ratio=0.35,
            max_overflow=175,
            layer_metrics={"metal3": 175},
        )

        diagnosis_report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        selector = DiagnosisDrivenECOSelector(diagnosis_report)

        # Simulate applying ECOs and tracking effectiveness
        eco_applications: list[ECOApplication] = []

        # Apply first ECO - successful
        eco1 = selector.select_next_eco([])
        assert eco1 is not None
        app1 = selector.create_eco_application_record(
            eco=eco1,
            applied=True,
            success=True,
            effectiveness_notes="WNS improved by 300ps, as predicted for wire-dominated paths",
        )
        eco_applications.append(app1)

        # Apply second ECO - successful (if available)
        eco2 = selector.select_next_eco([eco1.eco])
        if eco2 is not None:
            app2 = selector.create_eco_application_record(
                eco=eco2,
                applied=True,
                success=True,
                effectiveness_notes="Reduced congestion in predicted region",
            )
            eco_applications.append(app2)

        # Apply third ECO - failed (if available)
        applied_so_far = [eco1.eco]
        if eco2 is not None:
            applied_so_far.append(eco2.eco)

        eco3 = selector.select_next_eco(applied_so_far)
        if eco3 is not None:
            app3 = selector.create_eco_application_record(
                eco=eco3,
                applied=True,
                success=False,
                effectiveness_notes="ECO failed to apply - incompatible with previous changes",
            )
            eco_applications.append(app3)

        # Generate selection report
        report = selector.generate_selection_report(eco_applications)

        # Verify report structure
        assert report.diagnosis_summary == diagnosis_report.diagnosis_summary
        assert len(report.eco_applications) >= 1  # At least first ECO applied
        assert report.eco_applications[0].success is True

        # If we have more ECOs, verify their tracking
        if len(report.eco_applications) >= 2:
            assert report.eco_applications[1].success is True
        if len(report.eco_applications) >= 3:
            assert report.eco_applications[2].success is False

        # Verify tracking includes effectiveness notes for first ECO
        assert "WNS improved" in report.eco_applications[0].effectiveness_notes

        # Verify selection notes summary includes key information
        assert "primary issue" in report.selection_notes.lower()

    def test_convenience_function_select_ecos_from_diagnosis(self) -> None:
        """Test convenience function for selecting ECOs from diagnosis."""
        timing_metrics = TimingMetrics(
            wns_ps=-1500,
            tns_ps=-30000,
            failing_endpoints=150,
            top_paths=[
                TimingPath(
                    slack_ps=-1500,
                    startpoint="input_A",
                    endpoint="reg_out",
                    path_group="clk",
                ),
            ],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=400,
            hot_ratio=0.40,
            max_overflow=200,
            layer_metrics={"metal3": 200},
        )

        diagnosis_report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        # Use convenience function
        selected_ecos = select_ecos_from_diagnosis(diagnosis_report, max_ecos=3)

        # Verify correct number of ECOs selected
        assert len(selected_ecos) <= 3
        assert len(selected_ecos) > 0

        # Verify they're in priority order
        priorities = [eco.priority for eco in selected_ecos]
        assert priorities == sorted(priorities)

    def test_selector_requires_diagnosis_summary(self) -> None:
        """Test that selector raises error if diagnosis has no summary."""
        from src.analysis.diagnosis import CompleteDiagnosisReport

        # Create incomplete diagnosis without summary
        incomplete_diagnosis = CompleteDiagnosisReport(
            timing_diagnosis=None,
            congestion_diagnosis=None,
            diagnosis_summary=None,
        )

        # Should raise ValueError
        with pytest.raises(ValueError, match="diagnosis_summary"):
            DiagnosisDrivenECOSelector(incomplete_diagnosis)

    def test_select_next_eco_returns_none_when_exhausted(self) -> None:
        """Test that select_next_eco returns None when all ECOs applied."""
        timing_metrics = TimingMetrics(
            wns_ps=-1000,
            tns_ps=-20000,
            failing_endpoints=100,
            top_paths=[
                TimingPath(
                    slack_ps=-1000,
                    startpoint="input_A",
                    endpoint="reg_out",
                    path_group="clk",
                ),
            ],
        )

        diagnosis_report = generate_complete_diagnosis(timing_metrics=timing_metrics)
        selector = DiagnosisDrivenECOSelector(diagnosis_report)

        # Get all ECO names from queue
        all_eco_names = [
            eco.eco for eco in diagnosis_report.diagnosis_summary.eco_priority_queue  # type: ignore
        ]

        # Mark all as applied
        next_eco = selector.select_next_eco(applied_ecos=all_eco_names)

        # Should return None
        assert next_eco is None

    def test_get_eco_by_priority_returns_none_for_missing_priority(self) -> None:
        """Test get_eco_by_priority returns None for non-existent priority."""
        timing_metrics = TimingMetrics(
            wns_ps=-1000,
            tns_ps=-20000,
            failing_endpoints=100,
            top_paths=[
                TimingPath(
                    slack_ps=-1000,
                    startpoint="input_A",
                    endpoint="reg_out",
                    path_group="clk",
                ),
            ],
        )

        diagnosis_report = generate_complete_diagnosis(timing_metrics=timing_metrics)
        selector = DiagnosisDrivenECOSelector(diagnosis_report)

        # Try to get ECO with priority 999 (should not exist)
        eco = selector.get_eco_by_priority(999)
        assert eco is None

    def test_eco_application_record_to_dict(self) -> None:
        """Test ECOApplication serialization to dictionary."""
        app = ECOApplication(
            eco_name="insert_buffers",
            priority=1,
            addresses="timing",
            applied=True,
            success=True,
            addresses_primary_issue=True,
            effectiveness_notes="Improved WNS by 250ps",
        )

        app_dict = app.to_dict()

        assert app_dict["eco_name"] == "insert_buffers"
        assert app_dict["priority"] == 1
        assert app_dict["addresses"] == "timing"
        assert app_dict["applied"] is True
        assert app_dict["success"] is True
        assert app_dict["addresses_primary_issue"] is True
        assert "250ps" in app_dict["effectiveness_notes"]

    def test_diagnosis_driven_eco_selection_to_dict(self) -> None:
        """Test DiagnosisDrivenECOSelection serialization to dictionary."""
        timing_metrics = TimingMetrics(
            wns_ps=-1500,
            tns_ps=-30000,
            failing_endpoints=150,
            top_paths=[
                TimingPath(
                    slack_ps=-1500,
                    startpoint="input_A",
                    endpoint="reg_out",
                    path_group="clk",
                ),
            ],
        )

        diagnosis_report = generate_complete_diagnosis(timing_metrics=timing_metrics)
        selector = DiagnosisDrivenECOSelector(diagnosis_report)

        # Create some application records
        eco1 = selector.select_next_eco([])
        assert eco1 is not None
        app1 = selector.create_eco_application_record(
            eco=eco1, applied=True, success=True, effectiveness_notes="Test"
        )

        report = selector.generate_selection_report([app1])
        report_dict = report.to_dict()

        # Verify structure
        assert "diagnosis_summary" in report_dict
        assert "eco_applications" in report_dict
        assert "selection_notes" in report_dict
        assert len(report_dict["eco_applications"]) == 1
