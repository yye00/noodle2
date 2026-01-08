"""Tests for Pareto frontier visualization."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import matplotlib.pyplot as plt
import pytest

from src.controller.pareto import (
    CONGESTION_OBJECTIVE,
    TIMING_OBJECTIVE,
    ObjectiveSpec,
    ParetoFrontier,
    ParetoTrial,
    compute_pareto_frontier,
)
from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult
from src.visualization.pareto_plot import (
    generate_pareto_visualization,
    plot_pareto_frontier_2d,
    save_pareto_plot,
)


@pytest.fixture
def sample_trial_results(tmp_path: Path) -> list[TrialResult]:
    """Create sample trial results with metrics for testing."""
    trials = []

    # Define test cases with different timing/congestion tradeoffs
    test_cases = [
        # (case_name, wns_ps, hot_ratio) - Pareto optimal points
        ("case_0_0", -100, 0.05),  # Good timing, low congestion - PARETO
        ("case_0_1", -50, 0.15),  # Better timing, higher congestion - PARETO
        ("case_0_2", -20, 0.30),  # Best timing, highest congestion - PARETO
        # Dominated points
        ("case_0_3", -150, 0.20),  # Bad timing, high congestion - DOMINATED
        ("case_0_4", -80, 0.25),  # Medium timing, medium congestion - DOMINATED
    ]

    for i, (case_name, wns, hot_ratio) in enumerate(test_cases):
        # Create metrics file
        metrics_dir = tmp_path / case_name
        metrics_dir.mkdir(parents=True, exist_ok=True)
        metrics_file = metrics_dir / "metrics.json"

        metrics = {
            "timing": {"wns_ps": wns},
            "congestion": {"hot_ratio": hot_ratio},
        }

        with open(metrics_file, "w") as f:
            json.dump(metrics, f)

        # Create trial result
        config = TrialConfig(
            study_name="test_study",
            case_name=case_name,
            stage_index=0,
            trial_index=i,
            script_path="/tmp/test.tcl",
        )

        artifacts = TrialArtifacts(
            trial_dir=metrics_dir,
            metrics_json=metrics_file,
        )

        trial = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=10.0,
            artifacts=artifacts,
        )

        trials.append(trial)

    return trials


@pytest.fixture
def sample_pareto_frontier(sample_trial_results: list[TrialResult]) -> ParetoFrontier:
    """Create sample Pareto frontier for testing."""
    objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
    return compute_pareto_frontier(sample_trial_results, objectives)


class TestParetoFrontierPlot:
    """Tests for Pareto frontier 2D plotting."""

    def test_generate_pareto_plot(self, sample_pareto_frontier: ParetoFrontier) -> None:
        """Test basic Pareto plot generation."""
        fig = plot_pareto_frontier_2d(
            sample_pareto_frontier,
            objective_x="wns_ps",
            objective_y="hot_ratio",
        )

        assert fig is not None
        assert isinstance(fig, plt.Figure)

        # Verify figure has axes
        axes = fig.get_axes()
        assert len(axes) == 1

        ax = axes[0]
        assert ax.get_xlabel() != ""
        assert ax.get_ylabel() != ""
        assert ax.get_title() != ""

        plt.close(fig)

    def test_plot_has_correct_axes_labels(
        self, sample_pareto_frontier: ParetoFrontier
    ) -> None:
        """Test that axes are labeled with objective names and units."""
        fig = plot_pareto_frontier_2d(
            sample_pareto_frontier,
            objective_x="wns_ps",
            objective_y="hot_ratio",
        )

        ax = fig.get_axes()[0]
        x_label = ax.get_xlabel()
        y_label = ax.get_ylabel()

        # Check that labels include objective names
        assert "wns_ps" in x_label
        assert "hot_ratio" in y_label

        # Check that labels include units
        assert "ps" in x_label
        assert "ratio" in y_label

        # Check that labels include optimization direction indicators
        assert "↑" in x_label or "↓" in x_label  # WNS maximize (less negative)
        assert "↑" in y_label or "↓" in y_label  # hot_ratio minimize

        plt.close(fig)

    def test_plot_highlights_pareto_optimal_points(
        self, sample_pareto_frontier: ParetoFrontier
    ) -> None:
        """Test that Pareto-optimal points are highlighted."""
        fig = plot_pareto_frontier_2d(
            sample_pareto_frontier,
            objective_x="wns_ps",
            objective_y="hot_ratio",
        )

        ax = fig.get_axes()[0]

        # Get collections (scatter plots)
        collections = ax.collections

        # Should have at least 2 collections: dominated and Pareto-optimal
        assert len(collections) >= 2

        # Check that there are different visual styles
        # (Pareto points should be highlighted with different color/size/marker)
        colors = [c.get_facecolors() for c in collections if len(c.get_facecolors()) > 0]
        assert len(colors) >= 2  # At least 2 different colors

        plt.close(fig)

    def test_plot_includes_legend(self, sample_pareto_frontier: ParetoFrontier) -> None:
        """Test that plot includes a legend."""
        fig = plot_pareto_frontier_2d(
            sample_pareto_frontier,
            objective_x="wns_ps",
            objective_y="hot_ratio",
        )

        ax = fig.get_axes()[0]
        legend = ax.get_legend()

        assert legend is not None
        # Legend should have entries for Pareto-optimal and dominated points
        assert len(legend.get_texts()) >= 2

        plt.close(fig)

    def test_plot_includes_title(self, sample_pareto_frontier: ParetoFrontier) -> None:
        """Test that plot includes a title."""
        fig = plot_pareto_frontier_2d(
            sample_pareto_frontier,
            objective_x="wns_ps",
            objective_y="hot_ratio",
        )

        ax = fig.get_axes()[0]
        title = ax.get_title()

        assert title != ""
        assert "Pareto" in title
        assert "wns_ps" in title
        assert "hot_ratio" in title

        plt.close(fig)

    def test_custom_title(self, sample_pareto_frontier: ParetoFrontier) -> None:
        """Test that custom title is used when provided."""
        custom_title = "Custom Pareto Analysis"
        fig = plot_pareto_frontier_2d(
            sample_pareto_frontier,
            objective_x="wns_ps",
            objective_y="hot_ratio",
            title=custom_title,
        )

        ax = fig.get_axes()[0]
        assert ax.get_title() == custom_title

        plt.close(fig)

    def test_custom_figsize(self, sample_pareto_frontier: ParetoFrontier) -> None:
        """Test that custom figure size is applied."""
        figsize = (12, 10)
        fig = plot_pareto_frontier_2d(
            sample_pareto_frontier,
            objective_x="wns_ps",
            objective_y="hot_ratio",
            figsize=figsize,
        )

        # Get figure size in inches
        actual_size = fig.get_size_inches()
        assert abs(actual_size[0] - figsize[0]) < 0.1
        assert abs(actual_size[1] - figsize[1]) < 0.1

        plt.close(fig)

    def test_custom_dpi(self, sample_pareto_frontier: ParetoFrontier) -> None:
        """Test that custom DPI is applied."""
        dpi = 200
        fig = plot_pareto_frontier_2d(
            sample_pareto_frontier,
            objective_x="wns_ps",
            objective_y="hot_ratio",
            dpi=dpi,
        )

        assert fig.dpi == dpi

        plt.close(fig)

    def test_invalid_objective_x_raises_error(
        self, sample_pareto_frontier: ParetoFrontier
    ) -> None:
        """Test that invalid x objective raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            plot_pareto_frontier_2d(
                sample_pareto_frontier,
                objective_x="invalid_objective",
                objective_y="hot_ratio",
            )

    def test_invalid_objective_y_raises_error(
        self, sample_pareto_frontier: ParetoFrontier
    ) -> None:
        """Test that invalid y objective raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            plot_pareto_frontier_2d(
                sample_pareto_frontier,
                objective_x="wns_ps",
                objective_y="invalid_objective",
            )

    def test_too_few_trials_raises_error(self) -> None:
        """Test that fewer than 2 trials raises ValueError."""
        # Create frontier with only 1 trial
        single_trial = ParetoTrial(
            case_name="case_0",
            trial_result=None,  # type: ignore
            objective_values={"wns_ps": -100, "hot_ratio": 0.1},
            is_pareto_optimal=True,
        )

        frontier = ParetoFrontier(
            objectives=[TIMING_OBJECTIVE, CONGESTION_OBJECTIVE],
            all_trials=[single_trial],
            pareto_optimal_trials=[single_trial],
            dominated_trials=[],
        )

        with pytest.raises(ValueError, match="at least 2 trials"):
            plot_pareto_frontier_2d(frontier, "wns_ps", "hot_ratio")


class TestSaveParetoPlot:
    """Tests for saving Pareto plots to file."""

    def test_save_plot_to_png(self, sample_pareto_frontier: ParetoFrontier) -> None:
        """Test saving plot to PNG file."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "pareto.png"

            fig = plot_pareto_frontier_2d(
                sample_pareto_frontier,
                objective_x="wns_ps",
                objective_y="hot_ratio",
            )

            save_pareto_plot(fig, output_path, format="png")

            # Verify file was created
            assert output_path.exists()
            assert output_path.stat().st_size > 0

            plt.close(fig)

    def test_save_plot_to_pdf(self, sample_pareto_frontier: ParetoFrontier) -> None:
        """Test saving plot to PDF file."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "pareto.pdf"

            fig = plot_pareto_frontier_2d(
                sample_pareto_frontier,
                objective_x="wns_ps",
                objective_y="hot_ratio",
            )

            save_pareto_plot(fig, output_path, format="pdf")

            # Verify file was created
            assert output_path.exists()
            assert output_path.stat().st_size > 0

            plt.close(fig)

    def test_save_creates_parent_directories(
        self, sample_pareto_frontier: ParetoFrontier
    ) -> None:
        """Test that saving creates parent directories if needed."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "subdir1" / "subdir2" / "pareto.png"

            fig = plot_pareto_frontier_2d(
                sample_pareto_frontier,
                objective_x="wns_ps",
                objective_y="hot_ratio",
            )

            save_pareto_plot(fig, output_path)

            # Verify file and directories were created
            assert output_path.exists()
            assert output_path.parent.exists()

            plt.close(fig)


class TestGenerateParetoVisualization:
    """Tests for batch Pareto visualization generation."""

    def test_generate_single_plot_pair(
        self, sample_pareto_frontier: ParetoFrontier
    ) -> None:
        """Test generating a single plot for specified objective pair."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            plots = generate_pareto_visualization(
                sample_pareto_frontier,
                output_dir,
                objective_pairs=[("wns_ps", "hot_ratio")],
            )

            # Verify one plot was generated
            assert len(plots) == 1
            assert plots[0].exists()
            assert "wns_ps" in plots[0].name
            assert "hot_ratio" in plots[0].name

    def test_generate_all_objective_combinations(
        self, sample_trial_results: list[TrialResult]
    ) -> None:
        """Test generating plots for all objective combinations."""
        # Create frontier with 3 objectives
        objectives = [
            TIMING_OBJECTIVE,
            CONGESTION_OBJECTIVE,
            ObjectiveSpec(
                name="area_um2",
                metric_path=["area", "total_area_um2"],
                minimize=True,
            ),
        ]

        # Add area metric to trial results
        for trial in sample_trial_results:
            with open(trial.artifacts.metrics_json) as f:
                metrics = json.load(f)
            metrics["area"] = {"total_area_um2": 1000.0}
            with open(trial.artifacts.metrics_json, "w") as f:
                json.dump(metrics, f)

        frontier = compute_pareto_frontier(sample_trial_results, objectives)

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Generate all combinations (should be 3 choose 2 = 3 plots)
            plots = generate_pareto_visualization(frontier, output_dir)

            # Should generate 3 plots: timing-congestion, timing-area, congestion-area
            assert len(plots) == 3

            # Verify all plots exist
            for plot_path in plots:
                assert plot_path.exists()
                assert plot_path.suffix == ".png"

    def test_output_directory_creation(
        self, sample_pareto_frontier: ParetoFrontier
    ) -> None:
        """Test that output directory is created if it doesn't exist."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "visualizations" / "pareto"

            assert not output_dir.exists()

            generate_pareto_visualization(
                sample_pareto_frontier,
                output_dir,
                objective_pairs=[("wns_ps", "hot_ratio")],
            )

            assert output_dir.exists()

    def test_multiple_objective_pairs(
        self, sample_trial_results: list[TrialResult]
    ) -> None:
        """Test generating multiple specific objective pair plots."""
        # Create frontier with 3 objectives
        objectives = [
            TIMING_OBJECTIVE,
            CONGESTION_OBJECTIVE,
            ObjectiveSpec(
                name="area_um2", metric_path=["area", "total_area_um2"], minimize=True
            ),
        ]

        # Add area metric
        for trial in sample_trial_results:
            with open(trial.artifacts.metrics_json) as f:
                metrics = json.load(f)
            metrics["area"] = {"total_area_um2": 1000.0}
            with open(trial.artifacts.metrics_json, "w") as f:
                json.dump(metrics, f)

        frontier = compute_pareto_frontier(sample_trial_results, objectives)

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            plots = generate_pareto_visualization(
                frontier,
                output_dir,
                objective_pairs=[
                    ("wns_ps", "hot_ratio"),
                    ("wns_ps", "area_um2"),
                ],
            )

            assert len(plots) == 2
            assert all(p.exists() for p in plots)

    def test_too_few_objectives_raises_error(self) -> None:
        """Test that frontier with < 2 objectives raises error."""
        single_objective = [TIMING_OBJECTIVE]

        frontier = ParetoFrontier(
            objectives=single_objective,
            all_trials=[],
            pareto_optimal_trials=[],
            dominated_trials=[],
        )

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with pytest.raises(ValueError, match="at least 2 objectives"):
                generate_pareto_visualization(frontier, output_dir)


class TestEndToEndVisualization:
    """End-to-end tests for complete visualization workflow."""

    def test_complete_workflow(self, sample_trial_results: list[TrialResult]) -> None:
        """Test complete workflow from trials to visualization."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "study_artifacts" / "pareto"

            # Step 1: Compute Pareto frontier
            objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
            frontier = compute_pareto_frontier(sample_trial_results, objectives)

            # Verify frontier was computed
            assert len(frontier.pareto_optimal_trials) == 3
            assert len(frontier.dominated_trials) == 2

            # Step 2: Generate visualization
            plots = generate_pareto_visualization(
                frontier, output_dir, objective_pairs=[("wns_ps", "hot_ratio")]
            )

            # Step 3: Verify plot was generated
            assert len(plots) == 1
            assert plots[0].exists()

            # Verify plot has meaningful content (file size > 1KB)
            assert plots[0].stat().st_size > 1024

    def test_visualization_clearly_shows_tradeoff(
        self, sample_pareto_frontier: ParetoFrontier
    ) -> None:
        """Test that visualization clearly shows trade-off between objectives."""
        fig = plot_pareto_frontier_2d(
            sample_pareto_frontier,
            objective_x="wns_ps",
            objective_y="hot_ratio",
        )

        ax = fig.get_axes()[0]

        # Verify axes are labeled
        assert ax.get_xlabel() != ""
        assert ax.get_ylabel() != ""

        # Verify there are data points
        collections = ax.collections
        assert len(collections) > 0

        # Verify legend exists to distinguish Pareto vs dominated
        legend = ax.get_legend()
        assert legend is not None

        # Verify title indicates this is a Pareto analysis
        assert "Pareto" in ax.get_title()

        plt.close(fig)
