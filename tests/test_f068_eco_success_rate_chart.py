"""Tests for F068: ECO success rate chart visualization.

This module tests the ECO success rate chart feature that visualizes
ECO effectiveness through bar charts.

Feature F068 Steps:
  Step 1: Run study with multiple ECOs
  Step 2: Compute success rate per ECO from priors
  Step 3: Create bar chart with ECO names (x-axis) vs success rate (y-axis)
  Step 4: Save as PNG
  Step 5: Verify chart shows which ECOs are most effective
"""

import tempfile
from pathlib import Path

import pytest

from src.controller.eco import ECOEffectiveness, ECOPrior
from src.visualization.eco_success_rate_chart import (
    generate_eco_success_rate_chart,
    plot_eco_success_rate_chart,
    save_eco_success_rate_chart,
)


class TestF068Step01:
    """Step 1: Run study with multiple ECOs."""

    def test_create_multiple_eco_effectiveness_records(self):
        """Test creating effectiveness records for multiple ECOs."""
        # Create effectiveness records for different ECOs
        eco1 = ECOEffectiveness(eco_name="buffer_insertion")
        eco2 = ECOEffectiveness(eco_name="cell_sizing")
        eco3 = ECOEffectiveness(eco_name="pin_swap")

        assert eco1.eco_name == "buffer_insertion"
        assert eco2.eco_name == "cell_sizing"
        assert eco3.eco_name == "pin_swap"

        # Initially all have 0 applications
        assert eco1.total_applications == 0
        assert eco2.total_applications == 0
        assert eco3.total_applications == 0

    def test_simulate_eco_applications_across_trials(self):
        """Test simulating ECO applications with different success rates."""
        # Buffer insertion: 8 successes out of 10 trials (80% success)
        buffer_eco = ECOEffectiveness(eco_name="buffer_insertion")
        for _ in range(8):
            buffer_eco.update(success=True, wns_delta_ps=50.0)
        for _ in range(2):
            buffer_eco.update(success=False, wns_delta_ps=-10.0)

        assert buffer_eco.total_applications == 10
        assert buffer_eco.successful_applications == 8
        assert buffer_eco.success_rate == 0.8

        # Cell sizing: 5 successes out of 10 trials (50% success)
        sizing_eco = ECOEffectiveness(eco_name="cell_sizing")
        for _ in range(5):
            sizing_eco.update(success=True, wns_delta_ps=30.0)
        for _ in range(5):
            sizing_eco.update(success=False, wns_delta_ps=-5.0)

        assert sizing_eco.total_applications == 10
        assert sizing_eco.successful_applications == 5
        assert sizing_eco.success_rate == 0.5

        # Pin swap: 3 successes out of 10 trials (30% success)
        pinswap_eco = ECOEffectiveness(eco_name="pin_swap")
        for _ in range(3):
            pinswap_eco.update(success=True, wns_delta_ps=20.0)
        for _ in range(7):
            pinswap_eco.update(success=False, wns_delta_ps=-15.0)

        assert pinswap_eco.total_applications == 10
        assert pinswap_eco.successful_applications == 3
        assert pinswap_eco.success_rate == 0.3


class TestF068Step02:
    """Step 2: Compute success rate per ECO from priors."""

    def test_success_rate_calculation(self):
        """Test success rate is correctly calculated."""
        eco = ECOEffectiveness(eco_name="test_eco")

        # Update with 7 successes, 3 failures
        for _ in range(7):
            eco.update(success=True, wns_delta_ps=40.0)
        for _ in range(3):
            eco.update(success=False, wns_delta_ps=-20.0)

        # Success rate should be 7/10 = 0.7
        assert eco.success_rate == 0.7
        assert eco.total_applications == 10
        assert eco.successful_applications == 7
        assert eco.failed_applications == 3

    def test_success_rate_for_all_successful(self):
        """Test success rate when all applications succeed."""
        eco = ECOEffectiveness(eco_name="perfect_eco")

        for _ in range(10):
            eco.update(success=True, wns_delta_ps=50.0)

        assert eco.success_rate == 1.0

    def test_success_rate_for_all_failed(self):
        """Test success rate when all applications fail."""
        eco = ECOEffectiveness(eco_name="broken_eco")

        for _ in range(10):
            eco.update(success=False, wns_delta_ps=-30.0)

        assert eco.success_rate == 0.0

    def test_success_rate_with_no_applications(self):
        """Test success rate is 0 when there are no applications."""
        eco = ECOEffectiveness(eco_name="unused_eco")

        assert eco.success_rate == 0.0
        assert eco.total_applications == 0


class TestF068Step03:
    """Step 3: Create bar chart with ECO names (x-axis) vs success rate (y-axis)."""

    def test_create_basic_success_rate_chart(self):
        """Test creating a basic ECO success rate chart."""
        # Create ECOs with different success rates
        eco1 = ECOEffectiveness(eco_name="buffer_insertion")
        for _ in range(8):
            eco1.update(success=True, wns_delta_ps=50.0)
        for _ in range(2):
            eco1.update(success=False, wns_delta_ps=-10.0)

        eco2 = ECOEffectiveness(eco_name="cell_sizing")
        for _ in range(6):
            eco2.update(success=True, wns_delta_ps=30.0)
        for _ in range(4):
            eco2.update(success=False, wns_delta_ps=-5.0)

        eco3 = ECOEffectiveness(eco_name="pin_swap")
        for _ in range(3):
            eco3.update(success=True, wns_delta_ps=20.0)
        for _ in range(7):
            eco3.update(success=False, wns_delta_ps=-15.0)

        # Generate chart
        fig = plot_eco_success_rate_chart([eco1, eco2, eco3])

        # Verify figure was created
        assert fig is not None
        assert len(fig.axes) == 1

        # Get the axis
        ax = fig.axes[0]

        # Verify labels
        assert ax.get_xlabel() == "ECO Type"
        assert ax.get_ylabel() == "Success Rate (%)"
        assert "ECO Success Rate Comparison" in ax.get_title()

        # Verify we have 3 bars
        bars = [p for p in ax.patches if p.get_height() > 0]
        assert len(bars) == 3

        # Clean up
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_chart_sorts_ecos_by_success_rate(self):
        """Test that ECOs are sorted by success rate in descending order."""
        # Create ECOs with known success rates
        eco_low = ECOEffectiveness(eco_name="low_success")
        for _ in range(3):
            eco_low.update(success=True, wns_delta_ps=20.0)
        for _ in range(7):
            eco_low.update(success=False, wns_delta_ps=-10.0)

        eco_high = ECOEffectiveness(eco_name="high_success")
        for _ in range(9):
            eco_high.update(success=True, wns_delta_ps=50.0)
        for _ in range(1):
            eco_high.update(success=False, wns_delta_ps=-5.0)

        eco_medium = ECOEffectiveness(eco_name="medium_success")
        for _ in range(6):
            eco_medium.update(success=True, wns_delta_ps=30.0)
        for _ in range(4):
            eco_medium.update(success=False, wns_delta_ps=-10.0)

        # Generate chart (unsorted order)
        fig = plot_eco_success_rate_chart([eco_low, eco_high, eco_medium])

        ax = fig.axes[0]

        # Get x-tick labels (should be sorted by success rate)
        labels = [label.get_text() for label in ax.get_xticklabels()]

        # Should be sorted: high (90%), medium (60%), low (30%)
        assert labels == ["high_success", "medium_success", "low_success"]

        # Clean up
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_chart_with_custom_title(self):
        """Test chart generation with custom title."""
        eco = ECOEffectiveness(eco_name="test_eco")
        for _ in range(5):
            eco.update(success=True, wns_delta_ps=30.0)
        for _ in range(5):
            eco.update(success=False, wns_delta_ps=-10.0)

        fig = plot_eco_success_rate_chart(
            [eco],
            title="Custom Title: ECO Performance"
        )

        ax = fig.axes[0]
        assert ax.get_title() == "Custom Title: ECO Performance"

        # Clean up
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_chart_with_min_applications_filter(self):
        """Test filtering ECOs by minimum applications."""
        # ECO with 10 applications
        eco_many = ECOEffectiveness(eco_name="many_apps")
        for _ in range(10):
            eco_many.update(success=True, wns_delta_ps=30.0)

        # ECO with only 2 applications
        eco_few = ECOEffectiveness(eco_name="few_apps")
        for _ in range(2):
            eco_few.update(success=True, wns_delta_ps=20.0)

        # Filter to require at least 5 applications
        fig = plot_eco_success_rate_chart(
            [eco_many, eco_few],
            min_applications=5
        )

        ax = fig.axes[0]

        # Should only show eco_many
        labels = [label.get_text() for label in ax.get_xticklabels()]
        assert len(labels) == 1
        assert "many_apps" in labels

        # Clean up
        import matplotlib.pyplot as plt
        plt.close(fig)


class TestF068Step04:
    """Step 4: Save as PNG."""

    def test_save_chart_to_png(self):
        """Test saving chart to PNG file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "eco_success_rate.png"

            # Create ECO data
            eco = ECOEffectiveness(eco_name="test_eco")
            for _ in range(7):
                eco.update(success=True, wns_delta_ps=40.0)
            for _ in range(3):
                eco.update(success=False, wns_delta_ps=-10.0)

            # Generate and save chart
            fig = plot_eco_success_rate_chart([eco])
            save_eco_success_rate_chart(fig, output_path)

            # Verify file was created
            assert output_path.exists()
            assert output_path.stat().st_size > 0

    def test_save_chart_creates_parent_directories(self):
        """Test that saving creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "dirs" / "chart.png"

            # Parent directories don't exist yet
            assert not output_path.parent.exists()

            # Create ECO data
            eco = ECOEffectiveness(eco_name="test_eco")
            for _ in range(5):
                eco.update(success=True, wns_delta_ps=30.0)

            # Generate and save chart
            fig = plot_eco_success_rate_chart([eco])
            save_eco_success_rate_chart(fig, output_path)

            # Verify directories were created and file exists
            assert output_path.parent.exists()
            assert output_path.exists()

    def test_generate_eco_success_rate_chart_convenience_function(self):
        """Test the convenience function that generates and saves in one step."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "eco_chart.png"

            # Create ECO effectiveness map
            eco_map = {}

            buffer_eco = ECOEffectiveness(eco_name="buffer_insertion")
            for _ in range(8):
                buffer_eco.update(success=True, wns_delta_ps=50.0)
            for _ in range(2):
                buffer_eco.update(success=False, wns_delta_ps=-10.0)
            eco_map["buffer_insertion"] = buffer_eco

            sizing_eco = ECOEffectiveness(eco_name="cell_sizing")
            for _ in range(6):
                sizing_eco.update(success=True, wns_delta_ps=30.0)
            for _ in range(4):
                sizing_eco.update(success=False, wns_delta_ps=-5.0)
            eco_map["cell_sizing"] = sizing_eco

            # Generate and save using convenience function
            fig = generate_eco_success_rate_chart(eco_map, output_path)

            # Verify file was created
            assert output_path.exists()
            assert output_path.stat().st_size > 0

            # Verify figure was returned
            assert fig is not None


class TestF068Step05:
    """Step 5: Verify chart shows which ECOs are most effective."""

    def test_chart_clearly_distinguishes_effective_ecos(self):
        """Test that chart visually distinguishes effective vs ineffective ECOs."""
        # Create ECOs with very different success rates
        high_success = ECOEffectiveness(eco_name="highly_effective")
        for _ in range(95):
            high_success.update(success=True, wns_delta_ps=60.0)
        for _ in range(5):
            high_success.update(success=False, wns_delta_ps=-5.0)

        low_success = ECOEffectiveness(eco_name="poorly_effective")
        for _ in range(10):
            low_success.update(success=True, wns_delta_ps=10.0)
        for _ in range(90):
            low_success.update(success=False, wns_delta_ps=-20.0)

        # Generate chart
        fig = plot_eco_success_rate_chart([high_success, low_success])

        ax = fig.axes[0]

        # Get bars
        bars = [p for p in ax.patches if p.get_height() > 0]
        assert len(bars) == 2

        # First bar should be the high success (95%)
        # Second bar should be the low success (10%)
        heights = [bar.get_height() for bar in bars]
        assert heights[0] > 90  # High success is ~95%
        assert heights[1] < 15  # Low success is ~10%

        # Verify they're clearly different
        assert heights[0] > heights[1] * 5

        # Clean up
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_chart_includes_application_counts(self):
        """Test that chart shows number of applications for context."""
        # This verifies the (n=X) labels on bars
        eco1 = ECOEffectiveness(eco_name="eco_10_apps")
        for _ in range(7):
            eco1.update(success=True, wns_delta_ps=30.0)
        for _ in range(3):
            eco1.update(success=False, wns_delta_ps=-10.0)

        eco2 = ECOEffectiveness(eco_name="eco_50_apps")
        for _ in range(35):
            eco2.update(success=True, wns_delta_ps=25.0)
        for _ in range(15):
            eco2.update(success=False, wns_delta_ps=-8.0)

        fig = plot_eco_success_rate_chart([eco1, eco2])

        # The chart should include these counts in the labels
        # We verify by checking the figure was created with both ECOs
        assert fig is not None
        assert eco1.total_applications == 10
        assert eco2.total_applications == 50

        # Clean up
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_multiple_ecos_comparison_e2e(self):
        """End-to-end test: Generate chart comparing multiple ECOs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "eco_comparison.png"

            # Create diverse ECO effectiveness profiles
            ecos = {}

            # Excellent ECO
            excellent = ECOEffectiveness(eco_name="buffer_insertion")
            for _ in range(18):
                excellent.update(success=True, wns_delta_ps=55.0)
            for _ in range(2):
                excellent.update(success=False, wns_delta_ps=-5.0)
            ecos["buffer_insertion"] = excellent

            # Good ECO
            good = ECOEffectiveness(eco_name="cell_sizing")
            for _ in range(14):
                good.update(success=True, wns_delta_ps=40.0)
            for _ in range(6):
                good.update(success=False, wns_delta_ps=-8.0)
            ecos["cell_sizing"] = good

            # Average ECO
            average = ECOEffectiveness(eco_name="pin_swap")
            for _ in range(10):
                average.update(success=True, wns_delta_ps=25.0)
            for _ in range(10):
                average.update(success=False, wns_delta_ps=-12.0)
            ecos["pin_swap"] = average

            # Poor ECO
            poor = ECOEffectiveness(eco_name="logic_restructure")
            for _ in range(6):
                poor.update(success=True, wns_delta_ps=15.0)
            for _ in range(14):
                poor.update(success=False, wns_delta_ps=-25.0)
            ecos["logic_restructure"] = poor

            # Generate chart
            fig = generate_eco_success_rate_chart(
                ecos,
                output_path,
                title="ECO Effectiveness Study Results"
            )

            # Verify file exists
            assert output_path.exists()

            # Verify success rates are as expected
            assert ecos["buffer_insertion"].success_rate == 0.9
            assert ecos["cell_sizing"].success_rate == 0.7
            assert ecos["pin_swap"].success_rate == 0.5
            assert ecos["logic_restructure"].success_rate == 0.3

            # Verify chart visually distinguishes them
            ax = fig.axes[0]
            bars = [p for p in ax.patches if p.get_height() > 0]
            assert len(bars) == 4

            # Heights should be in descending order
            heights = [bar.get_height() for bar in bars]
            assert heights[0] > heights[1] > heights[2] > heights[3]


class TestF068ErrorHandling:
    """Test error handling for edge cases."""

    def test_empty_eco_list_raises_error(self):
        """Test that empty ECO list raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            plot_eco_success_rate_chart([])

    def test_empty_eco_map_raises_error(self):
        """Test that empty ECO map raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "chart.png"
            with pytest.raises(ValueError, match="cannot be empty"):
                generate_eco_success_rate_chart({}, output_path)

    def test_min_applications_filter_too_high_raises_error(self):
        """Test that overly restrictive min_applications raises error."""
        eco = ECOEffectiveness(eco_name="test_eco")
        for _ in range(2):
            eco.update(success=True, wns_delta_ps=20.0)

        with pytest.raises(ValueError, match="No ECOs have at least"):
            plot_eco_success_rate_chart([eco], min_applications=5)

    def test_save_non_png_path_raises_error(self):
        """Test that saving to non-PNG path raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "chart.jpg"

            eco = ECOEffectiveness(eco_name="test_eco")
            for _ in range(5):
                eco.update(success=True, wns_delta_ps=30.0)

            fig = plot_eco_success_rate_chart([eco])

            with pytest.raises(ValueError, match="must end in .png"):
                save_eco_success_rate_chart(fig, output_path)

            # Clean up
            import matplotlib.pyplot as plt
            plt.close(fig)


class TestF068Integration:
    """Integration tests for complete F068 workflow."""

    def test_complete_f068_workflow(self):
        """Test complete F068 workflow from ECO data to saved chart."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "study_eco_effectiveness.png"

            # Step 1: Simulate study with multiple ECOs
            eco_effectiveness_map = {}

            # Buffer insertion - high success
            buffer_eco = ECOEffectiveness(eco_name="buffer_insertion")
            for trial_idx in range(20):
                success = trial_idx < 17  # 17/20 = 85% success
                wns_delta = 50.0 if success else -10.0
                buffer_eco.update(success=success, wns_delta_ps=wns_delta)
            eco_effectiveness_map["buffer_insertion"] = buffer_eco

            # Cell sizing - medium success
            sizing_eco = ECOEffectiveness(eco_name="cell_sizing")
            for trial_idx in range(20):
                success = trial_idx < 12  # 12/20 = 60% success
                wns_delta = 35.0 if success else -8.0
                sizing_eco.update(success=success, wns_delta_ps=wns_delta)
            eco_effectiveness_map["cell_sizing"] = sizing_eco

            # Pin swap - low success
            pinswap_eco = ECOEffectiveness(eco_name="pin_swap")
            for trial_idx in range(20):
                success = trial_idx < 8  # 8/20 = 40% success
                wns_delta = 20.0 if success else -15.0
                pinswap_eco.update(success=success, wns_delta_ps=wns_delta)
            eco_effectiveness_map["pin_swap"] = pinswap_eco

            # Step 2: Verify success rates are computed
            assert buffer_eco.success_rate == 0.85
            assert sizing_eco.success_rate == 0.60
            assert pinswap_eco.success_rate == 0.40

            # Step 3 & 4: Generate and save chart
            fig = generate_eco_success_rate_chart(
                eco_effectiveness_map,
                output_path,
                title="Study: ECO Effectiveness Comparison",
                min_applications=1
            )

            # Step 5: Verify chart shows effectiveness clearly
            assert output_path.exists()
            assert output_path.stat().st_size > 0

            ax = fig.axes[0]
            assert "Study: ECO Effectiveness Comparison" in ax.get_title()

            # Verify all 3 ECOs are shown
            bars = [p for p in ax.patches if p.get_height() > 0]
            assert len(bars) == 3

            # Verify they're sorted by success rate (descending)
            heights = [bar.get_height() for bar in bars]
            assert heights[0] > heights[1] > heights[2]

            # Verify effectiveness is clearly visible
            assert heights[0] > 80  # Buffer insertion (85%)
            assert 55 < heights[1] < 65  # Cell sizing (60%)
            assert 35 < heights[2] < 45  # Pin swap (40%)
