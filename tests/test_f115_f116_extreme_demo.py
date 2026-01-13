"""Tests for F115 and F116: Nangate45 extreme demo achievement verification.

F115: Nangate45 extreme demo achieves >50% WNS improvement from initial < -1500ps
F116: Nangate45 extreme demo reduces hot_ratio by >60% from initial > 0.3

These tests verify that the extreme demo achieves the required improvements.
"""

import json
import subprocess
from pathlib import Path

import pytest


class TestF115WNSImprovement:
    """Test F115: Nangate45 extreme demo achieves >50% WNS improvement."""

    def test_step_1_verify_initial_wns_less_than_minus_1500ps(self):
        """Step 1: Verify initial state has WNS < -1500ps."""
        # Check snapshot metrics
        snapshot_path = Path("studies/nangate45_extreme_ibex/metrics.json")
        assert snapshot_path.exists(), f"Snapshot metrics not found at {snapshot_path}"

        with open(snapshot_path) as f:
            metrics = json.load(f)

        initial_wns = metrics.get("wns_ps", 0)
        assert initial_wns < -1500, f"Initial WNS ({initial_wns}ps) is not < -1500ps"

    def test_step_2_run_demo_nangate45_extreme_to_completion(self):
        """Step 2: Run demo_nangate45_extreme.sh to completion."""
        demo_script = Path("demo_nangate45_extreme.sh")
        assert demo_script.exists(), "Demo script demo_nangate45_extreme.sh not found"

        # Run the demo script
        result = subprocess.run(
            ["bash", str(demo_script)],
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout
        )

        assert result.returncode == 0, f"Demo script failed: {result.stderr}"

    def test_step_3_measure_initial_and_final_wns_from_summary(self):
        """Step 3: Measure initial and final WNS from summary.json."""
        summary_path = Path("demo_output/nangate45_extreme_demo/summary.json")
        assert summary_path.exists(), f"Summary file not found at {summary_path}"

        with open(summary_path) as f:
            summary = json.load(f)

        initial_wns = summary["initial_state"]["wns_ps"]
        final_wns = summary["final_state"]["wns_ps"]

        # Store for next step
        self.initial_wns = initial_wns
        self.final_wns = final_wns

        assert initial_wns < -1500, f"Initial WNS ({initial_wns}ps) is not < -1500ps"
        assert final_wns > initial_wns, f"Final WNS ({final_wns}ps) is not better than initial ({initial_wns}ps)"

    def test_step_4_calculate_improvement_percentage(self):
        """Step 4: Calculate improvement_pct = (initial - final) / abs(initial) * 100."""
        summary_path = Path("demo_output/nangate45_extreme_demo/summary.json")
        with open(summary_path) as f:
            summary = json.load(f)

        initial_wns = summary["initial_state"]["wns_ps"]
        final_wns = summary["final_state"]["wns_ps"]

        # Calculate improvement percentage
        # For WNS: improvement means going from more negative to less negative
        # e.g., -1800ps -> -800ps is a 55.5% improvement
        improvement_pct = (final_wns - initial_wns) / abs(initial_wns) * 100

        # Store for verification
        self.improvement_pct = improvement_pct

        assert improvement_pct > 0, f"Improvement percentage ({improvement_pct:.1f}%) is not positive"

    def test_step_5_verify_improvement_greater_than_50_percent(self):
        """Step 5: Verify improvement_pct > 50%."""
        summary_path = Path("demo_output/nangate45_extreme_demo/summary.json")
        with open(summary_path) as f:
            summary = json.load(f)

        initial_wns = summary["initial_state"]["wns_ps"]
        final_wns = summary["final_state"]["wns_ps"]

        # Calculate improvement percentage
        improvement_pct = (final_wns - initial_wns) / abs(initial_wns) * 100

        assert improvement_pct > 50, (
            f"WNS improvement ({improvement_pct:.1f}%) does not meet >50% target. "
            f"Initial: {initial_wns}ps, Final: {final_wns}ps"
        )


class TestF116HotRatioReduction:
    """Test F116: Nangate45 extreme demo reduces hot_ratio by >60%."""

    def test_step_1_verify_initial_hot_ratio_greater_than_0_3(self):
        """Step 1: Verify initial state has hot_ratio > 0.3."""
        # Check snapshot metrics
        snapshot_path = Path("studies/nangate45_extreme_ibex/metrics.json")
        assert snapshot_path.exists(), f"Snapshot metrics not found at {snapshot_path}"

        with open(snapshot_path) as f:
            metrics = json.load(f)

        initial_hot_ratio = metrics.get("hot_ratio", 0)
        assert initial_hot_ratio > 0.3, f"Initial hot_ratio ({initial_hot_ratio}) is not > 0.3"

    def test_step_2_run_demo_to_completion(self):
        """Step 2: Run demo to completion."""
        # This is the same as F115 step 2, but included for completeness
        summary_path = Path("demo_output/nangate45_extreme_demo/summary.json")
        assert summary_path.exists(), (
            "Demo must be run first. Run demo_nangate45_extreme.sh or "
            "ensure F115 step 2 has been executed."
        )

    def test_step_3_measure_initial_and_final_hot_ratio(self):
        """Step 3: Measure initial and final hot_ratio."""
        summary_path = Path("demo_output/nangate45_extreme_demo/summary.json")
        assert summary_path.exists(), f"Summary file not found at {summary_path}"

        with open(summary_path) as f:
            summary = json.load(f)

        initial_hot_ratio = summary["initial_state"]["hot_ratio"]
        final_hot_ratio = summary["final_state"]["hot_ratio"]

        assert initial_hot_ratio > 0.3, f"Initial hot_ratio ({initial_hot_ratio}) is not > 0.3"
        assert final_hot_ratio < initial_hot_ratio, (
            f"Final hot_ratio ({final_hot_ratio}) is not better than initial ({initial_hot_ratio})"
        )

    def test_step_4_calculate_reduction_percentage(self):
        """Step 4: Calculate reduction_pct = (initial - final) / initial * 100."""
        summary_path = Path("demo_output/nangate45_extreme_demo/summary.json")
        with open(summary_path) as f:
            summary = json.load(f)

        initial_hot_ratio = summary["initial_state"]["hot_ratio"]
        final_hot_ratio = summary["final_state"]["hot_ratio"]

        # Calculate reduction percentage
        reduction_pct = (initial_hot_ratio - final_hot_ratio) / initial_hot_ratio * 100

        assert reduction_pct > 0, f"Reduction percentage ({reduction_pct:.1f}%) is not positive"

    def test_step_5_verify_reduction_greater_than_60_percent(self):
        """Step 5: Verify reduction_pct > 60%."""
        summary_path = Path("demo_output/nangate45_extreme_demo/summary.json")
        with open(summary_path) as f:
            summary = json.load(f)

        initial_hot_ratio = summary["initial_state"]["hot_ratio"]
        final_hot_ratio = summary["final_state"]["hot_ratio"]

        # Calculate reduction percentage
        reduction_pct = (initial_hot_ratio - final_hot_ratio) / initial_hot_ratio * 100

        assert reduction_pct > 60, (
            f"hot_ratio reduction ({reduction_pct:.1f}%) does not meet >60% target. "
            f"Initial: {initial_hot_ratio}, Final: {final_hot_ratio}"
        )


class TestDemoIntegration:
    """Integration tests to verify demo produces valid results."""

    def test_demo_summary_exists_and_valid(self):
        """Verify demo summary.json exists and contains required fields."""
        summary_path = Path("demo_output/nangate45_extreme_demo/summary.json")

        # If summary doesn't exist, the demo hasn't been run yet
        # This is expected for fresh environments
        if not summary_path.exists():
            pytest.skip("Demo has not been run yet. Run demo_nangate45_extreme.sh first.")

        with open(summary_path) as f:
            summary = json.load(f)

        # Verify required fields exist
        assert "initial_state" in summary
        assert "final_state" in summary
        assert "wns_ps" in summary["initial_state"]
        assert "hot_ratio" in summary["initial_state"]
        assert "wns_ps" in summary["final_state"]
        assert "hot_ratio" in summary["final_state"]

    def test_demo_shows_actual_execution(self):
        """Verify demo summary indicates actual execution (no mocking)."""
        summary_path = Path("demo_output/nangate45_extreme_demo/summary.json")

        if not summary_path.exists():
            pytest.skip("Demo has not been run yet. Run demo_nangate45_extreme.sh first.")

        with open(summary_path) as f:
            summary = json.load(f)

        assert summary.get("execution_mode") == "ACTUAL_EXECUTION"
        assert summary.get("mocking") is False
        assert summary.get("placeholders") is False

    def test_snapshot_metrics_are_loaded(self):
        """Verify snapshot metrics are properly loaded from metrics.json."""
        snapshot_metrics_path = Path("studies/nangate45_extreme_ibex/metrics.json")
        assert snapshot_metrics_path.exists()

        with open(snapshot_metrics_path) as f:
            snapshot_metrics = json.load(f)

        # Verify snapshot has the expected extreme values
        assert snapshot_metrics.get("wns_ps", 0) < -1500
        assert snapshot_metrics.get("hot_ratio", 0) > 0.3
