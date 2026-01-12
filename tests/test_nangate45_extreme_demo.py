"""Tests for Nangate45 extreme demo script execution.

This module tests the end-to-end execution of the demo_nangate45_extreme.sh
script which showcases fixing an extremely broken design.
"""

import json
import subprocess
from pathlib import Path

import pytest


class TestNangate45ExtremeDemo:
    """Test the Nangate45 extreme demo script."""

    @pytest.fixture
    def demo_output_dir(self) -> Path:
        """Get the demo output directory path."""
        return Path("demo_output/nangate45_extreme_demo")

    def test_demo_script_exists(self) -> None:
        """Step 1: Verify demo script file exists and is executable."""
        script_path = Path("demo_nangate45_extreme.sh")
        assert script_path.exists(), "Demo script not found"
        assert script_path.is_file(), "Demo script is not a file"
        # Check if executable
        assert script_path.stat().st_mode & 0o111, "Demo script is not executable"

    def test_demo_script_execution(self) -> None:
        """Step 1: Execute ./demo_nangate45_extreme.sh and verify success."""
        result = subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minute timeout
        )
        assert result.returncode == 0, f"Demo script failed: {result.stderr}"

    def test_demo_completes_within_time_limit(self) -> None:
        """Step 2: Verify demo completes within 30 minutes."""
        import time

        start = time.time()
        result = subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minute timeout
        )
        duration = time.time() - start

        assert result.returncode == 0, "Demo failed"
        assert duration < 1800, f"Demo took too long: {duration:.1f}s > 1800s"

    def test_wns_improvement(self, demo_output_dir: Path) -> None:
        """Step 3: Verify WNS improvement > 50% (from ~-2000ps to < -1000ps)."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            timeout=1800,
        )

        summary_path = demo_output_dir / "summary.json"
        assert summary_path.exists(), "summary.json not found"

        with summary_path.open() as f:
            summary = json.load(f)

        initial_wns = summary["initial_state"]["wns_ps"]
        final_wns = summary["final_state"]["wns_ps"]
        improvement_percent = summary["improvements"]["wns_improvement_percent"]

        # Verify initial WNS is around -2000ps (allow range -3000 to -2000)
        assert -3000 <= initial_wns <= -2000, f"Initial WNS {initial_wns} not in extreme range"

        # Verify final WNS is better than -1000ps
        assert final_wns > -1000, f"Final WNS {final_wns} not improved enough"

        # Verify improvement > 50%
        assert improvement_percent > 50, f"WNS improvement {improvement_percent}% < 50%"

    def test_hot_ratio_reduction(self, demo_output_dir: Path) -> None:
        """Step 4: Verify hot_ratio reduction > 60% (from > 0.3 to < 0.12)."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            timeout=1800,
        )

        summary_path = demo_output_dir / "summary.json"
        with summary_path.open() as f:
            summary = json.load(f)

        initial_hot_ratio = summary["initial_state"]["hot_ratio"]
        final_hot_ratio = summary["final_state"]["hot_ratio"]
        reduction_percent = summary["improvements"]["hot_ratio_improvement_percent"]

        # Verify initial hot_ratio > 0.3
        assert initial_hot_ratio > 0.3, f"Initial hot_ratio {initial_hot_ratio} not extreme"

        # Verify final hot_ratio < 0.12
        assert final_hot_ratio < 0.12, f"Final hot_ratio {final_hot_ratio} not improved enough"

        # Verify reduction > 60%
        assert reduction_percent > 60, f"hot_ratio reduction {reduction_percent}% < 60%"

    def test_all_required_artifacts_generated(self, demo_output_dir: Path) -> None:
        """Step 5: Verify all required artifacts are generated."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            timeout=1800,
        )

        # Check main directories
        required_dirs = ["before", "after", "comparison", "stages", "diagnosis"]
        for dir_name in required_dirs:
            dir_path = demo_output_dir / dir_name
            assert dir_path.exists(), f"Directory {dir_name}/ not found"
            assert dir_path.is_dir(), f"{dir_name}/ is not a directory"

        # Check summary.json
        assert (demo_output_dir / "summary.json").exists(), "summary.json not found"

    def test_before_after_directories_contain_heatmaps(
        self, demo_output_dir: Path
    ) -> None:
        """Step 6: Verify before/ and after/ directories contain complete heatmaps."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            timeout=1800,
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
        """Step 7: Verify comparison/ directory contains all differential visualizations."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            timeout=1800,
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
        """Step 8: Verify demo_output/nangate45_extreme_demo/summary.json exists."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            timeout=1800,
        )

        summary_path = demo_output_dir / "summary.json"
        assert summary_path.exists(), "summary.json not found"
        assert summary_path.is_file(), "summary.json is not a file"

        # Verify it's valid JSON
        with summary_path.open() as f:
            summary = json.load(f)

        # Verify required fields
        assert "demo_name" in summary
        assert "initial_state" in summary
        assert "final_state" in summary
        assert "improvements" in summary
        assert "success_criteria" in summary

    def test_demo_output_structure_complete(self, demo_output_dir: Path) -> None:
        """Verify complete demo output structure matches specification."""
        # Execute demo first
        subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            timeout=1800,
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

        # Check stages/ structure
        for stage_id in [0, 1, 2]:
            stage_dir = demo_output_dir / f"stages/stage_{stage_id}"
            assert stage_dir.exists(), f"Stage {stage_id} directory not found"
            assert (stage_dir / "stage_summary.json").exists()
            assert (stage_dir / "survivors").is_dir()

    def test_create_nangate45_extreme_demo_study(self) -> None:
        """Verify create_nangate45_extreme_demo_study() function exists and works."""
        from src.controller.demo_study import create_nangate45_extreme_demo_study

        demo = create_nangate45_extreme_demo_study()

        # Verify basic attributes
        assert demo.name == "nangate45_extreme_demo"
        assert demo.pdk == "Nangate45"
        assert demo.base_case_name == "nangate45_extreme"

        # Verify it has 3 stages
        assert len(demo.stages) == 3

        # Verify stage names
        assert demo.stages[0].name == "aggressive_exploration"
        assert demo.stages[1].name == "placement_refinement"
        assert demo.stages[2].name == "aggressive_closure"

    def test_extreme_demo_study_has_visualization_enabled(self) -> None:
        """Verify all stages have visualization enabled for demo purposes."""
        from src.controller.demo_study import create_nangate45_extreme_demo_study

        demo = create_nangate45_extreme_demo_study()

        for stage in demo.stages:
            assert stage.visualization_enabled is True, f"Stage {stage.name} has visualization disabled"

    def test_extreme_demo_study_uses_sta_congestion_mode(self) -> None:
        """Verify extreme demo uses STA_CONGESTION mode to track both metrics."""
        from src.controller.demo_study import create_nangate45_extreme_demo_study
        from src.controller.types import ExecutionMode

        demo = create_nangate45_extreme_demo_study()

        # All stages should use STA_CONGESTION mode for extreme demo
        for stage in demo.stages:
            assert stage.execution_mode == ExecutionMode.STA_CONGESTION, (
                f"Stage {stage.name} not using STA_CONGESTION mode"
            )

    def test_extreme_demo_study_validation_passes(self) -> None:
        """Verify extreme demo Study configuration passes validation."""
        from src.controller.demo_study import create_nangate45_extreme_demo_study

        demo = create_nangate45_extreme_demo_study()

        # Should not raise any exceptions
        demo.validate()
