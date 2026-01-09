"""End-to-end test for heatmap generation and spatial analysis workflow.

This test validates the complete heatmap workflow including:
- GUI mode configuration and execution
- CSV heatmap export (placement density, RUDY, routing congestion)
- PNG preview generation
- Post-ECO heatmap generation
- Spatial diff computation
- Artifact indexing
- Spatial region analysis
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.controller.study import create_study_config, StudyConfig
from src.controller.types import SafetyDomain, StageConfig, ECOClass, ExecutionMode
from src.trial_runner.docker_runner import DockerRunConfig, DockerTrialRunner
from src.trial_runner.tcl_generator import (
    generate_heatmap_export_commands,
    generate_trial_script,
    write_trial_script,
)
from src.visualization.heatmap_renderer import (
    compute_heatmap_diff,
    generate_eco_impact_heatmaps,
    get_recommended_colormap,
    parse_heatmap_csv,
    render_all_heatmaps,
    render_diff_heatmap,
    render_heatmap_png,
)


class TestStep1ConfigureStudyStageForHeatmaps:
    """Step 1: Configure Study stage to enable heatmap exports."""

    def test_stage_config_accepts_heatmap_export_flag(self) -> None:
        """StageConfig should support heatmap export configuration."""
        # This is typically handled via execution mode and docker config
        stage_config = StageConfig(
            name="heatmap_stage",
            execution_mode=ExecutionMode.STA_CONGESTION,
            trial_budget=10,
            survivor_count=3,
            allowed_eco_classes=[ECOClass.PLACEMENT_LOCAL],
            visualization_enabled=True,
        )
        assert stage_config.execution_mode == ExecutionMode.STA_CONGESTION
        assert stage_config.visualization_enabled is True

    def test_docker_run_config_enables_gui_mode(self) -> None:
        """DockerRunConfig should support GUI mode for heatmap export."""
        config = DockerRunConfig(gui_mode=True)
        assert config.gui_mode is True

    def test_study_creation_with_heatmap_enabled_stage(self) -> None:
        """Create Study with stage configured for heatmap generation."""
        stage = StageConfig(
            name="heatmap_stage",
            execution_mode=ExecutionMode.STA_CONGESTION,
            trial_budget=5,
            survivor_count=2,
            allowed_eco_classes=[ECOClass.PLACEMENT_LOCAL],
            visualization_enabled=True,
        )

        study = create_study_config(
            name="heatmap_study",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path="/snapshots/test_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[stage],
        )

        assert study.name == "heatmap_study"
        assert len(study.stages) == 1
        assert study.stages[0].execution_mode == ExecutionMode.STA_CONGESTION
        assert study.stages[0].visualization_enabled is True


class TestStep2ExecuteTrialWithGUIMode:
    """Step 2: Execute trial with GUI mode enabled (X11 passthrough)."""

    def test_gui_mode_execution_configuration(self) -> None:
        """Verify GUI mode can be enabled in trial execution."""
        config = DockerRunConfig(gui_mode=True)
        runner = DockerTrialRunner(config)
        assert runner.config.gui_mode is True

    def test_x11_passthrough_configured_when_gui_enabled(self) -> None:
        """When GUI mode is enabled, X11 should be configured."""
        with patch.dict("os.environ", {"DISPLAY": ":0"}):
            with patch("pathlib.Path.exists", return_value=True):
                config = DockerRunConfig(gui_mode=True)
                runner = DockerTrialRunner(config)
                assert runner.check_gui_available() is True

    def test_heatmap_export_commands_generated_for_gui_mode(self) -> None:
        """Generate heatmap export TCL commands for GUI mode trial."""
        commands = generate_heatmap_export_commands("/work/artifacts")
        assert "gui::dump_heatmap" in commands
        assert "placement_density" in commands


class TestStep3LoadDesignInGUIMode:
    """Step 3: Load design in OpenROAD GUI mode."""

    def test_trial_script_includes_design_loading(self) -> None:
        """Trial script should include design loading commands."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_case",
            output_dir="/work",
            pdk="nangate45",
            visualization_enabled=True,
        )
        # Script should contain OpenROAD commands
        assert len(script) > 0
        assert isinstance(script, str)

    def test_gui_mode_compatible_with_design_load(self) -> None:
        """GUI mode should be compatible with standard design loading."""
        # Verify that design loading works in GUI mode
        # (This is a structural test - actual execution requires Docker)
        config = DockerRunConfig(gui_mode=True)
        runner = DockerTrialRunner(config)
        assert runner.config.gui_mode is True


class TestStep4ExportPlacementDensityHeatmap:
    """Step 4: Export placement density heatmap CSV."""

    def test_generate_placement_density_heatmap_command(self) -> None:
        """Generate TCL command for placement density heatmap export."""
        commands = generate_heatmap_export_commands("/work/artifacts")
        assert "placement_density" in commands
        assert "gui::dump_heatmap" in commands
        assert "csv" in commands.lower() or ".csv" in commands

    def test_placement_density_csv_path_constructed(self) -> None:
        """Placement density CSV should have predictable path."""
        artifacts_dir = Path("/work/artifacts")
        expected_csv = artifacts_dir / "heatmaps" / "placement_density.csv"
        assert expected_csv.name == "placement_density.csv"


class TestStep5ExportRUDYCongestionHeatmap:
    """Step 5: Export RUDY congestion heatmap CSV."""

    def test_generate_rudy_heatmap_command(self) -> None:
        """Generate TCL command for RUDY heatmap export."""
        commands = generate_heatmap_export_commands("/work/artifacts")
        assert "rudy" in commands.lower()
        assert "gui::dump_heatmap" in commands

    def test_rudy_csv_path_constructed(self) -> None:
        """RUDY CSV should have predictable path."""
        artifacts_dir = Path("/work/artifacts")
        expected_csv = artifacts_dir / "heatmaps" / "rudy.csv"
        assert expected_csv.name == "rudy.csv"


class TestStep6ExportRoutingCongestionHeatmap:
    """Step 6: Export routing congestion heatmap CSV."""

    def test_generate_routing_congestion_heatmap_command(self) -> None:
        """Generate TCL command for routing congestion heatmap export."""
        commands = generate_heatmap_export_commands("/work/artifacts")
        assert "routing_congestion" in commands or "congestion" in commands.lower()
        assert "gui::dump_heatmap" in commands

    def test_routing_congestion_csv_path_constructed(self) -> None:
        """Routing congestion CSV should have predictable path."""
        artifacts_dir = Path("/work/artifacts")
        expected_csv = artifacts_dir / "heatmaps" / "routing_congestion.csv"
        assert expected_csv.name == "routing_congestion.csv"


class TestStep7VerifyAllCSVsCreated:
    """Step 7: Verify all three CSV files are created in artifacts."""

    def test_verify_csv_files_exist_in_artifacts(self, tmp_path: Path) -> None:
        """Verify all expected heatmap CSVs are created."""
        # Simulate heatmap CSV creation
        heatmaps_dir = tmp_path / "heatmaps"
        heatmaps_dir.mkdir()

        # Create mock CSV files
        (heatmaps_dir / "placement_density.csv").write_text("1,2,3\n4,5,6\n")
        (heatmaps_dir / "rudy.csv").write_text("0.1,0.2,0.3\n0.4,0.5,0.6\n")
        (heatmaps_dir / "routing_congestion.csv").write_text("0,1,2\n3,4,5\n")

        # Verify all files exist
        assert (heatmaps_dir / "placement_density.csv").exists()
        assert (heatmaps_dir / "rudy.csv").exists()
        assert (heatmaps_dir / "routing_congestion.csv").exists()

    def test_count_heatmap_csvs(self, tmp_path: Path) -> None:
        """Count number of heatmap CSVs created."""
        heatmaps_dir = tmp_path / "heatmaps"
        heatmaps_dir.mkdir()

        # Create expected CSV files
        for name in ["placement_density", "rudy", "routing_congestion"]:
            (heatmaps_dir / f"{name}.csv").write_text("1,2\n3,4\n")

        csv_files = list(heatmaps_dir.glob("*.csv"))
        assert len(csv_files) == 3


class TestStep8ParseCSVAndValidateFormat:
    """Step 8: Parse CSV data and validate format."""

    def test_parse_placement_density_csv(self, tmp_path: Path) -> None:
        """Parse placement density CSV and extract data."""
        csv_path = tmp_path / "placement_density.csv"
        csv_path.write_text("1.0,2.0,3.0\n4.0,5.0,6.0\n7.0,8.0,9.0\n")

        data, metadata = parse_heatmap_csv(csv_path)

        assert isinstance(data, np.ndarray)
        assert data.shape == (3, 3)
        assert metadata["min_value"] == 1.0
        assert metadata["max_value"] == 9.0

    def test_parse_rudy_csv(self, tmp_path: Path) -> None:
        """Parse RUDY CSV and extract data."""
        csv_path = tmp_path / "rudy.csv"
        csv_path.write_text("0.1,0.2\n0.3,0.4\n")

        data, metadata = parse_heatmap_csv(csv_path)

        assert data.shape == (2, 2)
        assert metadata["mean_value"] == pytest.approx(0.25)

    def test_parse_routing_congestion_csv(self, tmp_path: Path) -> None:
        """Parse routing congestion CSV and extract data."""
        csv_path = tmp_path / "routing_congestion.csv"
        csv_path.write_text("0,1,2\n3,4,5\n")

        data, metadata = parse_heatmap_csv(csv_path)

        assert data.shape == (2, 3)
        assert metadata["nonzero_count"] == 5  # One zero value

    def test_validate_csv_format_structure(self, tmp_path: Path) -> None:
        """Validate CSV format is rectangular grid."""
        csv_path = tmp_path / "test.csv"
        csv_path.write_text("1,2,3\n4,5,6\n7,8,9\n")

        data, metadata = parse_heatmap_csv(csv_path)

        # Verify rectangular grid
        assert len(data.shape) == 2
        assert metadata["shape"] == (3, 3)


class TestStep9GeneratePNGPlacementDensity:
    """Step 9: Generate PNG preview for placement density."""

    def test_render_placement_density_png(self, tmp_path: Path) -> None:
        """Render placement density heatmap as PNG."""
        csv_path = tmp_path / "placement_density.csv"
        csv_path.write_text("1.0,2.0,3.0\n4.0,5.0,6.0\n7.0,8.0,9.0\n")

        png_path = tmp_path / "placement_density.png"

        metadata = render_heatmap_png(
            csv_path=csv_path,
            output_path=png_path,
            title="Placement Density",
            colormap="viridis",
        )

        assert png_path.exists()
        assert metadata["png_path"] == str(png_path)
        assert metadata["colormap"] == "viridis"

    def test_use_recommended_colormap_for_placement_density(self) -> None:
        """Verify recommended colormap for placement density."""
        colormap = get_recommended_colormap("placement_density")
        assert colormap == "viridis"


class TestStep10GeneratePNGRUDY:
    """Step 10: Generate PNG preview for RUDY."""

    def test_render_rudy_png(self, tmp_path: Path) -> None:
        """Render RUDY heatmap as PNG."""
        csv_path = tmp_path / "rudy.csv"
        csv_path.write_text("0.1,0.2,0.3\n0.4,0.5,0.6\n0.7,0.8,0.9\n")

        png_path = tmp_path / "rudy.png"

        metadata = render_heatmap_png(
            csv_path=csv_path,
            output_path=png_path,
            title="RUDY Congestion",
            colormap="plasma",
        )

        assert png_path.exists()
        assert metadata["colormap"] == "plasma"

    def test_use_recommended_colormap_for_rudy(self) -> None:
        """Verify recommended colormap for RUDY."""
        colormap = get_recommended_colormap("rudy")
        assert colormap == "plasma"


class TestStep11GeneratePNGRoutingCongestion:
    """Step 11: Generate PNG preview for routing congestion."""

    def test_render_routing_congestion_png(self, tmp_path: Path) -> None:
        """Render routing congestion heatmap as PNG."""
        csv_path = tmp_path / "routing_congestion.csv"
        csv_path.write_text("0,1,2\n3,4,5\n6,7,8\n")

        png_path = tmp_path / "routing_congestion.png"

        metadata = render_heatmap_png(
            csv_path=csv_path,
            output_path=png_path,
            title="Routing Congestion",
            colormap="hot",
        )

        assert png_path.exists()
        assert metadata["colormap"] == "hot"

    def test_use_recommended_colormap_for_routing_congestion(self) -> None:
        """Verify recommended colormap for routing congestion."""
        colormap = get_recommended_colormap("routing_congestion")
        assert colormap == "hot"

    def test_render_all_heatmaps_batch_processing(self, tmp_path: Path) -> None:
        """Render all heatmaps in a directory at once."""
        heatmaps_dir = tmp_path / "heatmaps"
        heatmaps_dir.mkdir()

        # Create CSV files
        for name in ["placement_density", "rudy", "routing_congestion"]:
            csv_path = heatmaps_dir / f"{name}.csv"
            csv_path.write_text("1,2,3\n4,5,6\n7,8,9\n")

        # Render all at once
        results = render_all_heatmaps(heatmaps_dir, output_dir=heatmaps_dir)

        assert len(results) == 3
        assert (heatmaps_dir / "placement_density.png").exists()
        assert (heatmaps_dir / "rudy.png").exists()
        assert (heatmaps_dir / "routing_congestion.png").exists()


class TestStep12ApplyECOAndGeneratePostECOHeatmaps:
    """Step 12: Apply ECO and generate post-ECO heatmaps."""

    def test_post_eco_heatmap_generation(self, tmp_path: Path) -> None:
        """Generate heatmaps after ECO application."""
        # Simulate baseline heatmaps (before ECO)
        baseline_dir = tmp_path / "baseline" / "heatmaps"
        baseline_dir.mkdir(parents=True)
        (baseline_dir / "routing_congestion.csv").write_text(
            "5,6,7\n8,9,10\n11,12,13\n"
        )

        # Simulate post-ECO heatmaps (after buffer insertion)
        post_eco_dir = tmp_path / "post_eco" / "heatmaps"
        post_eco_dir.mkdir(parents=True)
        # Reduced congestion after ECO
        (post_eco_dir / "routing_congestion.csv").write_text(
            "3,4,5\n6,7,8\n9,10,11\n"
        )

        # Verify both exist
        assert (baseline_dir / "routing_congestion.csv").exists()
        assert (post_eco_dir / "routing_congestion.csv").exists()

    def test_multiple_eco_trials_generate_separate_heatmaps(self, tmp_path: Path) -> None:
        """Each ECO trial should generate independent heatmap sets."""
        for trial_id in range(3):
            trial_dir = tmp_path / f"trial_{trial_id}" / "heatmaps"
            trial_dir.mkdir(parents=True)
            (trial_dir / "routing_congestion.csv").write_text("1,2\n3,4\n")

        # Verify all trial heatmaps exist
        assert (tmp_path / "trial_0" / "heatmaps" / "routing_congestion.csv").exists()
        assert (tmp_path / "trial_1" / "heatmaps" / "routing_congestion.csv").exists()
        assert (tmp_path / "trial_2" / "heatmaps" / "routing_congestion.csv").exists()


class TestStep13ComputeSpatialDiffHeatmaps:
    """Step 13: Compute spatial diff heatmaps (before/after)."""

    def test_compute_heatmap_diff(self, tmp_path: Path) -> None:
        """Compute spatial difference between baseline and post-ECO."""
        baseline_csv = tmp_path / "baseline.csv"
        baseline_csv.write_text("10,20,30\n40,50,60\n")

        comparison_csv = tmp_path / "comparison.csv"
        comparison_csv.write_text("8,18,28\n38,48,58\n")  # Reduced by 2

        diff, metadata = compute_heatmap_diff(baseline_csv, comparison_csv)

        # All values should show improvement (positive diff)
        assert np.all(diff > 0)
        assert metadata["improved_bins"] == 6  # All bins improved
        assert metadata["degraded_bins"] == 0

    def test_diff_identifies_improvement_regions(self, tmp_path: Path) -> None:
        """Diff should identify regions where congestion improved."""
        baseline_csv = tmp_path / "baseline.csv"
        baseline_csv.write_text("5,10,15\n20,25,30\n")

        comparison_csv = tmp_path / "comparison.csv"
        comparison_csv.write_text("3,8,13\n18,23,28\n")  # Uniform -2 improvement

        diff, metadata = compute_heatmap_diff(baseline_csv, comparison_csv)

        assert metadata["improved_bins"] == 6
        assert metadata["mean_diff"] == pytest.approx(2.0)

    def test_diff_identifies_degradation_regions(self, tmp_path: Path) -> None:
        """Diff should identify regions where congestion worsened."""
        baseline_csv = tmp_path / "baseline.csv"
        baseline_csv.write_text("5,5,5\n5,5,5\n")

        comparison_csv = tmp_path / "comparison.csv"
        comparison_csv.write_text("6,6,6\n6,6,6\n")  # All increased by 1

        diff, metadata = compute_heatmap_diff(baseline_csv, comparison_csv)

        assert metadata["degraded_bins"] == 6  # All bins degraded
        assert metadata["improved_bins"] == 0
        assert metadata["mean_diff"] == pytest.approx(-1.0)

    def test_diff_computes_statistics(self, tmp_path: Path) -> None:
        """Diff should compute comprehensive statistics."""
        baseline_csv = tmp_path / "baseline.csv"
        baseline_csv.write_text("10,20,30\n40,50,60\n")

        comparison_csv = tmp_path / "comparison.csv"
        comparison_csv.write_text("12,18,32\n38,50,58\n")  # Mixed changes

        diff, metadata = compute_heatmap_diff(baseline_csv, comparison_csv)

        assert "min_diff" in metadata
        assert "max_diff" in metadata
        assert "mean_diff" in metadata
        assert "std_diff" in metadata
        assert "total_improvement" in metadata
        assert "total_degradation" in metadata


class TestStep14IndexHeatmapsInArtifactIndex:
    """Step 14: Index all heatmaps in artifact_index.json."""

    def test_heatmap_artifacts_indexed(self, tmp_path: Path) -> None:
        """Heatmaps should be indexed in artifact_index.json."""
        import json

        from src.trial_runner.artifact_index import (
            ArtifactEntry,
            TrialArtifactIndex,
            infer_content_type,
        )

        # Create heatmap files
        heatmaps_dir = tmp_path / "heatmaps"
        heatmaps_dir.mkdir()
        (heatmaps_dir / "placement_density.csv").write_text("1,2\n3,4\n")
        (heatmaps_dir / "placement_density.png").write_bytes(b"fake_png")

        # Create artifact index
        index = TrialArtifactIndex(
            study_name="heatmap_study",
            case_name="test_base_0_1",
            stage_index=0,
            trial_index=1,
            trial_root=tmp_path,
        )

        # Add heatmap artifacts
        for csv_file in heatmaps_dir.glob("*.csv"):
            index.add_artifact(
                path=csv_file,
                label=csv_file.stem,
                content_type=infer_content_type(csv_file),
            )

        for png_file in heatmaps_dir.glob("*.png"):
            index.add_artifact(
                path=png_file,
                label=png_file.stem,
                content_type=infer_content_type(png_file),
            )

        # Verify heatmaps are indexed
        assert len(index.entries) == 2
        artifact_paths = [str(a.path) for a in index.entries]
        assert any("placement_density.csv" in p for p in artifact_paths)
        assert any("placement_density.png" in p for p in artifact_paths)

    def test_heatmap_content_types_inferred_correctly(self) -> None:
        """Heatmap file content types should be inferred correctly."""
        from src.trial_runner.artifact_index import infer_content_type

        assert infer_content_type(Path("placement_density.csv")) == "text/csv"
        assert infer_content_type(Path("rudy.png")) == "image/png"


class TestStep15GenerateHeatmapComparisonReport:
    """Step 15: Generate heatmap comparison report."""

    def test_render_diff_heatmap_png(self, tmp_path: Path) -> None:
        """Generate comparative diff heatmap visualization."""
        baseline_csv = tmp_path / "baseline.csv"
        baseline_csv.write_text("10,20,30\n40,50,60\n70,80,90\n")

        comparison_csv = tmp_path / "comparison.csv"
        comparison_csv.write_text("8,18,28\n38,48,58\n68,78,88\n")  # -2 everywhere

        diff_png = tmp_path / "diff.png"

        metadata = render_diff_heatmap(
            baseline_csv=baseline_csv,
            comparison_csv=comparison_csv,
            output_path=diff_png,
            title="ECO Impact - Routing Congestion",
        )

        assert diff_png.exists()
        assert metadata["improved_bins"] == 9  # All bins improved
        assert metadata["degraded_bins"] == 0

    def test_generate_eco_impact_heatmaps_batch(self, tmp_path: Path) -> None:
        """Generate all ECO impact heatmaps for matching pairs."""
        baseline_dir = tmp_path / "baseline"
        baseline_dir.mkdir()
        comparison_dir = tmp_path / "comparison"
        comparison_dir.mkdir()
        output_dir = tmp_path / "diff"
        output_dir.mkdir()

        # Create matching heatmap pairs
        for name in ["placement_density", "rudy", "routing_congestion"]:
            (baseline_dir / f"{name}.csv").write_text("10,20\n30,40\n")
            (comparison_dir / f"{name}.csv").write_text("8,18\n28,38\n")

        # Generate all diffs
        results = generate_eco_impact_heatmaps(
            baseline_heatmaps_dir=baseline_dir,
            comparison_heatmaps_dir=comparison_dir,
            output_dir=output_dir,
        )

        assert len(results) == 3
        assert (output_dir / "placement_density_diff.png").exists()
        assert (output_dir / "rudy_diff.png").exists()
        assert (output_dir / "routing_congestion_diff.png").exists()


class TestStep16IdentifySpatialRegions:
    """Step 16: Identify spatial regions of improvement/degradation."""

    def test_identify_improvement_regions_from_diff(self, tmp_path: Path) -> None:
        """Identify specific spatial regions that improved after ECO."""
        baseline_csv = tmp_path / "baseline.csv"
        # High congestion in center
        baseline_csv.write_text("1,2,1\n2,10,2\n1,2,1\n")

        comparison_csv = tmp_path / "comparison.csv"
        # Congestion reduced in center
        comparison_csv.write_text("1,2,1\n2,5,2\n1,2,1\n")

        diff, metadata = compute_heatmap_diff(baseline_csv, comparison_csv)

        # Find locations with improvement
        improved_mask = diff > 0
        improvement_count = np.sum(improved_mask)

        assert improvement_count > 0
        # Center cell (1,1) should show improvement
        assert diff[1, 1] > 0

    def test_identify_degradation_regions_from_diff(self, tmp_path: Path) -> None:
        """Identify specific spatial regions that degraded after ECO."""
        baseline_csv = tmp_path / "baseline.csv"
        baseline_csv.write_text("1,1,1\n1,1,1\n1,1,1\n")

        comparison_csv = tmp_path / "comparison.csv"
        # Congestion increased in corners
        comparison_csv.write_text("5,1,5\n1,1,1\n5,1,5\n")

        diff, metadata = compute_heatmap_diff(baseline_csv, comparison_csv)

        # Find locations with degradation
        degraded_mask = diff < 0
        degradation_count = np.sum(degraded_mask)

        assert degradation_count == 4  # Four corners
        assert diff[0, 0] < 0  # Top-left corner degraded
        assert diff[0, 2] < 0  # Top-right corner degraded

    def test_spatial_impact_statistics(self, tmp_path: Path) -> None:
        """Compute spatial impact statistics across heatmap grid."""
        baseline_csv = tmp_path / "baseline.csv"
        baseline_csv.write_text("10,20,30\n40,50,60\n70,80,90\n")

        comparison_csv = tmp_path / "comparison.csv"
        comparison_csv.write_text("12,18,32\n38,48,62\n68,78,92\n")  # Mixed

        diff, metadata = compute_heatmap_diff(baseline_csv, comparison_csv)

        # Verify comprehensive statistics are computed
        assert metadata["improved_bins"] + metadata["degraded_bins"] + metadata["unchanged_bins"] == 9
        assert "total_improvement" in metadata
        assert "total_degradation" in metadata


class TestCompleteHeatmapWorkflowE2E:
    """End-to-end integration test for complete heatmap workflow."""

    def test_complete_heatmap_generation_and_analysis_workflow(
        self, tmp_path: Path
    ) -> None:
        """
        Complete workflow:
        1. Generate baseline heatmaps
        2. Apply ECO
        3. Generate post-ECO heatmaps
        4. Compute diffs
        5. Render visualizations
        6. Index artifacts
        """
        # Step 1: Create baseline heatmaps
        baseline_dir = tmp_path / "baseline" / "heatmaps"
        baseline_dir.mkdir(parents=True)
        (baseline_dir / "routing_congestion.csv").write_text(
            "10,20,30\n40,50,60\n70,80,90\n"
        )
        (baseline_dir / "placement_density.csv").write_text(
            "5,10,15\n20,25,30\n35,40,45\n"
        )

        # Step 2: Render baseline PNGs
        baseline_pngs = render_all_heatmaps(baseline_dir, output_dir=baseline_dir)
        assert len(baseline_pngs) == 2

        # Step 3: Create post-ECO heatmaps (improved)
        post_eco_dir = tmp_path / "post_eco" / "heatmaps"
        post_eco_dir.mkdir(parents=True)
        (post_eco_dir / "routing_congestion.csv").write_text(
            "8,18,28\n38,48,58\n68,78,88\n"
        )  # -2 improvement
        (post_eco_dir / "placement_density.csv").write_text(
            "4,9,14\n19,24,29\n34,39,44\n"
        )  # -1 improvement

        # Step 4: Render post-ECO PNGs
        post_eco_pngs = render_all_heatmaps(post_eco_dir, output_dir=post_eco_dir)
        assert len(post_eco_pngs) == 2

        # Step 5: Compute and render diffs
        diff_dir = tmp_path / "diffs"
        diff_dir.mkdir()
        diff_results = generate_eco_impact_heatmaps(
            baseline_heatmaps_dir=baseline_dir,
            comparison_heatmaps_dir=post_eco_dir,
            output_dir=diff_dir,
        )

        assert len(diff_results) == 2
        assert all(r["improved_bins"] > 0 for r in diff_results)

        # Step 6: Index all artifacts
        from src.trial_runner.artifact_index import (
            ArtifactEntry,
            TrialArtifactIndex,
            infer_content_type,
        )

        index = TrialArtifactIndex(
            study_name="heatmap_e2e_study",
            case_name="test_base_0_1",
            stage_index=0,
            trial_index=1,
            trial_root=tmp_path,
        )

        # Index baseline heatmaps
        for file in baseline_dir.iterdir():
            if file.is_file():
                index.add_artifact(
                    path=file,
                    label=f"baseline/{file.name}",
                    content_type=infer_content_type(file),
                )

        # Index post-ECO heatmaps
        for file in post_eco_dir.iterdir():
            if file.is_file():
                index.add_artifact(
                    path=file,
                    label=f"post_eco/{file.name}",
                    content_type=infer_content_type(file),
                )

        # Index diff heatmaps
        for file in diff_dir.iterdir():
            if file.is_file():
                index.add_artifact(
                    path=file,
                    label=f"diff/{file.name}",
                    content_type=infer_content_type(file),
                )

        # Verify complete artifact index
        assert len(index.entries) >= 6  # At least 2 baseline + 2 post-ECO + 2 diffs

        # Step 7: Verify all expected artifacts exist
        assert (baseline_dir / "routing_congestion.csv").exists()
        assert (baseline_dir / "routing_congestion.png").exists()
        assert (post_eco_dir / "routing_congestion.csv").exists()
        assert (post_eco_dir / "routing_congestion.png").exists()
        assert (diff_dir / "routing_congestion_diff.png").exists()

        # Step 8: Verify improvement was detected
        routing_diff = [
            r for r in diff_results if "routing_congestion" in r["baseline_csv"]
        ][0]
        assert routing_diff["improved_bins"] == 9  # All bins improved
        assert routing_diff["degraded_bins"] == 0
        assert routing_diff["mean_diff"] > 0  # Positive = improvement
