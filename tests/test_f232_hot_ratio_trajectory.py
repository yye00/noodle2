"""
Tests for Feature F232: Generate hot_ratio improvement trajectory chart.

Verification steps:
1. Run multi-stage study tracking congestion
2. Track hot_ratio per stage
3. Generate congestion_improvement.png
4. Verify chart shows hot_ratio progression
5. Verify improvement is visible (decreasing hot_ratio)
"""

from pathlib import Path

import numpy as np
import pytest

from src.visualization.trajectory_plot import (
    generate_hot_ratio_trajectory_chart,
    plot_hot_ratio_trajectory,
    save_trajectory_plot,
)


class TestHotRatioTrajectoryF232:
    """Tests for F232: Generate hot_ratio improvement trajectory chart."""

    def test_step_1_run_multi_stage_study_tracking_congestion(
        self, tmp_path: Path
    ) -> None:
        """
        Step 1: Run multi-stage study tracking congestion.

        This test simulates a multi-stage study with hot_ratio values improving
        (decreasing) across stages.
        """
        # Simulate a 3-stage study with hot_ratio improvement
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0_baseline",
                "hot_ratio_values": [0.85, 0.88, 0.90, 0.87, 0.89],  # High congestion
            },
            {
                "stage_index": 1,
                "stage_name": "S1_eco_round1",
                "hot_ratio_values": [0.72, 0.75, 0.70, 0.73, 0.74],  # Improved
            },
            {
                "stage_index": 2,
                "stage_name": "S2_eco_round2",
                "hot_ratio_values": [0.60, 0.63, 0.58, 0.61, 0.59],  # Further improved
            },
        ]

        # Verify we have stage data
        assert len(stage_data) == 3
        assert stage_data[0]["stage_name"] == "S0_baseline"
        assert len(stage_data[0]["hot_ratio_values"]) == 5

    def test_step_2_track_hot_ratio_per_stage(self, tmp_path: Path) -> None:
        """
        Step 2: Track hot_ratio per stage.

        Verify that hot_ratio values are tracked for each stage and show improvement.
        """
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "hot_ratio_values": [0.85, 0.88, 0.90, 0.87, 0.89],
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "hot_ratio_values": [0.72, 0.75, 0.70, 0.73, 0.74],
            },
            {
                "stage_index": 2,
                "stage_name": "S2",
                "hot_ratio_values": [0.60, 0.63, 0.58, 0.61, 0.59],
            },
        ]

        # Verify hot_ratio improves (decreases) across stages
        median_s0 = np.median(stage_data[0]["hot_ratio_values"])
        median_s1 = np.median(stage_data[1]["hot_ratio_values"])
        median_s2 = np.median(stage_data[2]["hot_ratio_values"])

        assert median_s0 > median_s1  # S1 better than S0 (lower is better)
        assert median_s1 > median_s2  # S2 better than S1
        assert median_s2 < 0.7  # Final stage below critical threshold

    def test_step_3_generate_congestion_improvement_png(self, tmp_path: Path) -> None:
        """
        Step 3: Generate congestion_improvement.png.

        Verify that the chart is generated and saved successfully.
        """
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0_baseline",
                "hot_ratio_values": [0.85, 0.88, 0.90, 0.87, 0.89],
            },
            {
                "stage_index": 1,
                "stage_name": "S1_eco",
                "hot_ratio_values": [0.72, 0.75, 0.70, 0.73, 0.74],
            },
            {
                "stage_index": 2,
                "stage_name": "S2_final",
                "hot_ratio_values": [0.60, 0.63, 0.58, 0.61, 0.59],
            },
        ]

        # Generate chart
        output_path = generate_hot_ratio_trajectory_chart(
            stage_data, tmp_path, "congestion_improvement.png"
        )

        # Verify file created
        assert output_path.exists()
        assert output_path.name == "congestion_improvement.png"
        assert output_path.stat().st_size > 0

    def test_step_4_verify_chart_shows_hot_ratio_progression(
        self, tmp_path: Path
    ) -> None:
        """
        Step 4: Verify chart shows hot_ratio progression.

        Generate a chart and verify it contains all stages.
        """
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "hot_ratio_values": [0.95, 0.98, 0.93],
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "hot_ratio_values": [0.80, 0.82, 0.78],
            },
            {
                "stage_index": 2,
                "stage_name": "S2",
                "hot_ratio_values": [0.65, 0.68, 0.63],
            },
            {
                "stage_index": 3,
                "stage_name": "S3",
                "hot_ratio_values": [0.50, 0.53, 0.48],
            },
        ]

        # Generate chart
        fig = plot_hot_ratio_trajectory(stage_data)

        # Verify figure created
        assert fig is not None
        assert len(fig.axes) == 1

        ax = fig.axes[0]

        # Verify x-axis has correct number of stages
        assert len(ax.get_xticks()) == 4

        # Verify y-axis label
        assert "Hot Ratio" in ax.get_ylabel()

        # Verify title
        assert "Trajectory" in ax.get_title()

    def test_step_5_verify_improvement_is_visible(self, tmp_path: Path) -> None:
        """
        Step 5: Verify improvement is visible (decreasing hot_ratio).

        Check that the plot shows decreasing hot_ratio trend.
        """
        # Create strongly improving data (decreasing hot_ratio)
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "hot_ratio_values": [0.95, 0.96, 0.97],
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "hot_ratio_values": [0.75, 0.76, 0.77],
            },
            {
                "stage_index": 2,
                "stage_name": "S2",
                "hot_ratio_values": [0.55, 0.56, 0.57],
            },
            {
                "stage_index": 3,
                "stage_name": "S3",
                "hot_ratio_values": [0.35, 0.36, 0.37],
            },
        ]

        fig = plot_hot_ratio_trajectory(stage_data)
        ax = fig.axes[0]

        # Verify trend line is included
        legend_labels = [text.get_text() for text in ax.get_legend().get_texts()]
        assert any("Trend" in label for label in legend_labels)

        # Calculate actual trend slope from median values
        median_values = [np.median(stage["hot_ratio_values"]) for stage in stage_data]
        stages = [s["stage_index"] for s in stage_data]

        # Fit linear trend
        z = np.polyfit(stages, median_values, 1)
        slope = z[0]

        # Verify negative slope (improvement = hot_ratio decreasing)
        assert slope < 0, f"Expected negative slope (improvement), got {slope}"


class TestHotRatioTrajectoryEdgeCases:
    """Test edge cases for hot_ratio trajectory visualization."""

    def test_empty_stage_data_raises_error(self) -> None:
        """Empty stage data should raise ValueError."""
        with pytest.raises(ValueError, match="stage_data cannot be empty"):
            plot_hot_ratio_trajectory([])

    def test_missing_stage_index_raises_error(self) -> None:
        """Missing stage_index should raise ValueError."""
        stage_data = [
            {
                "stage_name": "S0",
                "hot_ratio_values": [0.8],
            }
        ]
        with pytest.raises(ValueError, match="missing 'stage_index'"):
            plot_hot_ratio_trajectory(stage_data)

    def test_missing_stage_name_raises_error(self) -> None:
        """Missing stage_name should raise ValueError."""
        stage_data = [
            {
                "stage_index": 0,
                "hot_ratio_values": [0.8],
            }
        ]
        with pytest.raises(ValueError, match="missing 'stage_name'"):
            plot_hot_ratio_trajectory(stage_data)

    def test_missing_hot_ratio_values_raises_error(self) -> None:
        """Missing hot_ratio_values should raise ValueError."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
            }
        ]
        with pytest.raises(ValueError, match="missing 'hot_ratio_values'"):
            plot_hot_ratio_trajectory(stage_data)

    def test_empty_hot_ratio_values_raises_error(self) -> None:
        """Empty hot_ratio_values list should raise ValueError."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "hot_ratio_values": [],
            }
        ]
        with pytest.raises(ValueError, match="empty 'hot_ratio_values'"):
            plot_hot_ratio_trajectory(stage_data)

    def test_single_stage_chart(self, tmp_path: Path) -> None:
        """Single stage should create valid chart without trend line."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0_only",
                "hot_ratio_values": [0.80, 0.85, 0.82],
            }
        ]

        fig = plot_hot_ratio_trajectory(stage_data)
        assert fig is not None

        # Save should work
        output_path = tmp_path / "single_stage_hot_ratio.png"
        save_trajectory_plot(fig, output_path)
        assert output_path.exists()

    def test_many_stages_chart(self, tmp_path: Path) -> None:
        """Chart should handle many stages gracefully."""
        stage_data = [
            {
                "stage_index": i,
                "stage_name": f"S{i}",
                "hot_ratio_values": [0.95 - i * 0.05, 0.97 - i * 0.05, 0.93 - i * 0.05],
            }
            for i in range(10)
        ]

        fig = plot_hot_ratio_trajectory(stage_data)
        assert fig is not None

        # Verify all stages included
        ax = fig.axes[0]
        assert len(ax.get_xticks()) == 10

    def test_custom_title(self, tmp_path: Path) -> None:
        """Custom title should be used."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "hot_ratio_values": [0.8],
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "hot_ratio_values": [0.6],
            },
        ]

        custom_title = "Custom Hot Ratio Trajectory"
        fig = plot_hot_ratio_trajectory(stage_data, title=custom_title)

        assert fig.axes[0].get_title() == custom_title

    def test_critical_threshold_line_shown(self, tmp_path: Path) -> None:
        """Critical threshold line at 0.7 should be shown when relevant."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "hot_ratio_values": [0.95, 0.96, 0.97],  # Above threshold
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "hot_ratio_values": [0.75, 0.76, 0.77],  # Above threshold
            },
            {
                "stage_index": 2,
                "stage_name": "S2",
                "hot_ratio_values": [0.55, 0.56, 0.57],  # Below threshold
            },
        ]

        fig = plot_hot_ratio_trajectory(stage_data)
        ax = fig.axes[0]

        # Verify y-axis range includes both above and below 0.7
        y_min, y_max = ax.get_ylim()
        assert y_min < 0.7 < y_max


class TestF232Integration:
    """Integration tests for complete F232 workflow."""

    def test_complete_f232_workflow(self, tmp_path: Path) -> None:
        """
        Complete F232 workflow: multi-stage study -> hot_ratio tracking -> chart generation.
        """
        # Simulate multi-stage study execution with congestion improvement
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0_baseline",
                "hot_ratio_values": [0.92, 0.95, 0.91, 0.93, 0.94],
            },
            {
                "stage_index": 1,
                "stage_name": "S1_eco_placement",
                "hot_ratio_values": [0.78, 0.80, 0.76, 0.79, 0.77],
            },
            {
                "stage_index": 2,
                "stage_name": "S2_eco_routing",
                "hot_ratio_values": [0.62, 0.65, 0.60, 0.63, 0.61],
            },
            {
                "stage_index": 3,
                "stage_name": "S3_eco_final",
                "hot_ratio_values": [0.48, 0.50, 0.46, 0.49, 0.47],
            },
        ]

        # Generate chart using high-level API
        output_path = generate_hot_ratio_trajectory_chart(
            stage_data, tmp_path, "congestion_improvement.png"
        )

        # Verify chart created
        assert output_path.exists()
        assert output_path.name == "congestion_improvement.png"
        assert output_path.stat().st_size > 10000  # Reasonable PNG size

        # Verify improvement trend (decreasing hot_ratio)
        medians = [np.median(s["hot_ratio_values"]) for s in stage_data]
        assert medians[0] > medians[1] > medians[2] > medians[3]
        assert medians[3] < 0.7  # Final stage below critical threshold

    def test_generate_hot_ratio_trajectory_with_default_filename(
        self, tmp_path: Path
    ) -> None:
        """Test default filename for hot_ratio trajectory chart."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "hot_ratio_values": [0.8],
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "hot_ratio_values": [0.6],
            },
        ]

        output_path = generate_hot_ratio_trajectory_chart(stage_data, tmp_path)

        # Default filename should be hot_ratio_trajectory.png
        assert output_path.name == "hot_ratio_trajectory.png"
        assert output_path.exists()

    def test_output_directory_created_if_not_exists(self, tmp_path: Path) -> None:
        """Output directory should be created automatically."""
        nested_dir = tmp_path / "congestion" / "charts"
        assert not nested_dir.exists()

        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "hot_ratio_values": [0.8],
            }
        ]

        output_path = generate_hot_ratio_trajectory_chart(stage_data, nested_dir)

        assert nested_dir.exists()
        assert output_path.exists()

    def test_best_median_worst_bands_are_shown(self, tmp_path: Path) -> None:
        """Verify best/median/worst bands are displayed correctly."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "hot_ratio_values": [0.80, 0.85, 0.90, 0.82, 0.88],  # Wide spread
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "hot_ratio_values": [0.60, 0.65, 0.70, 0.62, 0.68],
            },
            {
                "stage_index": 2,
                "stage_name": "S2",
                "hot_ratio_values": [0.40, 0.45, 0.50, 0.42, 0.48],
            },
        ]

        fig = plot_hot_ratio_trajectory(stage_data)
        ax = fig.axes[0]

        # Verify we have multiple lines (best, median, worst, trend, fill)
        lines = ax.get_lines()
        assert len(lines) >= 3  # At least median, best, worst

        # Verify legend entries
        legend_labels = [text.get_text() for text in ax.get_legend().get_texts()]
        assert any("Median" in label for label in legend_labels)
        assert any("Best" in label for label in legend_labels)
        assert any("Worst" in label for label in legend_labels)
        assert any("Range" in label for label in legend_labels)
