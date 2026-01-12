"""Tests for Sky130 extreme demo script execution.

This module tests the end-to-end execution of the demo_sky130_extreme.sh
script which showcases fixing an extremely broken Sky130 design with
production-realistic Ibex design, complete audit trail, and publication-quality
visualizations.
"""

import json
import subprocess
from pathlib import Path

import pytest


class TestSky130ExtremeDemo:
    """Test the Sky130 extreme demo script."""

    @pytest.fixture
    def demo_output_dir(self) -> Path:
        """Get the demo output directory path."""
        return Path("demo_output/sky130_extreme_demo")

    def test_demo_script_exists(self) -> None:
        """Step 1: Verify demo script file exists and is executable."""
        script_path = Path("demo_sky130_extreme.sh")
        assert script_path.exists(), "Demo script not found"
        assert script_path.is_file(), "Demo script is not a file"
        # Check if executable
        assert script_path.stat().st_mode & 0o111, "Demo script is not executable"

    def test_demo_script_execution(self) -> None:
        """Step 1: Execute: ./demo_sky130_extreme.sh and verify success."""
        result = subprocess.run(
            ["bash", "demo_sky130_extreme.sh"],
            capture_output=True,
            text=True,
            timeout=2700,  # 45 minute timeout for Sky130
        )
        assert result.returncode == 0, f"Demo script failed: {result.stderr}"

    def test_demo_completes_within_time_limit(self) -> None:
        """Step 2: Verify demo completes within 45 minutes."""
        import time

        start = time.time()
        result = subprocess.run(
            ["bash", "demo_sky130_extreme.sh"],
            capture_output=True,
            text=True,
            timeout=2700,  # 45 minute timeout
        )
        duration = time.time() - start

        assert result.returncode == 0, "Demo failed"
        assert duration < 2700, f"Demo took too long: {duration:.1f}s > 2700s"

    def test_wns_improvement(self, demo_output_dir: Path) -> None:
        """Step 3: Verify WNS improvement > 50%."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_sky130_extreme.sh"],
            capture_output=True,
            timeout=2700,
        )

        summary_path = demo_output_dir / "summary.json"
        assert summary_path.exists(), "summary.json not found"

        with summary_path.open() as f:
            summary = json.load(f)

        initial_wns = summary["initial_state"]["wns_ps"]
        final_wns = summary["final_state"]["wns_ps"]
        improvement_percent = summary["improvements"]["wns_improvement_percent"]

        # Verify initial WNS is around -2200ps (Sky130 extreme range -2500 to -1900)
        assert -2500 <= initial_wns <= -1900, f"Initial WNS {initial_wns} not in Sky130 extreme range"

        # Verify final WNS is better than -1000ps
        assert final_wns > -1000, f"Final WNS {final_wns} not improved enough"

        # Verify improvement > 50%
        assert improvement_percent > 50, f"WNS improvement {improvement_percent}% < 50%"

    def test_hot_ratio_reduction(self, demo_output_dir: Path) -> None:
        """Step 4: Verify hot_ratio reduction > 60%."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_sky130_extreme.sh"],
            capture_output=True,
            timeout=2700,
        )

        summary_path = demo_output_dir / "summary.json"
        with summary_path.open() as f:
            summary = json.load(f)

        initial_hot_ratio = summary["initial_state"]["hot_ratio"]
        final_hot_ratio = summary["final_state"]["hot_ratio"]
        reduction_percent = summary["improvements"]["hot_ratio_improvement_percent"]

        # Verify initial hot_ratio > 0.32 (severe congestion)
        assert initial_hot_ratio > 0.30, f"Initial hot_ratio {initial_hot_ratio} not severe enough"

        # Verify final hot_ratio < 0.13 (acceptable congestion)
        assert final_hot_ratio < 0.13, f"Final hot_ratio {final_hot_ratio} still too high"

        # Verify reduction > 60%
        assert reduction_percent > 60, f"hot_ratio reduction {reduction_percent}% < 60%"

    def test_production_realistic_ibex_design(self, demo_output_dir: Path) -> None:
        """Step 5: Verify production-realistic Ibex design is used."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_sky130_extreme.sh"],
            capture_output=True,
            timeout=2700,
        )

        summary_path = demo_output_dir / "summary.json"
        with summary_path.open() as f:
            summary = json.load(f)

        # Verify design is Ibex RISC-V Core
        assert summary["design"] == "Ibex RISC-V Core", "Design is not Ibex"

        # Verify PDK is Sky130
        assert summary["pdk"] == "Sky130", "PDK is not Sky130"

        # Verify std_cell_library is sky130_fd_sc_hd
        assert summary["std_cell_library"] == "sky130_fd_sc_hd", "Wrong std_cell_library"

        # Verify production features flag
        assert summary["production_features"]["ibex_design_realistic"], "Ibex design not marked as realistic"

        # Verify before/diagnosis.json contains Ibex-specific information
        diagnosis_path = demo_output_dir / "before" / "diagnosis.json"
        assert diagnosis_path.exists(), "diagnosis.json not found"

        with diagnosis_path.open() as f:
            diagnosis = json.load(f)

        assert diagnosis["design"] == "Ibex RISC-V Core", "Diagnosis doesn't reference Ibex"
        # Check for Ibex-specific nets
        problem_nets = diagnosis["timing_diagnosis"]["problem_nets"]
        assert any("ibex" in net for net in problem_nets), "No Ibex-specific nets in diagnosis"

    def test_complete_audit_trail(self, demo_output_dir: Path) -> None:
        """Step 6: Verify complete audit trail is generated."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_sky130_extreme.sh"],
            capture_output=True,
            timeout=2700,
        )

        audit_trail_dir = demo_output_dir / "audit_trail"
        assert audit_trail_dir.exists(), "audit_trail directory not found"

        # Verify initial state audit entry
        initial_state_path = audit_trail_dir / "initial_state.json"
        assert initial_state_path.exists(), "initial_state.json not found in audit_trail"

        with initial_state_path.open() as f:
            initial_state = json.load(f)

        assert initial_state["audit_entry_type"] == "initial_design_state"
        assert initial_state["design"] == "Ibex RISC-V Core"
        assert initial_state["pdk"] == "Sky130A"

        # Verify stage completion audit entries
        for stage_id in [0, 1, 2]:
            stage_completion_path = audit_trail_dir / f"stage_{stage_id}_completion.json"
            assert stage_completion_path.exists(), f"stage_{stage_id}_completion.json not found"

            with stage_completion_path.open() as f:
                stage_completion = json.load(f)

            assert stage_completion["audit_entry_type"] == "stage_completion"
            assert stage_completion["stage_id"] == stage_id

        # Verify final summary audit entry
        final_summary_path = audit_trail_dir / "final_summary.json"
        assert final_summary_path.exists(), "final_summary.json not found"

        with final_summary_path.open() as f:
            final_summary = json.load(f)

        assert final_summary["audit_entry_type"] == "final_summary"
        assert final_summary["audit_complete"] is True

        # Verify summary.json confirms audit trail is complete
        summary_path = demo_output_dir / "summary.json"
        with summary_path.open() as f:
            summary = json.load(f)

        assert summary["production_features"]["audit_trail_complete"] is True

    def test_approval_gate_simulation(self, demo_output_dir: Path) -> None:
        """Step 7: Verify approval gate simulation (if configured)."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_sky130_extreme.sh"],
            capture_output=True,
            timeout=2700,
        )

        # Verify approval gate simulation results exist
        approval_gate_path = demo_output_dir / "audit_trail" / "approval_gate_simulation.json"
        assert approval_gate_path.exists(), "approval_gate_simulation.json not found"

        with approval_gate_path.open() as f:
            approval_gate = json.load(f)

        assert approval_gate["audit_entry_type"] == "approval_gate_simulation"
        assert approval_gate["gate_type"] == "manufacturing_readiness"
        assert approval_gate["design"] == "Ibex RISC-V Core"

        # Verify gate criteria are checked
        gate_criteria = approval_gate["gate_criteria"]
        assert gate_criteria["wns_improvement_target_percent"] == 50
        assert gate_criteria["wns_improvement_achieved"] > 50
        assert gate_criteria["hot_ratio_reduction_target_percent"] == 60
        assert gate_criteria["hot_ratio_reduction_achieved"] > 60

        # Verify gate decision is APPROVED
        assert approval_gate["gate_decision"] == "APPROVED", "Approval gate not passed"

        # Verify summary.json confirms approval gate was simulated
        summary_path = demo_output_dir / "summary.json"
        with summary_path.open() as f:
            summary = json.load(f)

        assert summary["production_features"]["approval_gate_simulated"] is True

    def test_publication_quality_visualizations(self, demo_output_dir: Path) -> None:
        """Step 8: Verify all comparison visualizations are publication-quality."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_sky130_extreme.sh"],
            capture_output=True,
            timeout=2700,
        )

        # Verify comparison directory exists
        comparison_dir = demo_output_dir / "comparison"
        assert comparison_dir.exists(), "comparison directory not found"

        # Verify publication-quality differential visualizations exist
        expected_heatmaps = ["placement_density", "routing_congestion", "rudy"]
        for heatmap in expected_heatmaps:
            diff_csv = comparison_dir / f"{heatmap}_diff.csv"
            diff_png = comparison_dir / f"{heatmap}_diff.png"

            assert diff_csv.exists(), f"{heatmap}_diff.csv not found"
            assert diff_png.exists(), f"{heatmap}_diff.png not found"

            # Verify the files contain "Publication-quality" marker
            with diff_csv.open() as f:
                csv_content = f.read()
            assert "Publication-quality" in csv_content or "publication" in csv_content.lower()

        # Verify summary.json confirms visualizations are publication-quality
        summary_path = demo_output_dir / "summary.json"
        with summary_path.open() as f:
            summary = json.load(f)

        assert summary["production_features"]["visualizations_publication_quality"] is True

    def test_all_required_artifacts_generated(self, demo_output_dir: Path) -> None:
        """Verify all required artifacts are generated."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_sky130_extreme.sh"],
            capture_output=True,
            timeout=2700,
        )

        # Verify main output directory exists
        assert demo_output_dir.exists(), "Demo output directory not found"

        # Verify before/ directory structure
        before_dir = demo_output_dir / "before"
        assert before_dir.exists(), "before/ directory not found"
        assert (before_dir / "metrics.json").exists(), "before/metrics.json not found"
        assert (before_dir / "diagnosis.json").exists(), "before/diagnosis.json not found"
        assert (before_dir / "heatmaps").exists(), "before/heatmaps/ directory not found"
        assert (before_dir / "overlays").exists(), "before/overlays/ directory not found"

        # Verify after/ directory structure
        after_dir = demo_output_dir / "after"
        assert after_dir.exists(), "after/ directory not found"
        assert (after_dir / "metrics.json").exists(), "after/metrics.json not found"
        assert (after_dir / "heatmaps").exists(), "after/heatmaps/ directory not found"
        assert (after_dir / "overlays").exists(), "after/overlays/ directory not found"

        # Verify comparison/ directory
        comparison_dir = demo_output_dir / "comparison"
        assert comparison_dir.exists(), "comparison/ directory not found"

        # Verify stages/ directory
        stages_dir = demo_output_dir / "stages"
        assert stages_dir.exists(), "stages/ directory not found"
        for stage_id in [0, 1, 2]:
            stage_dir = stages_dir / f"stage_{stage_id}"
            assert stage_dir.exists(), f"stage_{stage_id} directory not found"
            assert (stage_dir / "stage_summary.json").exists(), f"stage_{stage_id}/stage_summary.json not found"

        # Verify audit_trail/ directory
        audit_trail_dir = demo_output_dir / "audit_trail"
        assert audit_trail_dir.exists(), "audit_trail/ directory not found"

        # Verify summary.json
        assert (demo_output_dir / "summary.json").exists(), "summary.json not found"

    def test_demo_output_structure_complete(self, demo_output_dir: Path) -> None:
        """Verify complete output structure matches Sky130 requirements."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_sky130_extreme.sh"],
            capture_output=True,
            timeout=2700,
        )

        summary_path = demo_output_dir / "summary.json"
        with summary_path.open() as f:
            summary = json.load(f)

        # Verify all success criteria are met
        assert summary["success_criteria"]["wns_improvement_target_percent"] == 50
        assert summary["success_criteria"]["wns_improvement_achieved"] is True
        assert summary["success_criteria"]["hot_ratio_reduction_target_percent"] == 60
        assert summary["success_criteria"]["hot_ratio_reduction_achieved"] is True

        # Verify all production features are present
        assert summary["production_features"]["audit_trail_complete"] is True
        assert summary["production_features"]["approval_gate_simulated"] is True
        assert summary["production_features"]["visualizations_publication_quality"] is True
        assert summary["production_features"]["ibex_design_realistic"] is True

        # Verify Sky130-specific features
        assert summary["sky130_specific"]["pdk_variant"] == "sky130A"
        assert summary["sky130_specific"]["std_cell_library"] == "sky130_fd_sc_hd"
        assert summary["sky130_specific"]["open_source_pdk"] is True
        assert summary["sky130_specific"]["manufacturing_ready"] is True

    def test_create_sky130_extreme_demo_study(self) -> None:
        """Verify create_sky130_extreme_demo_study() function works."""
        from src.controller import create_sky130_extreme_demo_study

        demo = create_sky130_extreme_demo_study()

        # Verify study name
        assert demo.name == "sky130_extreme_demo"

        # Verify PDK
        assert demo.pdk == "Sky130"

        # Verify stages
        assert len(demo.stages) == 3
        assert demo.stages[0].name == "aggressive_exploration"
        assert demo.stages[1].name == "placement_refinement"
        assert demo.stages[2].name == "final_closure"

        # Verify metadata
        assert demo.metadata["design"] == "Ibex RISC-V Core"
        assert demo.metadata["design_type"] == "production_realistic"

    def test_extreme_demo_study_has_visualization_enabled(self) -> None:
        """Verify all stages have visualization enabled."""
        from src.controller import create_sky130_extreme_demo_study

        demo = create_sky130_extreme_demo_study()

        for stage in demo.stages:
            assert stage.visualization_enabled is True

    def test_extreme_demo_study_uses_sta_congestion_mode(self) -> None:
        """Verify all stages use STA_CONGESTION execution mode."""
        from src.controller import create_sky130_extreme_demo_study
        from src.controller.types import ExecutionMode

        demo = create_sky130_extreme_demo_study()

        for stage in demo.stages:
            assert stage.execution_mode == ExecutionMode.STA_CONGESTION

    def test_extreme_demo_study_validation_passes(self) -> None:
        """Verify study configuration passes validation."""
        from src.controller import create_sky130_extreme_demo_study

        demo = create_sky130_extreme_demo_study()

        # Should not raise ValidationError
        demo.validate()

    def test_sky130_metadata_includes_production_features(self) -> None:
        """Verify Sky130 metadata includes production features."""
        from src.controller import create_sky130_extreme_demo_study

        demo = create_sky130_extreme_demo_study()

        # Verify sky130_features list
        assert "sky130_features" in demo.metadata
        sky130_features = demo.metadata["sky130_features"]

        assert "production_realistic_ibex_design" in sky130_features
        assert "complete_audit_trail" in sky130_features
        assert "approval_gate_simulation" in sky130_features
        assert "publication_quality_visualizations" in sky130_features

        # Verify success criteria
        assert "success_criteria" in demo.metadata
        success_criteria = demo.metadata["success_criteria"]

        assert success_criteria["wns_improvement_percent"] == 50
        assert success_criteria["hot_ratio_reduction_percent"] == 60
        assert success_criteria["audit_trail_complete"] is True
        assert success_criteria["approval_gate_passed"] is True

    def test_sky130_staging_strategy_documented(self) -> None:
        """Verify Sky130 staging strategy is properly documented."""
        from src.controller import create_sky130_extreme_demo_study

        demo = create_sky130_extreme_demo_study()

        # Verify metadata includes purpose and expected behavior
        assert "purpose" in demo.metadata
        assert "production-realistic workflow" in demo.metadata["purpose"]

        assert "expected_behavior" in demo.metadata
        assert ">50%" in demo.metadata["expected_behavior"]

        # Verify description includes key features
        assert "production-realistic" in demo.description.lower()
        assert "ibex" in demo.description.lower()
        assert "audit trail" in demo.description.lower()

        # Verify tags include relevant labels
        assert "production-realistic" in demo.tags
        assert "ibex" in demo.tags
        assert "audit-trail" in demo.tags
