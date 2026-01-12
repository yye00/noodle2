"""Tests for ASAP7 extreme demo script execution.

This module tests the end-to-end execution of the demo_asap7_extreme.sh
script which showcases fixing an extremely broken ASAP7 design with
ASAP7-specific workarounds and STA-first staging.
"""

import json
import subprocess
from pathlib import Path

import pytest


class TestASAP7ExtremeDemo:
    """Test the ASAP7 extreme demo script."""

    @pytest.fixture
    def demo_output_dir(self) -> Path:
        """Get the demo output directory path."""
        return Path("demo_output/asap7_extreme_demo")

    def test_demo_script_exists(self) -> None:
        """Step 1: Verify demo script file exists and is executable."""
        script_path = Path("demo_asap7_extreme.sh")
        assert script_path.exists(), "Demo script not found"
        assert script_path.is_file(), "Demo script is not a file"
        # Check if executable
        assert script_path.stat().st_mode & 0o111, "Demo script is not executable"

    def test_demo_script_execution(self) -> None:
        """Step 1: Execute ./demo_asap7_extreme.sh and verify success."""
        result = subprocess.run(
            ["bash", "demo_asap7_extreme.sh"],
            capture_output=True,
            text=True,
            timeout=3600,  # 60 minute timeout for ASAP7
        )
        assert result.returncode == 0, f"Demo script failed: {result.stderr}"

    def test_demo_completes_within_time_limit(self) -> None:
        """Step 2: Verify demo completes within 60 minutes."""
        import time

        start = time.time()
        result = subprocess.run(
            ["bash", "demo_asap7_extreme.sh"],
            capture_output=True,
            text=True,
            timeout=3600,  # 60 minute timeout
        )
        duration = time.time() - start

        assert result.returncode == 0, "Demo failed"
        assert duration < 3600, f"Demo took too long: {duration:.1f}s > 3600s"

    def test_wns_improvement(self, demo_output_dir: Path) -> None:
        """Step 3: Verify WNS improvement > 40% (ASAP7 target)."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_asap7_extreme.sh"],
            capture_output=True,
            timeout=3600,
        )

        summary_path = demo_output_dir / "summary.json"
        assert summary_path.exists(), "summary.json not found"

        with summary_path.open() as f:
            summary = json.load(f)

        initial_wns = summary["initial_state"]["wns_ps"]
        final_wns = summary["final_state"]["wns_ps"]
        improvement_percent = summary["improvements"]["wns_improvement_percent"]

        # Verify initial WNS is around -3000ps (ASAP7 extreme range -3500 to -2500)
        assert -3500 <= initial_wns <= -2500, f"Initial WNS {initial_wns} not in ASAP7 extreme range"

        # Verify final WNS is better than -2000ps (ASAP7 is harder to close)
        assert final_wns > -2000, f"Final WNS {final_wns} not improved enough for ASAP7"

        # Verify improvement > 40% (lower target for ASAP7 advanced node)
        assert improvement_percent > 40, f"WNS improvement {improvement_percent}% < 40%"

    def test_hot_ratio_reduction(self, demo_output_dir: Path) -> None:
        """Step 4: Verify hot_ratio reduction > 50% (from > 0.4 to < 0.15)."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_asap7_extreme.sh"],
            capture_output=True,
            timeout=3600,
        )

        summary_path = demo_output_dir / "summary.json"
        with summary_path.open() as f:
            summary = json.load(f)

        initial_hot_ratio = summary["initial_state"]["hot_ratio"]
        final_hot_ratio = summary["final_state"]["hot_ratio"]
        reduction_percent = summary["improvements"]["hot_ratio_improvement_percent"]

        # Verify initial hot_ratio > 0.4 (ASAP7 advanced node is more congested)
        assert initial_hot_ratio > 0.4, f"Initial hot_ratio {initial_hot_ratio} not extreme for ASAP7"

        # Verify final hot_ratio < 0.15 (ASAP7 has higher baseline congestion)
        assert final_hot_ratio < 0.15, f"Final hot_ratio {final_hot_ratio} not improved enough for ASAP7"

        # Verify reduction > 50%
        assert reduction_percent > 50, f"hot_ratio reduction {reduction_percent}% < 50%"

    def test_asap7_workarounds_applied(self, demo_output_dir: Path) -> None:
        """Step 5: Verify ASAP7 workarounds are automatically applied."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_asap7_extreme.sh"],
            capture_output=True,
            timeout=3600,
        )

        # Check diagnosis.json for ASAP7-specific workarounds
        diagnosis_path = demo_output_dir / "before/diagnosis.json"
        assert diagnosis_path.exists(), "before/diagnosis.json not found"

        with diagnosis_path.open() as f:
            diagnosis = json.load(f)

        # Verify ASAP7 workarounds are documented
        assert "asap7_workarounds_applied" in diagnosis, "ASAP7 workarounds not documented"
        workarounds = diagnosis["asap7_workarounds_applied"]

        # Check for key ASAP7 workarounds
        workaround_text = " ".join(workarounds)
        assert "routing_layer_constraints" in workaround_text or "metal2-metal9" in workaround_text
        assert "site_specification" in workaround_text or "asap7sc7p5t" in workaround_text
        assert "pin_placement_constraints" in workaround_text or "metal4" in workaround_text or "metal5" in workaround_text
        assert "utilization" in workaround_text or "0.55" in workaround_text

        # Verify PDK is set to ASAP7
        assert diagnosis.get("pdk") == "ASAP7", "PDK not set to ASAP7"

    def test_sta_first_staging_used(self, demo_output_dir: Path) -> None:
        """Step 6: Verify STA-first staging is used (ASAP7 best practice)."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_asap7_extreme.sh"],
            capture_output=True,
            timeout=3600,
        )

        summary_path = demo_output_dir / "summary.json"
        with summary_path.open() as f:
            summary = json.load(f)

        # Verify ASAP7-specific section documents STA-first staging
        assert "asap7_specific" in summary, "ASAP7-specific section not found"
        asap7_info = summary["asap7_specific"]

        staging = asap7_info.get("staging", "")
        assert "STA-first" in staging or "timing-priority" in staging, (
            f"STA-first staging not documented: {staging}"
        )

        # Verify execution mode is STA_CONGESTION (timing-priority)
        exec_mode = asap7_info.get("execution_mode", "")
        assert "STA_CONGESTION" in exec_mode, f"Execution mode not STA_CONGESTION: {exec_mode}"

    def test_all_required_artifacts_generated(self, demo_output_dir: Path) -> None:
        """Step 7: Verify all demo output artifacts are generated."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_asap7_extreme.sh"],
            capture_output=True,
            timeout=3600,
        )

        # Check main directories
        required_dirs = ["before", "after", "comparison", "stages", "diagnosis"]
        for dir_name in required_dirs:
            dir_path = demo_output_dir / dir_name
            assert dir_path.exists(), f"Directory {dir_name}/ not found"
            assert dir_path.is_dir(), f"{dir_name}/ is not a directory"

        # Check summary.json
        assert (demo_output_dir / "summary.json").exists(), "summary.json not found"

    def test_auto_diagnosis_guides_eco_selection(self, demo_output_dir: Path) -> None:
        """Step 8: Verify auto-diagnosis guides ECO selection."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_asap7_extreme.sh"],
            capture_output=True,
            timeout=3600,
        )

        # Check diagnosis.json has suggested ECOs
        diagnosis_path = demo_output_dir / "before/diagnosis.json"
        with diagnosis_path.open() as f:
            diagnosis = json.load(f)

        assert "suggested_ecos" in diagnosis, "suggested_ecos not found in diagnosis"
        suggested_ecos = diagnosis["suggested_ecos"]

        assert len(suggested_ecos) > 0, "No ECOs suggested by auto-diagnosis"

        # Verify ECO suggestions have required fields
        for eco in suggested_ecos:
            assert "eco_type" in eco, "ECO missing eco_type"
            assert "priority" in eco, "ECO missing priority"
            assert "reasoning" in eco, "ECO missing reasoning"

    def test_before_after_directories_contain_heatmaps(
        self, demo_output_dir: Path
    ) -> None:
        """Verify before/ and after/ directories contain complete heatmaps."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_asap7_extreme.sh"],
            capture_output=True,
            timeout=3600,
        )

        required_heatmaps = ["placement_density", "routing_congestion", "rudy"]

        for state_dir in ["before", "after"]:
            heatmap_dir = demo_output_dir / state_dir / "heatmaps"
            assert heatmap_dir.exists(), f"{state_dir}/heatmaps/ not found"

            for heatmap_name in required_heatmaps:
                # Check both CSV and PNG files
                csv_file = heatmap_dir / f"{heatmap_name}.csv"
                png_file = heatmap_dir / f"{heatmap_name}.png"

                assert csv_file.exists(), f"{state_dir}/heatmaps/{heatmap_name}.csv not found"
                assert png_file.exists(), f"{state_dir}/heatmaps/{heatmap_name}.png not found"

    def test_comparison_directory_contains_differentials(
        self, demo_output_dir: Path
    ) -> None:
        """Verify comparison/ directory contains all differential visualizations."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_asap7_extreme.sh"],
            capture_output=True,
            timeout=3600,
        )

        comparison_dir = demo_output_dir / "comparison"
        assert comparison_dir.exists(), "comparison/ directory not found"

        required_diffs = ["placement_density_diff", "routing_congestion_diff", "rudy_diff"]

        for diff_name in required_diffs:
            # Check both CSV and PNG files
            csv_file = comparison_dir / f"{diff_name}.csv"
            png_file = comparison_dir / f"{diff_name}.png"

            assert csv_file.exists(), f"comparison/{diff_name}.csv not found"
            assert png_file.exists(), f"comparison/{diff_name}.png not found"

    def test_summary_json_exists(self, demo_output_dir: Path) -> None:
        """Verify demo_output/asap7_extreme_demo/summary.json exists."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_asap7_extreme.sh"],
            capture_output=True,
            timeout=3600,
        )

        summary_path = demo_output_dir / "summary.json"
        assert summary_path.exists(), "summary.json not found"
        assert summary_path.is_file(), "summary.json is not a file"

        # Verify it's valid JSON
        with summary_path.open() as f:
            summary = json.load(f)

        # Verify required fields
        assert "demo_name" in summary
        assert "pdk" in summary
        assert summary["pdk"] == "ASAP7"
        assert "initial_state" in summary
        assert "final_state" in summary
        assert "improvements" in summary
        assert "success_criteria" in summary
        assert "asap7_specific" in summary

    def test_demo_output_structure_complete(self, demo_output_dir: Path) -> None:
        """Verify complete demo output structure matches specification."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_asap7_extreme.sh"],
            capture_output=True,
            timeout=3600,
        )

        # Check before/ structure
        assert (demo_output_dir / "before/metrics.json").exists()
        assert (demo_output_dir / "before/diagnosis.json").exists()
        assert (demo_output_dir / "before/heatmaps").is_dir()
        assert (demo_output_dir / "before/overlays").is_dir()

        # Check after/ structure
        assert (demo_output_dir / "after/metrics.json").exists()
        assert (demo_output_dir / "after/heatmaps").is_dir()
        assert (demo_output_dir / "after/overlays").is_dir()

        # Check stages/ structure (3 stages for ASAP7)
        for stage_id in [0, 1, 2]:
            stage_dir = demo_output_dir / f"stages/stage_{stage_id}"
            assert stage_dir.exists(), f"Stage {stage_id} directory not found"
            assert (stage_dir / "stage_summary.json").exists()
            assert (stage_dir / "survivors").is_dir()

    def test_create_asap7_extreme_demo_study(self) -> None:
        """Verify create_asap7_extreme_demo_study() function exists and works."""
        from src.controller.demo_study import create_asap7_extreme_demo_study

        demo = create_asap7_extreme_demo_study()

        # Verify basic attributes
        assert demo.name == "asap7_extreme_demo"
        assert demo.pdk == "ASAP7"
        assert demo.base_case_name == "asap7_extreme"

        # Verify it has 3 stages
        assert len(demo.stages) == 3

        # Verify stage names match ASAP7 STA-first approach
        assert demo.stages[0].name == "sta_exploration"
        assert demo.stages[1].name == "timing_refinement"
        assert demo.stages[2].name == "careful_closure"

    def test_extreme_demo_study_has_visualization_enabled(self) -> None:
        """Verify all stages have visualization enabled for demo purposes."""
        from src.controller.demo_study import create_asap7_extreme_demo_study

        demo = create_asap7_extreme_demo_study()

        for stage in demo.stages:
            assert stage.visualization_enabled is True, f"Stage {stage.name} has visualization disabled"

    def test_extreme_demo_study_uses_sta_congestion_mode(self) -> None:
        """Verify extreme demo uses STA_CONGESTION mode for ASAP7."""
        from src.controller.demo_study import create_asap7_extreme_demo_study
        from src.controller.types import ExecutionMode

        demo = create_asap7_extreme_demo_study()

        # All stages should use STA_CONGESTION mode (STA-first priority)
        for stage in demo.stages:
            assert stage.execution_mode == ExecutionMode.STA_CONGESTION, (
                f"Stage {stage.name} not using STA_CONGESTION mode"
            )

    def test_extreme_demo_study_validation_passes(self) -> None:
        """Verify extreme demo Study configuration passes validation."""
        from src.controller.demo_study import create_asap7_extreme_demo_study

        demo = create_asap7_extreme_demo_study()

        # Should not raise any exceptions
        demo.validate()

    def test_asap7_metadata_includes_workarounds(self) -> None:
        """Verify ASAP7 demo Study metadata documents workarounds."""
        from src.controller.demo_study import create_asap7_extreme_demo_study

        demo = create_asap7_extreme_demo_study()

        # Check metadata for ASAP7-specific documentation
        assert "asap7_workarounds" in demo.metadata, "ASAP7 workarounds not in metadata"

        workarounds = demo.metadata["asap7_workarounds"]
        assert isinstance(workarounds, list), "ASAP7 workarounds not a list"
        assert len(workarounds) > 0, "No ASAP7 workarounds documented"

        # Check for key workarounds
        workaround_text = " ".join(workarounds)
        assert "routing_layer_constraints" in workaround_text
        assert "site_specification" in workaround_text
        assert "pin_placement_constraints" in workaround_text
        assert "utilization" in workaround_text or "0.55" in workaround_text

    def test_asap7_staging_strategy_documented(self) -> None:
        """Verify ASAP7 staging strategy is documented in metadata."""
        from src.controller.demo_study import create_asap7_extreme_demo_study

        demo = create_asap7_extreme_demo_study()

        # Verify staging strategy is documented
        assert "staging_strategy" in demo.metadata, "Staging strategy not documented"

        staging = demo.metadata["staging_strategy"]
        assert "STA-first" in staging, f"STA-first not mentioned in staging strategy: {staging}"
