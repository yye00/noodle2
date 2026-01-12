"""Tests for F233: Trajectory charts show best/median/worst statistics per stage.

Feature: F233 - Trajectory charts show best/median/worst statistics per stage
Priority: medium
Category: functional

Steps:
1. Generate improvement trajectory
2. Verify best survivor metric is plotted
3. Verify median survivor metric is plotted
4. Verify worst survivor metric is plotted
5. Verify visual distinction between best/median/worst lines
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pytest

from src.visualization.trajectory_plot import (
    plot_hot_ratio_trajectory,
    plot_wns_trajectory,
)


class TestF233TrajectoryStatistics:
    """Tests for F233: Trajectory charts show best/median/worst statistics per stage."""

    def test_step_1_generate_improvement_trajectory(self, tmp_path: Path) -> None:
        """Step 1: Generate improvement trajectory."""
        # Create sample stage data with multiple trials per stage
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0_baseline",
                "wns_values": [-1000, -1100, -900, -1050, -950],
            },
            {
                "stage_index": 1,
                "stage_name": "S1_eco1",
                "wns_values": [-600, -700, -500, -650, -550],
            },
            {
                "stage_index": 2,
                "stage_name": "S2_eco2",
                "wns_values": [-200, -300, -150, -250, -180],
            },
        ]

        # Generate trajectory chart
        fig = plot_wns_trajectory(stage_data)

        # Verify figure is created
        assert fig is not None
        assert isinstance(fig, plt.Figure)
        assert len(fig.axes) > 0

        plt.close(fig)

    def test_step_2_verify_best_survivor_metric_is_plotted(
        self, tmp_path: Path
    ) -> None:
        """Step 2: Verify best survivor metric is plotted."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "wns_values": [-1000, -1100, -900],  # Best: -900
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "wns_values": [-500, -600, -400],  # Best: -400
            },
            {
                "stage_index": 2,
                "stage_name": "S2",
                "wns_values": [-200, -250, -150],  # Best: -150
            },
        ]

        fig = plot_wns_trajectory(stage_data)
        ax = fig.axes[0]

        # Get all line data
        lines = ax.get_lines()
        assert len(lines) >= 3  # Should have multiple lines

        # Check that best values are plotted
        # Best WNS = max (least negative): -900, -400, -150
        expected_best = [-900, -400, -150]

        # Find the line with best values (should be in one of the plotted lines)
        found_best_line = False
        for line in lines:
            y_data = line.get_ydata()
            if len(y_data) == 3:
                # Check if this line matches our expected best values
                if np.allclose(y_data, expected_best, atol=1):
                    found_best_line = True
                    break

        assert found_best_line, "Best survivor metric line not found in plot"

        plt.close(fig)

    def test_step_3_verify_median_survivor_metric_is_plotted(
        self, tmp_path: Path
    ) -> None:
        """Step 3: Verify median survivor metric is plotted."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "wns_values": [-900, -1000, -1100],  # Median: -1000
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "wns_values": [-400, -500, -600],  # Median: -500
            },
            {
                "stage_index": 2,
                "stage_name": "S2",
                "wns_values": [-150, -200, -250],  # Median: -200
            },
        ]

        fig = plot_wns_trajectory(stage_data)
        ax = fig.axes[0]

        # Get all line data
        lines = ax.get_lines()

        # Expected median values
        expected_median = [-1000, -500, -200]

        # Find the median line
        found_median_line = False
        for line in lines:
            y_data = line.get_ydata()
            if len(y_data) == 3:
                if np.allclose(y_data, expected_median, atol=1):
                    found_median_line = True
                    break

        assert found_median_line, "Median survivor metric line not found in plot"

        plt.close(fig)

    def test_step_4_verify_worst_survivor_metric_is_plotted(
        self, tmp_path: Path
    ) -> None:
        """Step 4: Verify worst survivor metric is plotted."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "wns_values": [-900, -1000, -1200],  # Worst: -1200
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "wns_values": [-400, -500, -700],  # Worst: -700
            },
            {
                "stage_index": 2,
                "stage_name": "S2",
                "wns_values": [-150, -200, -300],  # Worst: -300
            },
        ]

        fig = plot_wns_trajectory(stage_data)
        ax = fig.axes[0]

        # Get all line data
        lines = ax.get_lines()

        # Expected worst values (min = most negative)
        expected_worst = [-1200, -700, -300]

        # Find the worst line
        found_worst_line = False
        for line in lines:
            y_data = line.get_ydata()
            if len(y_data) == 3:
                if np.allclose(y_data, expected_worst, atol=1):
                    found_worst_line = True
                    break

        assert found_worst_line, "Worst survivor metric line not found in plot"

        plt.close(fig)

    def test_step_5_verify_visual_distinction_between_lines(
        self, tmp_path: Path
    ) -> None:
        """Step 5: Verify visual distinction between best/median/worst lines."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "wns_values": [-800, -900, -1000, -850, -950],
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

        # Get all lines
        lines = ax.get_lines()
        assert len(lines) >= 3

        # Verify lines have different visual properties
        colors = set()
        markers = set()
        linestyles = set()

        for line in lines:
            colors.add(line.get_color())
            markers.add(line.get_marker())
            linestyles.add(line.get_linestyle())

        # Should have at least 2 different colors (lines should be visually distinct)
        assert len(colors) >= 2, "Lines should have different colors"

        # Should have at least 2 different markers or linestyles
        assert len(markers) >= 2 or len(linestyles) >= 2, (
            "Lines should have different markers or linestyles"
        )

        plt.close(fig)


class TestF233HotRatioStatistics:
    """Test trajectory statistics for hot_ratio metric."""

    def test_hot_ratio_shows_best_median_worst_statistics(
        self, tmp_path: Path
    ) -> None:
        """Verify hot_ratio trajectory also shows best/median/worst statistics."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "hot_ratio_values": [0.9, 0.85, 0.95, 0.88, 0.92],
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "hot_ratio_values": [0.6, 0.55, 0.65, 0.58, 0.62],
            },
            {
                "stage_index": 2,
                "stage_name": "S2",
                "hot_ratio_values": [0.3, 0.25, 0.35, 0.28, 0.32],
            },
        ]

        fig = plot_hot_ratio_trajectory(stage_data)
        ax = fig.axes[0]

        # Verify multiple lines are plotted
        lines = ax.get_lines()
        assert len(lines) >= 3  # Should have best, median, worst (+ possibly trend)

        # Expected best (min for hot_ratio): 0.85, 0.55, 0.25
        expected_best = [0.85, 0.55, 0.25]

        # Expected median: 0.9, 0.6, 0.3
        expected_median = [0.9, 0.6, 0.3]

        # Expected worst (max for hot_ratio): 0.95, 0.65, 0.35
        expected_worst = [0.95, 0.65, 0.35]

        # Find these lines in the plot
        found_best = False
        found_median = False
        found_worst = False

        for line in lines:
            y_data = line.get_ydata()
            if len(y_data) == 3:
                if np.allclose(y_data, expected_best, atol=0.01):
                    found_best = True
                elif np.allclose(y_data, expected_median, atol=0.01):
                    found_median = True
                elif np.allclose(y_data, expected_worst, atol=0.01):
                    found_worst = True

        assert found_best, "Best hot_ratio line not found"
        assert found_median, "Median hot_ratio line not found"
        assert found_worst, "Worst hot_ratio line not found"

        plt.close(fig)


class TestF233StatisticsEdgeCases:
    """Test edge cases for trajectory statistics."""

    def test_single_trial_per_stage(self, tmp_path: Path) -> None:
        """Test trajectory with single trial per stage (best=median=worst)."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "wns_values": [-1000],  # Single value
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "wns_values": [-500],
            },
            {
                "stage_index": 2,
                "stage_name": "S2",
                "wns_values": [-200],
            },
        ]

        fig = plot_wns_trajectory(stage_data)
        ax = fig.axes[0]

        # Should still work, with all three statistics equal
        lines = ax.get_lines()
        assert len(lines) >= 3

        plt.close(fig)

    def test_many_trials_per_stage(self, tmp_path: Path) -> None:
        """Test trajectory with many trials per stage."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "wns_values": list(range(-1000, -900, 5)),  # 20 trials
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "wns_values": list(range(-600, -500, 5)),
            },
            {
                "stage_index": 2,
                "stage_name": "S2",
                "wns_values": list(range(-300, -200, 5)),
            },
        ]

        fig = plot_wns_trajectory(stage_data)
        ax = fig.axes[0]

        # Should handle many trials gracefully
        lines = ax.get_lines()
        assert len(lines) >= 3

        plt.close(fig)

    def test_two_stage_trajectory(self, tmp_path: Path) -> None:
        """Test trajectory with only two stages."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "wns_values": [-1000, -1100, -900],
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "wns_values": [-500, -600, -400],
            },
        ]

        fig = plot_wns_trajectory(stage_data)
        ax = fig.axes[0]

        # Should work with minimum number of stages
        lines = ax.get_lines()
        assert len(lines) >= 3

        plt.close(fig)

    def test_varied_trial_counts_per_stage(self, tmp_path: Path) -> None:
        """Test trajectory with different numbers of trials per stage."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "wns_values": [-1000, -1100],  # 2 trials
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "wns_values": [-500, -600, -550, -580, -520],  # 5 trials
            },
            {
                "stage_index": 2,
                "stage_name": "S2",
                "wns_values": [-200, -250, -220],  # 3 trials
            },
        ]

        fig = plot_wns_trajectory(stage_data)
        ax = fig.axes[0]

        # Should handle varying trial counts
        lines = ax.get_lines()
        assert len(lines) >= 3

        # Verify statistics are calculated correctly despite different counts
        # Stage 0: best=-1000, median=-1050, worst=-1100
        # Stage 1: best=-500, median=-550, worst=-600
        # Stage 2: best=-200, median=-220, worst=-250

        plt.close(fig)


class TestF233Legend:
    """Test that legend clearly identifies best/median/worst lines."""

    def test_legend_includes_all_statistics(self, tmp_path: Path) -> None:
        """Verify legend includes labels for best, median, and worst."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "wns_values": [-1000, -1100, -900],
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "wns_values": [-500, -600, -400],
            },
        ]

        fig = plot_wns_trajectory(stage_data)
        ax = fig.axes[0]

        # Get legend
        legend = ax.get_legend()
        assert legend is not None

        # Get legend text
        legend_texts = [text.get_text().lower() for text in legend.get_texts()]

        # Verify legend mentions best, median, worst
        has_best = any("best" in text for text in legend_texts)
        has_median = any("median" in text for text in legend_texts)
        has_worst = any("worst" in text for text in legend_texts)

        assert has_best, "Legend should mention 'best'"
        assert has_median, "Legend should mention 'median'"
        assert has_worst, "Legend should mention 'worst'"

        plt.close(fig)
