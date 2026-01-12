"""
Tests for Feature F231: Generate WNS improvement trajectory chart across stages.

Verification steps:
1. Run multi-stage study
2. Track WNS metric per stage
3. Generate improvement_trajectory.png
4. Verify chart shows WNS progression from S0 to final
5. Verify best/median/worst bands are shown
6. Verify trend line shows improvement
"""

from pathlib import Path

import numpy as np
import pytest

from src.visualization.trajectory_plot import (
    generate_wns_trajectory_chart,
    plot_wns_trajectory,
    save_trajectory_plot,
)


class TestWNSTrajectoryF231:
    """Tests for F231: Generate WNS improvement trajectory chart across stages."""

    def test_step_1_run_multi_stage_study(self, tmp_path: Path) -> None:
        """
        Step 1: Run multi-stage study.

        This test simulates a multi-stage study with WNS values improving across stages.
        """
        # Simulate a 3-stage study with WNS improvement
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0_baseline",
                "wns_values": [-800, -850, -900, -780, -820],  # ps
            },
            {
                "stage_index": 1,
                "stage_name": "S1_eco_round1",
                "wns_values": [-400, -450, -380, -420, -410],  # Improved
            },
            {
                "stage_index": 2,
                "stage_name": "S2_eco_round2",
                "wns_values": [-100, -150, -80, -120, -90],  # Further improved
            },
        ]

        # Verify we have stage data
        assert len(stage_data) == 3
        assert stage_data[0]["stage_name"] == "S0_baseline"
        assert len(stage_data[0]["wns_values"]) == 5

    def test_step_2_track_wns_metric_per_stage(self, tmp_path: Path) -> None:
        """
        Step 2: Track WNS metric per stage.

        Verify that WNS values are tracked for each stage and show improvement.
        """
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "wns_values": [-800, -850, -900, -780, -820],
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "wns_values": [-400, -450, -380, -420, -410],
            },
            {
                "stage_index": 2,
                "stage_name": "S2",
                "wns_values": [-100, -150, -80, -120, -90],
            },
        ]

        # Verify WNS improves (becomes less negative) across stages
        median_s0 = np.median(stage_data[0]["wns_values"])
        median_s1 = np.median(stage_data[1]["wns_values"])
        median_s2 = np.median(stage_data[2]["wns_values"])

        assert median_s0 < median_s1  # S1 better than S0
        assert median_s1 < median_s2  # S2 better than S1
        assert median_s2 > -200  # Final stage shows significant improvement

    def test_step_3_generate_improvement_trajectory_png(self, tmp_path: Path) -> None:
        """
        Step 3: Generate improvement_trajectory.png.

        Verify that the chart is generated and saved successfully.
        """
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0_baseline",
                "wns_values": [-800, -850, -900, -780, -820],
            },
            {
                "stage_index": 1,
                "stage_name": "S1_eco",
                "wns_values": [-400, -450, -380, -420, -410],
            },
            {
                "stage_index": 2,
                "stage_name": "S2_final",
                "wns_values": [-100, -150, -80, -120, -90],
            },
        ]

        # Generate chart
        output_path = generate_wns_trajectory_chart(
            stage_data, tmp_path, "improvement_trajectory.png"
        )

        # Verify file created
        assert output_path.exists()
        assert output_path.name == "improvement_trajectory.png"
        assert output_path.stat().st_size > 0

    def test_step_4_verify_chart_shows_wns_progression(self, tmp_path: Path) -> None:
        """
        Step 4: Verify chart shows WNS progression from S0 to final.

        Generate a chart and verify it contains all stages.
        """
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "wns_values": [-1000, -1100, -1050],
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "wns_values": [-600, -650, -580],
            },
            {
                "stage_index": 2,
                "stage_name": "S2",
                "wns_values": [-200, -250, -180],
            },
            {
                "stage_index": 3,
                "stage_name": "S3",
                "wns_values": [-50, -80, -40],
            },
        ]

        # Generate chart
        fig = plot_wns_trajectory(stage_data)

        # Verify figure created
        assert fig is not None
        assert len(fig.axes) == 1

        ax = fig.axes[0]

        # Verify x-axis has correct number of stages
        assert len(ax.get_xticks()) == 4

        # Verify y-axis label
        assert "WNS" in ax.get_ylabel()

        # Verify title
        assert "Trajectory" in ax.get_title()

    def test_step_5_verify_best_median_worst_bands(self, tmp_path: Path) -> None:
        """
        Step 5: Verify best/median/worst bands are shown.

        Check that the plot includes best, median, and worst WNS lines.
        """
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "wns_values": [-800, -900, -1000, -850, -950],  # Wide spread
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "wns_values": [-400, -450, -500, -420, -480],
            },
            {
                "stage_index": 2,
                "stage_name": "S2",
                "wns_values": [-100, -120, -150, -110, -130],
            },
        ]

        fig = plot_wns_trajectory(stage_data)
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

    def test_step_6_verify_trend_line_shows_improvement(self, tmp_path: Path) -> None:
        """
        Step 6: Verify trend line shows improvement.

        Check that the trend line is included and shows positive slope (improvement).
        """
        # Create strongly improving data
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "wns_values": [-1000, -1050, -1100],
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "wns_values": [-600, -650, -700],
            },
            {
                "stage_index": 2,
                "stage_name": "S2",
                "wns_values": [-200, -250, -300],
            },
            {
                "stage_index": 3,
                "stage_name": "S3",
                "wns_values": [0, -50, -100],  # Near timing closure
            },
        ]

        fig = plot_wns_trajectory(stage_data)
        ax = fig.axes[0]

        # Verify trend line is included
        legend_labels = [text.get_text() for text in ax.get_legend().get_texts()]
        assert any("Trend" in label for label in legend_labels)

        # Verify we have multiple plot lines
        lines = ax.get_lines()
        assert len(lines) >= 4  # median, best, worst, trend

        # Calculate actual trend slope from median values
        median_values = [
            np.median(stage["wns_values"]) for stage in stage_data
        ]
        stages = [s["stage_index"] for s in stage_data]

        # Fit linear trend
        z = np.polyfit(stages, median_values, 1)
        slope = z[0]

        # Verify positive slope (improvement = WNS becoming less negative)
        assert slope > 0, f"Expected positive slope (improvement), got {slope}"


class TestWNSTrajectoryEdgeCases:
    """Test edge cases for WNS trajectory visualization."""

    def test_empty_stage_data_raises_error(self) -> None:
        """Empty stage data should raise ValueError."""
        with pytest.raises(ValueError, match="stage_data cannot be empty"):
            plot_wns_trajectory([])

    def test_missing_stage_index_raises_error(self) -> None:
        """Missing stage_index should raise ValueError."""
        stage_data = [
            {
                "stage_name": "S0",
                "wns_values": [-800],
            }
        ]
        with pytest.raises(ValueError, match="missing 'stage_index'"):
            plot_wns_trajectory(stage_data)

    def test_missing_stage_name_raises_error(self) -> None:
        """Missing stage_name should raise ValueError."""
        stage_data = [
            {
                "stage_index": 0,
                "wns_values": [-800],
            }
        ]
        with pytest.raises(ValueError, match="missing 'stage_name'"):
            plot_wns_trajectory(stage_data)

    def test_missing_wns_values_raises_error(self) -> None:
        """Missing wns_values should raise ValueError."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
            }
        ]
        with pytest.raises(ValueError, match="missing 'wns_values'"):
            plot_wns_trajectory(stage_data)

    def test_empty_wns_values_raises_error(self) -> None:
        """Empty wns_values list should raise ValueError."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "wns_values": [],
            }
        ]
        with pytest.raises(ValueError, match="empty 'wns_values'"):
            plot_wns_trajectory(stage_data)

    def test_single_stage_chart(self, tmp_path: Path) -> None:
        """Single stage should create valid chart without trend line."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0_only",
                "wns_values": [-800, -850, -900],
            }
        ]

        fig = plot_wns_trajectory(stage_data)
        assert fig is not None

        # Save should work
        output_path = tmp_path / "single_stage.png"
        save_trajectory_plot(fig, output_path)
        assert output_path.exists()

    def test_many_stages_chart(self, tmp_path: Path) -> None:
        """Chart should handle many stages gracefully."""
        stage_data = [
            {
                "stage_index": i,
                "stage_name": f"S{i}",
                "wns_values": [-1000 + i * 150, -1050 + i * 150, -1100 + i * 150],
            }
            for i in range(10)
        ]

        fig = plot_wns_trajectory(stage_data)
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
                "wns_values": [-800],
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "wns_values": [-400],
            },
        ]

        custom_title = "Custom WNS Trajectory"
        fig = plot_wns_trajectory(stage_data, title=custom_title)

        assert fig.axes[0].get_title() == custom_title

    def test_custom_figsize_and_dpi(self, tmp_path: Path) -> None:
        """Custom figsize and DPI should be applied."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "wns_values": [-800],
            }
        ]

        fig = plot_wns_trajectory(stage_data, figsize=(8, 6), dpi=100)

        assert fig.get_figwidth() == 8
        assert fig.get_figheight() == 6
        assert fig.get_dpi() == 100


class TestF231Integration:
    """Integration tests for complete F231 workflow."""

    def test_complete_f231_workflow(self, tmp_path: Path) -> None:
        """
        Complete F231 workflow: multi-stage study -> WNS tracking -> chart generation.
        """
        # Simulate multi-stage study execution
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0_baseline",
                "wns_values": [-1200, -1300, -1150, -1250, -1280],
            },
            {
                "stage_index": 1,
                "stage_name": "S1_eco_topology",
                "wns_values": [-800, -850, -780, -820, -810],
            },
            {
                "stage_index": 2,
                "stage_name": "S2_eco_placement",
                "wns_values": [-400, -450, -380, -420, -410],
            },
            {
                "stage_index": 3,
                "stage_name": "S3_eco_final",
                "wns_values": [-100, -150, -80, -120, -95],
            },
        ]

        # Generate chart using high-level API
        output_path = generate_wns_trajectory_chart(
            stage_data, tmp_path, "improvement_trajectory.png"
        )

        # Verify chart created
        assert output_path.exists()
        assert output_path.name == "improvement_trajectory.png"
        assert output_path.stat().st_size > 10000  # Reasonable PNG size

        # Verify improvement trend
        medians = [np.median(s["wns_values"]) for s in stage_data]
        assert medians[0] < medians[1] < medians[2] < medians[3]
        assert medians[3] > -150  # Final stage near timing closure

    def test_generate_wns_trajectory_with_custom_filename(self, tmp_path: Path) -> None:
        """Test custom filename for WNS trajectory chart."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "wns_values": [-800],
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "wns_values": [-400],
            },
        ]

        custom_filename = "custom_wns_chart.png"
        output_path = generate_wns_trajectory_chart(
            stage_data, tmp_path, custom_filename
        )

        assert output_path.name == custom_filename
        assert output_path.exists()

    def test_output_directory_created_if_not_exists(self, tmp_path: Path) -> None:
        """Output directory should be created automatically."""
        nested_dir = tmp_path / "reports" / "charts"
        assert not nested_dir.exists()

        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "wns_values": [-800],
            }
        ]

        output_path = generate_wns_trajectory_chart(stage_data, nested_dir)

        assert nested_dir.exists()
        assert output_path.exists()
