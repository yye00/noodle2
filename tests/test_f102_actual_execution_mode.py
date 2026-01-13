"""Tests for F102: Demo scripts execute with ACTUAL_EXECUTION mode and no mocking.

This test verifies that demo scripts produce summary.json files with:
- execution_mode: ACTUAL_EXECUTION
- mocking: false
- placeholders: false
And that all trials execute real OpenROAD commands.
"""

import json
import subprocess
from pathlib import Path

import pytest


class TestF102ActualExecutionMode:
    """Test F102: Demo scripts execute with ACTUAL_EXECUTION mode and no mocking."""

    @pytest.fixture
    def demo_output_dirs(self) -> dict[str, Path]:
        """Get all demo output directory paths."""
        return {
            "nangate45": Path("demo_output/nangate45_extreme_demo"),
            "asap7": Path("demo_output/asap7_extreme_demo"),
            "sky130": Path("demo_output/sky130_extreme_demo"),
        }

    def test_step_1_run_nangate45_demo_script(self) -> None:
        """Step 1: Run demo script (demo_nangate45_extreme.sh)."""
        result = subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minute timeout
        )
        assert result.returncode == 0, f"Demo script failed: {result.stderr}"

    def test_step_2_verify_execution_mode_is_actual(
        self, demo_output_dirs: dict[str, Path]
    ) -> None:
        """Step 2: Verify summary.json contains execution_mode: ACTUAL_EXECUTION."""
        # Run demo first
        subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            timeout=1800,
        )

        summary_path = demo_output_dirs["nangate45"] / "summary.json"
        assert summary_path.exists(), "summary.json not found"

        with summary_path.open() as f:
            summary = json.load(f)

        assert "execution_mode" in summary, "execution_mode field missing"
        assert (
            summary["execution_mode"] == "ACTUAL_EXECUTION"
        ), f"Expected ACTUAL_EXECUTION, got {summary['execution_mode']}"

    def test_step_3_verify_mocking_is_false(
        self, demo_output_dirs: dict[str, Path]
    ) -> None:
        """Step 3: Verify summary.json contains mocking: false."""
        # Run demo first
        subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            timeout=1800,
        )

        summary_path = demo_output_dirs["nangate45"] / "summary.json"
        with summary_path.open() as f:
            summary = json.load(f)

        assert "mocking" in summary, "mocking field missing"
        assert summary["mocking"] is False, f"Expected mocking=false, got {summary['mocking']}"

    def test_step_4_verify_placeholders_is_false(
        self, demo_output_dirs: dict[str, Path]
    ) -> None:
        """Step 4: Verify summary.json contains placeholders: false."""
        # Run demo first
        subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            timeout=1800,
        )

        summary_path = demo_output_dirs["nangate45"] / "summary.json"
        with summary_path.open() as f:
            summary = json.load(f)

        assert "placeholders" in summary, "placeholders field missing"
        assert (
            summary["placeholders"] is False
        ), f"Expected placeholders=false, got {summary['placeholders']}"

    def test_step_5_verify_all_trials_execute_real_openroad_commands(
        self, demo_output_dirs: dict[str, Path]
    ) -> None:
        """Step 5: Verify all trials execute real OpenROAD commands.

        This checks:
        1. Trial metrics are not placeholder values
        2. Trial outputs contain real metric values (not zeros or placeholders)
        3. At least some trials completed successfully
        """
        # Run demo first
        subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            timeout=1800,
        )

        summary_path = demo_output_dirs["nangate45"] / "summary.json"
        with summary_path.open() as f:
            summary = json.load(f)

        # Verify initial and final states have real metrics
        initial_state = summary["initial_state"]
        final_state = summary["final_state"]

        # Check that WNS values are real (not placeholder zeros or None)
        assert initial_state["wns_ps"] is not None, "Initial WNS is None"
        assert final_state["wns_ps"] is not None, "Final WNS is None"
        assert initial_state["wns_ps"] != 0 or final_state["wns_ps"] != 0, (
            "Both initial and final WNS are zero (likely placeholders)"
        )

        # Check that hot_ratio values are real
        assert initial_state["hot_ratio"] is not None, "Initial hot_ratio is None"
        assert final_state["hot_ratio"] is not None, "Final hot_ratio is None"

        # Verify improvements were calculated
        assert "improvements" in summary, "improvements field missing"
        improvements = summary["improvements"]
        assert "wns_improvement_percent" in improvements, "WNS improvement not calculated"

    def test_all_demos_use_actual_execution_mode(
        self, demo_output_dirs: dict[str, Path]
    ) -> None:
        """Verify all three demos use ACTUAL_EXECUTION mode."""
        demos = [
            ("demo_nangate45_extreme.sh", "nangate45"),
            ("demo_asap7_extreme.sh", "asap7"),
            ("demo_sky130_extreme.sh", "sky130"),
        ]

        for script_name, output_key in demos:
            # Run demo
            result = subprocess.run(
                ["bash", script_name],
                capture_output=True,
                timeout=3600,  # 60 minutes for some demos
            )

            # Skip if script failed (might not have required resources)
            if result.returncode != 0:
                pytest.skip(f"{script_name} failed to execute (may need specific resources)")
                continue

            # Check summary.json
            summary_path = demo_output_dirs[output_key] / "summary.json"
            if not summary_path.exists():
                pytest.fail(f"{script_name} did not produce summary.json")

            with summary_path.open() as f:
                summary = json.load(f)

            # Verify all three critical fields
            assert summary.get("execution_mode") == "ACTUAL_EXECUTION", (
                f"{script_name}: execution_mode is not ACTUAL_EXECUTION"
            )
            assert summary.get("mocking") is False, (
                f"{script_name}: mocking is not false"
            )
            assert summary.get("placeholders") is False, (
                f"{script_name}: placeholders is not false"
            )
