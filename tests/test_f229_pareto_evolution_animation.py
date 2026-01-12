"""Tests for F229: Generate Pareto frontier evolution animation across stages."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from PIL import Image

from src.controller.pareto import (
    CONGESTION_OBJECTIVE,
    TIMING_OBJECTIVE,
    ParetoFrontier,
    compute_pareto_frontier,
)
from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult
from src.visualization.pareto_plot import (
    create_pareto_evolution_animation,
    generate_pareto_evolution_animation,
    generate_pareto_frontier_per_stage,
)


@pytest.fixture
def stage_trial_results(tmp_path: Path) -> list[list[TrialResult]]:
    """Create sample trial results for 3 stages with evolving Pareto frontiers."""
    stages = []

    # Stage 0: Initial trials with poor performance
    stage_0_cases = [
        ("stage_0_case_0", -200, 0.40),  # Poor timing, high congestion
        ("stage_0_case_1", -180, 0.35),  # Slightly better
        ("stage_0_case_2", -150, 0.30),  # Better timing
        ("stage_0_case_3", -250, 0.50),  # Dominated
    ]

    # Stage 1: Improved trials with better trade-offs
    stage_1_cases = [
        ("stage_1_case_0", -120, 0.25),  # Much better timing
        ("stage_1_case_1", -100, 0.20),  # Even better
        ("stage_1_case_2", -80, 0.18),  # Best so far
        ("stage_1_case_3", -140, 0.30),  # Dominated
    ]

    # Stage 2: Optimized trials achieving Pareto frontier
    stage_2_cases = [
        ("stage_2_case_0", -50, 0.12),  # Excellent timing
        ("stage_2_case_1", -30, 0.10),  # Near-optimal
        ("stage_2_case_2", -20, 0.08),  # Best achievable
        ("stage_2_case_3", -60, 0.15),  # Still good
    ]

    all_stage_cases = [stage_0_cases, stage_1_cases, stage_2_cases]

    for stage_idx, stage_cases in enumerate(all_stage_cases):
        stage_trials = []

        for trial_idx, (case_name, wns, hot_ratio) in enumerate(stage_cases):
            # Create metrics file
            metrics_dir = tmp_path / f"stage_{stage_idx}" / case_name
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
                study_name="multi_stage_study",
                case_name=case_name,
                stage_index=stage_idx,
                trial_index=trial_idx,
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

            stage_trials.append(trial)

        stages.append(stage_trials)

    return stages


@pytest.fixture
def stage_frontiers(stage_trial_results: list[list[TrialResult]]) -> list[ParetoFrontier]:
    """Create Pareto frontiers for each stage."""
    objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
    frontiers = []

    for stage_trials in stage_trial_results:
        frontier = compute_pareto_frontier(stage_trials, objectives)
        frontiers.append(frontier)

    return frontiers


class TestParetoEvolutionAnimationF229:
    """Tests for F229 verification steps."""

    def test_step_1_run_multi_stage_study_with_pareto_frontier_tracking(
        self, stage_trial_results: list[list[TrialResult]]
    ) -> None:
        """Step 1: Run multi-stage study with Pareto frontier tracking."""
        # Verify we have 3 stages
        assert len(stage_trial_results) == 3

        # Verify each stage has trials
        for stage_idx, stage_trials in enumerate(stage_trial_results):
            assert len(stage_trials) >= 3, f"Stage {stage_idx} should have at least 3 trials"

            # Verify each trial has metrics
            for trial in stage_trials:
                assert trial.success
                assert trial.artifacts.metrics_json.exists()

                # Load and verify metrics structure
                with open(trial.artifacts.metrics_json) as f:
                    metrics = json.load(f)
                assert "timing" in metrics
                assert "congestion" in metrics
                assert "wns_ps" in metrics["timing"]
                assert "hot_ratio" in metrics["congestion"]

    def test_step_2_capture_pareto_frontier_snapshot_per_stage(
        self, stage_frontiers: list[ParetoFrontier]
    ) -> None:
        """Step 2: Capture Pareto frontier snapshot per stage."""
        # Verify we have frontiers for all 3 stages
        assert len(stage_frontiers) == 3

        # Verify each frontier has computed optimal and dominated trials
        for stage_idx, frontier in enumerate(stage_frontiers):
            assert len(frontier.all_trials) >= 3, f"Stage {stage_idx} has trials"
            assert len(frontier.pareto_optimal_trials) >= 1, f"Stage {stage_idx} has Pareto-optimal trials"

            # Verify frontier has correct objectives
            obj_names = {obj.name for obj in frontier.objectives}
            assert "wns_ps" in obj_names
            assert "hot_ratio" in obj_names

        # Verify improvement across stages (first stage should be worse than last)
        stage_0_best_wns = max(
            trial.objective_values["wns_ps"]
            for trial in stage_frontiers[0].pareto_optimal_trials
        )
        stage_2_best_wns = max(
            trial.objective_values["wns_ps"]
            for trial in stage_frontiers[2].pareto_optimal_trials
        )

        # Better WNS means less negative (closer to 0)
        assert stage_2_best_wns > stage_0_best_wns, "Final stage should have better timing"

    def test_step_3_generate_pareto_frontier_stage_n_png_for_each_stage(
        self, stage_frontiers: list[ParetoFrontier]
    ) -> None:
        """Step 3: Generate pareto_frontier_stage_N.png for each stage."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Generate plots for each stage
            stage_plots = generate_pareto_frontier_per_stage(
                stage_frontiers=stage_frontiers,
                objective_x="wns_ps",
                objective_y="hot_ratio",
                output_dir=output_dir,
            )

            # Verify correct number of plots generated
            assert len(stage_plots) == 3

            # Verify each plot exists and has correct filename
            for stage_idx, plot_path in enumerate(stage_plots):
                assert plot_path.exists()
                assert plot_path.suffix == ".png"
                assert f"stage_{stage_idx}" in plot_path.name
                assert plot_path.stat().st_size > 0

            # Verify filenames follow pattern
            expected_names = [
                "pareto_frontier_stage_0.png",
                "pareto_frontier_stage_1.png",
                "pareto_frontier_stage_2.png",
            ]
            actual_names = [p.name for p in stage_plots]
            assert actual_names == expected_names

    def test_step_4_create_animated_gif_from_stage_snapshots(
        self, stage_frontiers: list[ParetoFrontier]
    ) -> None:
        """Step 4: Create animated GIF from stage snapshots."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # First generate stage plots
            stage_plots = generate_pareto_frontier_per_stage(
                stage_frontiers=stage_frontiers,
                objective_x="wns_ps",
                objective_y="hot_ratio",
                output_dir=output_dir,
            )

            # Create animation from stage plots
            animation_path = output_dir / "test_animation.gif"
            result_path = create_pareto_evolution_animation(
                stage_plot_paths=stage_plots,
                output_path=animation_path,
                duration_ms=1000,
                loop=0,
            )

            # Verify animation was created
            assert result_path == animation_path
            assert animation_path.exists()
            assert animation_path.suffix == ".gif"
            assert animation_path.stat().st_size > 0

            # Verify it's a valid GIF
            img = Image.open(animation_path)
            assert img.format == "GIF"
            assert img.is_animated

    def test_step_5_export_as_pareto_evolution_gif(
        self, stage_frontiers: list[ParetoFrontier]
    ) -> None:
        """Step 5: Export as pareto_evolution.gif."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Use convenience function to generate complete animation
            animation_path, stage_plots = generate_pareto_evolution_animation(
                stage_frontiers=stage_frontiers,
                objective_x="wns_ps",
                objective_y="hot_ratio",
                output_dir=output_dir,
                animation_filename="pareto_evolution.gif",
            )

            # Verify animation exists with correct name
            assert animation_path.exists()
            assert animation_path.name == "pareto_evolution.gif"
            assert animation_path.stat().st_size > 0

            # Verify stage plots were also created
            assert len(stage_plots) == 3
            for plot_path in stage_plots:
                assert plot_path.exists()

    def test_step_6_verify_animation_shows_frontier_evolution_over_time(
        self, stage_frontiers: list[ParetoFrontier]
    ) -> None:
        """Step 6: Verify animation shows frontier evolution over time."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Generate animation
            animation_path, stage_plots = generate_pareto_evolution_animation(
                stage_frontiers=stage_frontiers,
                objective_x="wns_ps",
                objective_y="hot_ratio",
                output_dir=output_dir,
            )

            # Load and verify animation properties
            img = Image.open(animation_path)

            # Verify it's an animated GIF
            assert img.format == "GIF"
            assert img.is_animated

            # Verify number of frames matches number of stages
            frame_count = 0
            try:
                while True:
                    img.seek(frame_count)
                    frame_count += 1
            except EOFError:
                pass

            assert frame_count == 3, "Animation should have 3 frames (one per stage)"

            # Verify animation loops infinitely
            assert img.info.get("loop", 1) == 0, "Animation should loop infinitely"


class TestParetoEvolutionEdgeCases:
    """Edge case tests for Pareto evolution animation."""

    def test_empty_stage_frontiers_raises_error(self) -> None:
        """Test that empty stage list raises ValueError."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with pytest.raises(ValueError, match="cannot be empty"):
                generate_pareto_frontier_per_stage(
                    stage_frontiers=[],
                    objective_x="wns_ps",
                    objective_y="hot_ratio",
                    output_dir=output_dir,
                )

    def test_single_stage_creates_single_frame_animation(
        self, stage_frontiers: list[ParetoFrontier]
    ) -> None:
        """Test that single stage creates valid single-frame animation."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Use only first stage
            single_stage = [stage_frontiers[0]]

            animation_path, stage_plots = generate_pareto_evolution_animation(
                stage_frontiers=single_stage,
                objective_x="wns_ps",
                objective_y="hot_ratio",
                output_dir=output_dir,
            )

            assert animation_path.exists()
            assert len(stage_plots) == 1

            # Verify it's still a valid GIF (single frame)
            img = Image.open(animation_path)
            assert img.format == "GIF"

    def test_many_stages_creates_animation(
        self, stage_trial_results: list[list[TrialResult]]
    ) -> None:
        """Test that many stages (10+) creates valid animation."""
        from src.controller.pareto import compute_pareto_frontier

        # Create 10 stages by duplicating and slightly modifying existing stages
        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        many_frontiers = []

        for i in range(10):
            # Reuse trial results (in real scenario, these would be different)
            stage_idx = i % len(stage_trial_results)
            trials = stage_trial_results[stage_idx]
            frontier = compute_pareto_frontier(trials, objectives)
            many_frontiers.append(frontier)

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            animation_path, stage_plots = generate_pareto_evolution_animation(
                stage_frontiers=many_frontiers,
                objective_x="wns_ps",
                objective_y="hot_ratio",
                output_dir=output_dir,
            )

            assert animation_path.exists()
            assert len(stage_plots) == 10

            # Verify animation has 10 frames
            img = Image.open(animation_path)
            frame_count = 0
            try:
                while True:
                    img.seek(frame_count)
                    frame_count += 1
            except EOFError:
                pass

            assert frame_count == 10

    def test_custom_duration_and_loop_settings(
        self, stage_frontiers: list[ParetoFrontier]
    ) -> None:
        """Test custom duration and loop settings."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Generate with custom settings
            animation_path, _ = generate_pareto_evolution_animation(
                stage_frontiers=stage_frontiers,
                objective_x="wns_ps",
                objective_y="hot_ratio",
                output_dir=output_dir,
                duration_ms=500,  # Custom duration
                loop=3,  # Loop 3 times
            )

            assert animation_path.exists()

            # Verify custom settings were applied
            img = Image.open(animation_path)
            assert img.info.get("loop") == 3

    def test_custom_animation_filename(
        self, stage_frontiers: list[ParetoFrontier]
    ) -> None:
        """Test custom animation filename."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            custom_name = "my_custom_animation.gif"
            animation_path, _ = generate_pareto_evolution_animation(
                stage_frontiers=stage_frontiers,
                objective_x="wns_ps",
                objective_y="hot_ratio",
                output_dir=output_dir,
                animation_filename=custom_name,
            )

            assert animation_path.name == custom_name
            assert animation_path.exists()

    def test_missing_stage_plot_file_raises_error(self) -> None:
        """Test that missing stage plot file raises ValueError."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create paths to non-existent files
            fake_paths = [
                output_dir / "stage_0.png",
                output_dir / "stage_1.png",
                output_dir / "stage_2.png",
            ]

            with pytest.raises(ValueError, match="not found"):
                create_pareto_evolution_animation(
                    stage_plot_paths=fake_paths,
                    output_path=output_dir / "animation.gif",
                )

    def test_output_directory_created_if_not_exists(
        self, stage_frontiers: list[ParetoFrontier]
    ) -> None:
        """Test that output directory is created if it doesn't exist."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "nested" / "output" / "dir"

            assert not output_dir.exists()

            animation_path, _ = generate_pareto_evolution_animation(
                stage_frontiers=stage_frontiers,
                objective_x="wns_ps",
                objective_y="hot_ratio",
                output_dir=output_dir,
            )

            assert output_dir.exists()
            assert animation_path.exists()


class TestF229Integration:
    """Integration test for complete F229 workflow."""

    def test_complete_f229_workflow(
        self, stage_trial_results: list[list[TrialResult]]
    ) -> None:
        """Test complete workflow from trial results to animation."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "pareto_evolution"

            # Step 1: Compute Pareto frontiers for each stage
            objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
            stage_frontiers = []

            for stage_trials in stage_trial_results:
                frontier = compute_pareto_frontier(stage_trials, objectives)
                stage_frontiers.append(frontier)

            # Verify frontiers computed
            assert len(stage_frontiers) == 3

            # Step 2: Generate animation
            animation_path, stage_plots = generate_pareto_evolution_animation(
                stage_frontiers=stage_frontiers,
                objective_x="wns_ps",
                objective_y="hot_ratio",
                output_dir=output_dir,
                animation_filename="pareto_evolution.gif",
                duration_ms=1000,
                loop=0,
            )

            # Step 3: Verify all outputs
            assert animation_path.exists()
            assert animation_path.name == "pareto_evolution.gif"
            assert len(stage_plots) == 3

            # Verify stage plots
            for i, plot_path in enumerate(stage_plots):
                assert plot_path.exists()
                assert f"stage_{i}" in plot_path.name

            # Verify animation is valid
            img = Image.open(animation_path)
            assert img.format == "GIF"
            assert img.is_animated

            # Count frames
            frame_count = 0
            try:
                while True:
                    img.seek(frame_count)
                    frame_count += 1
            except EOFError:
                pass

            assert frame_count == 3

            # Verify demonstrates evolution
            # (Check that stage 2 has better metrics than stage 0)
            stage_0_best_wns = max(
                trial.objective_values["wns_ps"]
                for trial in stage_frontiers[0].pareto_optimal_trials
            )
            stage_2_best_wns = max(
                trial.objective_values["wns_ps"]
                for trial in stage_frontiers[2].pareto_optimal_trials
            )

            assert stage_2_best_wns > stage_0_best_wns, "Should show improvement over time"
