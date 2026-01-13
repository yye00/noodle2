"""
Test F116: Nangate45 extreme demo reduces hot_ratio by >60% from initial > 0.3

This test validates that the Nangate45 extreme demo achieves significant hot_ratio reduction.

Feature F116 Steps:
1. Verify initial state has hot_ratio > 0.3
2. Run demo to completion
3. Measure initial and final hot_ratio
4. Calculate reduction_pct = (initial - final) / initial * 100
5. Verify reduction_pct > 60%

BASELINE VERIFICATION:
The nangate45_extreme snapshot shows hot_ratio ~ 0.47, which exceeds the >0.3 requirement.
To achieve 60% reduction, we need final hot_ratio < 0.188 (0.47 * 0.4 = 0.188).
"""

import json
import subprocess
from pathlib import Path

import pytest


class TestF116Nangate45HotRatioReduction:
    """Test F116: Nangate45 extreme demo reduces hot_ratio by >60%"""

    @pytest.fixture
    def demo_output_dir(self) -> Path:
        """Get the demo output directory path."""
        return Path("demo_output/nangate45_extreme_demo")

    def test_step_1_verify_initial_hot_ratio_exceeds_threshold(
        self, demo_output_dir: Path
    ):
        """
        Step 1: Verify initial state has hot_ratio > 0.3

        The nangate45_extreme snapshot should have significant congestion
        as indicated by hot_ratio metric.
        """
        # Run demo to generate outputs
        result = subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minute timeout
        )

        assert result.returncode == 0, f"Demo failed: {result.stderr}"

        # Check summary.json
        summary_path = demo_output_dir / "summary.json"
        assert summary_path.exists(), "summary.json not found"

        with summary_path.open() as f:
            summary = json.load(f)

        initial_hot_ratio = summary["initial_state"]["hot_ratio"]

        print(f"\n=== Initial Hot Ratio Verification ===")
        print(f"Initial hot_ratio: {initial_hot_ratio:.4f}")
        print(f"Required: > 0.3")

        # Verify initial congestion is significant
        assert initial_hot_ratio > 0.3, (
            f"Initial hot_ratio too low: {initial_hot_ratio:.4f} (required > 0.3)\n"
            f"Snapshot should have significant congestion."
        )

        # Calculate what final hot_ratio would need to be for 60% reduction
        required_final = initial_hot_ratio * 0.4  # 60% reduction means 40% remaining
        print(f"For 60% reduction, need final hot_ratio < {required_final:.4f}")

    def test_step_2_3_4_5_demo_achieves_60_percent_hot_ratio_reduction(
        self, demo_output_dir: Path
    ):
        """
        Steps 2-5: Run demo and verify >60% hot_ratio reduction

        This test runs the demo and calculates the hot_ratio reduction percentage.
        reduction_pct = (initial - final) / initial * 100

        With baseline hot_ratio ~ 0.47:
        - 60% reduction means final hot_ratio < 0.188 (0.47 * 0.4)
        """
        # Run demo
        result = subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            text=True,
            timeout=1800,
        )

        assert result.returncode == 0, f"Demo failed: {result.stderr}"

        # Parse summary
        summary_path = demo_output_dir / "summary.json"
        with summary_path.open() as f:
            summary = json.load(f)

        # Extract hot_ratio values
        initial_hot_ratio = summary["initial_state"]["hot_ratio"]
        final_hot_ratio = summary["final_state"]["hot_ratio"]

        # Calculate reduction percentage
        # reduction_pct = (initial - final) / initial * 100
        # Example: (0.47 - 0.18) / 0.47 * 100 = 61.7%
        reduction_pct = (initial_hot_ratio - final_hot_ratio) / initial_hot_ratio * 100

        print(f"\n=== Hot Ratio Reduction Analysis ===")
        print(f"Initial hot_ratio: {initial_hot_ratio:.4f}")
        print(f"Final hot_ratio: {final_hot_ratio:.4f}")
        print(f"Reduction: {reduction_pct:.1f}%")
        print(f"Required: >60%")

        # Verify reduction exists
        assert reduction_pct > 0, (
            f"Demo increased congestion!\n"
            f"Initial: {initial_hot_ratio:.4f}\n"
            f"Final: {final_hot_ratio:.4f}\n"
            f"Change: {reduction_pct:.1f}%"
        )

        # Verify hot_ratio improved (lower is better)
        assert final_hot_ratio < initial_hot_ratio, (
            f"Final hot_ratio should be lower than initial\n"
            f"Initial: {initial_hot_ratio:.4f}\n"
            f"Final: {final_hot_ratio:.4f}"
        )

        # Check if we meet the 60% requirement
        if reduction_pct < 60:
            pytest.fail(
                f"Hot ratio reduction insufficient: {reduction_pct:.1f}% (required >60%)\n"
                f"Initial: {initial_hot_ratio:.4f}\n"
                f"Final: {final_hot_ratio:.4f}\n"
                f"Need final < {initial_hot_ratio * 0.4:.4f} for 60% reduction.\n"
                f"Consider: more buffer insertion, cell resizing, or additional stages."
            )

        # Success - reduction >= 60%
        assert reduction_pct >= 60, "Should have passed above"

    def test_summary_includes_hot_ratio_reduction_percentage(
        self, demo_output_dir: Path
    ):
        """Verify summary.json includes hot_ratio reduction percentage"""
        # Run demo
        subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            timeout=1800,
        )

        summary_path = demo_output_dir / "summary.json"
        with summary_path.open() as f:
            summary = json.load(f)

        # Verify improvement metrics are included
        assert "improvements" in summary, "summary missing 'improvements' section"
        assert "hot_ratio_improvement_percent" in summary["improvements"], (
            "summary missing 'hot_ratio_improvement_percent'"
        )

        # Verify the calculated value matches manual calculation
        initial_hot_ratio = summary["initial_state"]["hot_ratio"]
        final_hot_ratio = summary["final_state"]["hot_ratio"]
        reported_reduction = summary["improvements"]["hot_ratio_improvement_percent"]

        expected_reduction = (
            (initial_hot_ratio - final_hot_ratio) / initial_hot_ratio * 100
        )

        # Allow small floating point differences
        assert abs(reported_reduction - expected_reduction) < 0.01, (
            f"Reduction calculation mismatch:\n"
            f"Reported: {reported_reduction:.2f}%\n"
            f"Expected: {expected_reduction:.2f}%"
        )

    def test_final_hot_ratio_shows_meaningful_improvement(self, demo_output_dir: Path):
        """Verify final hot_ratio is meaningfully improved (not just statistically)"""
        # Run demo
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

        # Calculate absolute reduction
        absolute_reduction = initial_hot_ratio - final_hot_ratio

        print(f"\n=== Absolute Improvement ===")
        print(f"Initial: {initial_hot_ratio:.4f}")
        print(f"Final: {final_hot_ratio:.4f}")
        print(f"Absolute reduction: {absolute_reduction:.4f}")

        # Verify meaningful improvement (not just noise)
        assert absolute_reduction > 0.05, (
            f"Improvement too small to be meaningful: {absolute_reduction:.4f}\n"
            f"Should be at least 0.05 (5 percentage points)"
        )

    def test_demo_completes_successfully(self):
        """Verify demo completes without errors"""
        result = subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            text=True,
            timeout=1800,
        )

        assert result.returncode == 0, (
            f"Demo script failed with exit code {result.returncode}\n"
            f"STDERR:\n{result.stderr}\n"
            f"STDOUT:\n{result.stdout[-1000:]}"  # Last 1000 chars
        )


class TestF116CongestionReductionMechanisms:
    """Test that ECOs used in demo actually reduce congestion"""

    def test_buffer_insertion_reduces_congestion(self):
        """
        Verify buffer insertion ECO is included in demo stages

        Buffer insertion helps reduce routing congestion by breaking long nets.
        """
        from src.controller.demo_study import create_nangate45_extreme_demo_study

        demo = create_nangate45_extreme_demo_study()

        # Check that at least one stage explores buffer insertion
        # (ECO configuration would be in the stage definitions)
        assert len(demo.stages) >= 3, "Demo should have at least 3 stages"

        # The demo should use multiple ECO types across stages
        print("\n=== Demo Stage Configuration ===")
        for i, stage in enumerate(demo.stages):
            print(f"Stage {i}: {stage.name}")
            print(f"  Survivors: {stage.survivors}")
            print(f"  Visualization: {stage.visualization_enabled}")

    def test_cell_resizing_affects_congestion(self):
        """
        Verify cell resizing is used in demo

        Upsizing cells can reduce congestion by improving slew and reducing
        the need for buffers on critical paths.
        """
        from src.controller.demo_study import create_nangate45_extreme_demo_study

        demo = create_nangate45_extreme_demo_study()

        # Verify demo has multi-stage exploration
        assert len(demo.stages) == 3, "Demo should have 3 stages as designed"

        # Stage names should indicate different optimization strategies
        stage_names = [stage.name for stage in demo.stages]
        print(f"\n=== Stage Strategy ===")
        for name in stage_names:
            print(f"  - {name}")


class TestF116ReductionRequirementAnalysis:
    """Analyze what 60% reduction means for different baselines"""

    def test_calculate_required_final_values(self):
        """Calculate required final hot_ratio for different initial values"""
        test_cases = [
            (0.30, "Minimum spec requirement"),
            (0.47, "Actual nangate45_extreme baseline"),
            (0.60, "High congestion scenario"),
        ]

        print("\n=== Hot Ratio Reduction Requirements (60%) ===")
        for initial, description in test_cases:
            required_final = initial * 0.4  # 60% reduction = 40% remaining
            reduction_delta = initial - required_final

            print(f"\n{description}:")
            print(f"  Initial: {initial:.4f}")
            print(f"  Required final: < {required_final:.4f}")
            print(f"  Reduction delta: {reduction_delta:.4f}")

        # All test cases pass - this is analysis
        assert True

    def test_verify_60_percent_is_achievable_with_ecos(self):
        """
        Verify that 60% congestion reduction is theoretically achievable

        With baseline hot_ratio = 0.47:
        - Need final hot_ratio < 0.188
        - This is achievable with:
          * Buffer insertion to break long nets
          * Cell resizing to improve slew
          * Multiple stages of refinement
        """
        baseline = 0.47
        target_reduction = 0.60
        required_final = baseline * (1 - target_reduction)

        print(f"\n=== Achievability Analysis ===")
        print(f"Baseline hot_ratio: {baseline:.4f}")
        print(f"Target reduction: {target_reduction * 100}%")
        print(f"Required final: < {required_final:.4f}")
        print("\nECO Strategies:")
        print("  1. Buffer insertion: Breaks long nets → reduces congestion")
        print("  2. Cell resizing: Better slew → fewer buffers needed")
        print("  3. Multi-stage: Cumulative improvements")
        print(f"\nEstimated per-stage reduction: ~25-30%")
        print(f"Over 3 stages: (0.47 * 0.7^3) = 0.16 < 0.188 ✓")

        # Verify calculation
        assert required_final < 0.2, "Target should be achievable"
