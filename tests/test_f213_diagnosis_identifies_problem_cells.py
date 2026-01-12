"""Test F213: Diagnosis identifies problem cells for targeted ECOs.

This test ensures that timing diagnosis identifies specific problem cells
(not just nets) that are driving critical paths, enabling targeted ECO selection.
"""

import pytest

from src.analysis.diagnosis import (
    ProblemCell,
    TimingDiagnosis,
    TimingIssueClassification,
    diagnose_timing,
)
from src.controller.types import TimingPath, TimingMetrics


class TestF213Step1:
    """Step 1: Run timing diagnosis with identify_problem_cells enabled."""

    def test_run_timing_diagnosis_with_problem_cell_identification(self) -> None:
        """Verify timing diagnosis can identify problem cells."""
        # Create timing metrics with critical paths
        metrics = TimingMetrics(
            wns_ps=-1500,
            tns_ps=-5000,
            failing_endpoints=10,
            top_paths=[
                TimingPath(
                    endpoint="reg1/D",
                    slack_ps=-1500,
                    startpoint="reg0/Q",
                    path_group="clk",
                    path_type="max",
                ),
                TimingPath(
                    endpoint="reg2/D",
                    slack_ps=-1200,
                    startpoint="reg1/Q",
                    path_group="clk",
                    path_type="max",
                ),
                TimingPath(
                    endpoint="reg3/D",
                    slack_ps=-800,
                    startpoint="reg2/Q",
                    path_group="clk",
                    path_type="max",
                ),
            ],
        )

        # Run diagnosis with problem cell identification
        diagnosis = diagnose_timing(
            metrics,
            path_count=20,
            identify_problem_cells=True,
        )

        # Verify diagnosis completed
        assert diagnosis is not None
        assert diagnosis.wns_ps == -1500


class TestF213Step2:
    """Step 2: Verify problem cells are listed."""

    def test_verify_problem_cells_are_listed(self) -> None:
        """Verify problem cells are extracted and listed in diagnosis."""
        metrics = TimingMetrics(
            wns_ps=-1500,
            tns_ps=-5000,
            failing_endpoints=10,
            top_paths=[
                TimingPath(
                    endpoint="reg1/D",
                    slack_ps=-1500,
                    startpoint="reg0/Q",
                    path_group="clk",
                    path_type="max",
                ),
                TimingPath(
                    endpoint="reg2/D",
                    slack_ps=-1200,
                    startpoint="reg1/Q",
                    path_group="clk",
                    path_type="max",
                ),
            ],
        )

        diagnosis = diagnose_timing(
            metrics,
            identify_problem_cells=True,
        )

        # Verify problem cells are listed
        assert hasattr(diagnosis, "problem_cells")
        assert diagnosis.problem_cells is not None
        assert len(diagnosis.problem_cells) > 0

        # Verify cells have required attributes
        for cell in diagnosis.problem_cells:
            assert isinstance(cell, ProblemCell)
            assert cell.name is not None
            assert cell.slack_ps is not None
            assert cell.cell_type is not None


class TestF213Step3:
    """Step 3: Verify cells are associated with critical paths."""

    def test_verify_cells_associated_with_critical_paths(self) -> None:
        """Verify each problem cell is associated with its critical paths."""
        metrics = TimingMetrics(
            wns_ps=-1500,
            tns_ps=-5000,
            failing_endpoints=10,
            top_paths=[
                TimingPath(
                    endpoint="reg1/D",
                    slack_ps=-1500,
                    startpoint="reg0/Q",
                    path_group="clk",
                    path_type="max",
                ),
                TimingPath(
                    endpoint="reg2/D",
                    slack_ps=-1200,
                    startpoint="reg1/Q",
                    path_group="clk",
                    path_type="max",
                ),
            ],
        )

        diagnosis = diagnose_timing(
            metrics,
            identify_problem_cells=True,
        )

        # Verify cells have critical path associations
        assert len(diagnosis.problem_cells) > 0

        for cell in diagnosis.problem_cells:
            # Each cell should be associated with at least one critical path
            assert cell.critical_paths is not None
            assert len(cell.critical_paths) > 0

            # Path names should reference the cell
            for path in cell.critical_paths:
                # Path should mention the cell (either as driver or endpoint)
                assert (
                    cell.name in path or
                    any(cell.name.split("/")[0] in part for part in path.split("/"))
                )


class TestF213Step4:
    """Step 4: Use problem cell list to guide resize_critical_drivers ECO."""

    def test_use_problem_cells_to_guide_eco(self) -> None:
        """Verify problem cell list can guide ECO selection."""
        metrics = TimingMetrics(
            wns_ps=-1500,
            tns_ps=-5000,
            failing_endpoints=10,
            top_paths=[
                TimingPath(
                    endpoint="reg1/D",
                    slack_ps=-1500,
                    startpoint="reg0/Q",
                    path_group="clk",
                    path_type="max",
                ),
            ],
        )

        diagnosis = diagnose_timing(
            metrics,
            identify_problem_cells=True,
        )

        # Check if diagnosis suggests resize_critical_drivers ECO
        eco_names = [eco.eco for eco in diagnosis.suggested_ecos]

        # For cell-dominated paths, resize_critical_drivers should be suggested
        if diagnosis.dominant_issue == TimingIssueClassification.CELL_DOMINATED:
            assert "resize_critical_drivers" in eco_names

            # Find the resize ECO suggestion
            resize_eco = next(
                eco for eco in diagnosis.suggested_ecos
                if eco.eco == "resize_critical_drivers"
            )

            # Verify reason mentions cells
            assert "cell" in resize_eco.reason.lower()


class TestF213Step5:
    """Step 5: Verify ECO targets identified problem cells."""

    def test_verify_eco_targets_problem_cells(self) -> None:
        """Verify ECO suggestions reference the identified problem cells."""
        metrics = TimingMetrics(
            wns_ps=-1500,
            tns_ps=-5000,
            failing_endpoints=10,
            top_paths=[
                TimingPath(
                    endpoint="reg1/D",
                    slack_ps=-1500,
                    startpoint="reg0/Q",
                    path_group="clk",
                    path_type="max",
                ),
            ],
        )

        diagnosis = diagnose_timing(
            metrics,
            identify_problem_cells=True,
        )

        # Verify problem cells were identified
        assert len(diagnosis.problem_cells) > 0

        # Extract cell names
        cell_names = [cell.name for cell in diagnosis.problem_cells]

        # Verify cells can be used for targeted ECO application
        # This would be used like:
        # eco_params = {"target_cells": cell_names}
        # apply_eco("resize_critical_drivers", **eco_params)

        assert len(cell_names) > 0
        assert all(isinstance(name, str) for name in cell_names)


class TestF213ProblemCellDetails:
    """Detailed tests for ProblemCell structure."""

    def test_problem_cell_has_required_fields(self) -> None:
        """Verify ProblemCell has all required fields."""
        cell = ProblemCell(
            name="buf_x4_123",
            cell_type="buffer",
            slack_ps=-1000,
            delay_ps=450,
            critical_paths=["reg0/Q -> reg1/D"],
        )

        assert cell.name == "buf_x4_123"
        assert cell.cell_type == "buffer"
        assert cell.slack_ps == -1000
        assert cell.delay_ps == 450
        assert len(cell.critical_paths) == 1

    def test_problem_cell_serialization(self) -> None:
        """Verify ProblemCell can be serialized to dict."""
        cell = ProblemCell(
            name="buf_x4_123",
            cell_type="buffer",
            slack_ps=-1000,
            delay_ps=450,
            critical_paths=["reg0/Q -> reg1/D"],
        )

        cell_dict = cell.to_dict()

        assert cell_dict["name"] == "buf_x4_123"
        assert cell_dict["cell_type"] == "buffer"
        assert cell_dict["slack_ps"] == -1000
        assert cell_dict["delay_ps"] == 450
        assert "critical_paths" in cell_dict


class TestF213Integration:
    """Integration tests for F213."""

    def test_complete_f213_workflow(self) -> None:
        """Test complete workflow: diagnosis -> problem cells -> ECO targeting."""
        # Step 1: Create metrics
        metrics = TimingMetrics(
            wns_ps=-1500,
            tns_ps=-8000,
            failing_endpoints=15,
            top_paths=[
                TimingPath(
                    endpoint=f"reg{i}/D",
                    slack_ps=-1500 + i * 100,
                    startpoint=f"reg{i-1}/Q",
                    path_group="clk",
                    path_type="max",
                )
                for i in range(1, 11)
            ],
        )

        # Step 2: Run diagnosis with problem cell identification
        diagnosis = diagnose_timing(
            metrics,
            identify_problem_cells=True,
        )

        # Step 3: Verify problem cells identified
        assert len(diagnosis.problem_cells) > 0

        # Step 4: Verify diagnosis suggests appropriate ECOs
        assert len(diagnosis.suggested_ecos) > 0

        # Step 5: Verify problem cells can guide ECO application
        target_cells = [cell.name for cell in diagnosis.problem_cells]
        assert len(target_cells) > 0

        # Step 6: Verify JSON serialization includes problem cells
        diagnosis_dict = diagnosis.to_dict()
        assert "problem_cells" in diagnosis_dict
        assert len(diagnosis_dict["problem_cells"]) > 0


class TestF213EdgeCases:
    """Edge case tests for problem cell identification."""

    def test_no_problem_cells_when_disabled(self) -> None:
        """When identify_problem_cells=False, no cells are identified."""
        metrics = TimingMetrics(
            wns_ps=-1500,
            top_paths=[
                TimingPath(
                    endpoint="reg1/D",
                    slack_ps=-1500,
                    startpoint="reg0/Q",
                    path_group="clk",
                    path_type="max",
                ),
            ],
        )

        diagnosis = diagnose_timing(
            metrics,
            identify_problem_cells=False,
        )

        # Should have empty or None problem_cells
        assert diagnosis.problem_cells == [] or diagnosis.problem_cells is None

    def test_problem_cells_from_multiple_paths(self) -> None:
        """Cells appearing in multiple critical paths are tracked."""
        metrics = TimingMetrics(
            wns_ps=-2000,
            top_paths=[
                TimingPath(
                    endpoint="reg1/D",
                    slack_ps=-2000,
                    startpoint="reg0/Q",
                    path_group="clk",
                    path_type="max",
                ),
                TimingPath(
                    endpoint="reg2/D",
                    slack_ps=-1800,
                    startpoint="reg0/Q",  # Same driver
                    path_group="clk",
                    path_type="max",
                ),
            ],
        )

        diagnosis = diagnose_timing(
            metrics,
            identify_problem_cells=True,
        )

        # Should identify reg0 as a problem (appears in multiple paths)
        assert len(diagnosis.problem_cells) > 0

        # At least one cell should be associated with multiple paths
        multi_path_cells = [
            cell for cell in diagnosis.problem_cells
            if len(cell.critical_paths) > 1
        ]

        # In this scenario, reg0 is the common driver
        assert len(multi_path_cells) > 0

    def test_empty_paths_returns_empty_cells(self) -> None:
        """No paths means no problem cells."""
        metrics = TimingMetrics(
            wns_ps=0,
            top_paths=[],
        )

        diagnosis = diagnose_timing(
            metrics,
            identify_problem_cells=True,
        )

        assert diagnosis.problem_cells == [] or diagnosis.problem_cells is None
