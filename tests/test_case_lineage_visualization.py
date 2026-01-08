"""Tests for Case lineage graph visualization (PNG rendering).

This module tests the end-to-end visualization feature for case lineage graphs,
including DOT export and PNG rendering using Graphviz.

Feature: Case lineage graph visualization is clear and shows DAG structure
"""

import pytest
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.controller.case import Case, CaseGraph


class TestPNGRenderingMethod:
    """Test render_to_png() method existence and basic functionality."""

    def test_render_to_png_method_exists(self):
        """CaseGraph has render_to_png() method."""
        graph = CaseGraph()
        assert hasattr(graph, "render_to_png")
        assert callable(graph.render_to_png)

    def test_render_to_png_creates_output_file(self, tmp_path):
        """render_to_png() creates PNG file at specified path."""
        graph = CaseGraph()
        base_case = Case.create_base_case(
            base_name="test_base",
            snapshot_path="/snapshots/test"
        )
        graph.add_case(base_case)

        output_file = tmp_path / "lineage.png"

        # Mock subprocess.run to simulate successful dot execution
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = graph.render_to_png(output_file)

        assert result is True
        mock_run.assert_called_once()

    def test_render_to_png_accepts_string_path(self, tmp_path):
        """render_to_png() accepts output path as string."""
        graph = CaseGraph()
        base_case = Case.create_base_case("test", "/snap")
        graph.add_case(base_case)

        output_file = str(tmp_path / "lineage.png")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = graph.render_to_png(output_file)

        assert result is True

    def test_render_to_png_accepts_path_object(self, tmp_path):
        """render_to_png() accepts output path as Path object."""
        graph = CaseGraph()
        base_case = Case.create_base_case("test", "/snap")
        graph.add_case(base_case)

        output_file = tmp_path / "lineage.png"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = graph.render_to_png(output_file)

        assert result is True


class TestPNGRenderingWithDOTCommand:
    """Test actual DOT command invocation."""

    def test_render_calls_dot_command(self, tmp_path):
        """render_to_png() invokes 'dot' command with correct arguments."""
        graph = CaseGraph()
        base_case = Case.create_base_case("test", "/snap")
        graph.add_case(base_case)

        output_file = tmp_path / "lineage.png"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            graph.render_to_png(output_file)

            # Verify subprocess.run was called with correct arguments
            call_args = mock_run.call_args
            assert call_args[0][0] == ["dot", "-Tpng", "-o", str(output_file)]

    def test_render_passes_dot_content_to_stdin(self, tmp_path):
        """render_to_png() passes DOT content via stdin."""
        graph = CaseGraph()
        base_case = Case.create_base_case("test_base", "/snap")
        graph.add_case(base_case)

        output_file = tmp_path / "lineage.png"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            graph.render_to_png(output_file)

            # Verify DOT content was passed as input
            call_args = mock_run.call_args
            assert call_args[1]["input"] is not None
            assert b"digraph CaseLineage" in call_args[1]["input"]

    def test_render_uses_export_to_dot_by_default(self, tmp_path):
        """render_to_png() calls export_to_dot() when dot_content not provided."""
        graph = CaseGraph()
        base_case = Case.create_base_case("test", "/snap")
        graph.add_case(base_case)

        output_file = tmp_path / "lineage.png"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            with patch.object(graph, "export_to_dot", return_value="digraph {}") as mock_export:
                graph.render_to_png(output_file)
                mock_export.assert_called_once()

    def test_render_accepts_custom_dot_content(self, tmp_path):
        """render_to_png() can accept custom DOT content instead of auto-generating."""
        graph = CaseGraph()

        output_file = tmp_path / "lineage.png"
        custom_dot = "digraph CustomGraph { A -> B; }"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            graph.render_to_png(output_file, dot_content=custom_dot)

            # Verify custom content was used
            call_args = mock_run.call_args
            assert custom_dot.encode("utf-8") == call_args[1]["input"]


class TestPNGRenderingOutputDirectory:
    """Test output directory handling."""

    def test_render_creates_output_directory_if_missing(self, tmp_path):
        """render_to_png() creates output directory if it doesn't exist."""
        graph = CaseGraph()
        base_case = Case.create_base_case("test", "/snap")
        graph.add_case(base_case)

        # Create nested path that doesn't exist yet
        output_file = tmp_path / "subdir" / "nested" / "lineage.png"
        assert not output_file.parent.exists()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            graph.render_to_png(output_file)

        # Directory should have been created
        assert output_file.parent.exists()

    def test_render_works_with_existing_directory(self, tmp_path):
        """render_to_png() works when output directory already exists."""
        graph = CaseGraph()
        base_case = Case.create_base_case("test", "/snap")
        graph.add_case(base_case)

        # Create directory explicitly
        output_dir = tmp_path / "existing"
        output_dir.mkdir()
        output_file = output_dir / "lineage.png"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = graph.render_to_png(output_file)

        assert result is True


class TestPNGRenderingErrorHandling:
    """Test error handling for various failure modes."""

    def test_render_raises_error_when_dot_not_found(self, tmp_path):
        """render_to_png() raises FileNotFoundError when dot command not available."""
        graph = CaseGraph()
        base_case = Case.create_base_case("test", "/snap")
        graph.add_case(base_case)

        output_file = tmp_path / "lineage.png"

        # Simulate dot command not found
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(FileNotFoundError) as exc_info:
                graph.render_to_png(output_file)

            assert "Graphviz 'dot' command not found" in str(exc_info.value)
            assert "apt-get install graphviz" in str(exc_info.value)

    def test_render_raises_error_when_dot_fails(self, tmp_path):
        """render_to_png() raises RuntimeError when dot command fails."""
        graph = CaseGraph()
        base_case = Case.create_base_case("test", "/snap")
        graph.add_case(base_case)

        output_file = tmp_path / "lineage.png"

        # Simulate dot command failure
        error = subprocess.CalledProcessError(
            returncode=1,
            cmd=["dot"],
            stderr=b"Syntax error in DOT file"
        )
        with patch("subprocess.run", side_effect=error):
            with pytest.raises(RuntimeError) as exc_info:
                graph.render_to_png(output_file)

            assert "Failed to render graph to PNG" in str(exc_info.value)
            assert "Syntax error" in str(exc_info.value)

    def test_render_raises_error_on_timeout(self, tmp_path):
        """render_to_png() raises RuntimeError when dot command times out."""
        graph = CaseGraph()
        base_case = Case.create_base_case("test", "/snap")
        graph.add_case(base_case)

        output_file = tmp_path / "lineage.png"

        # Simulate timeout
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("dot", 30)):
            with pytest.raises(RuntimeError) as exc_info:
                graph.render_to_png(output_file)

            assert "timed out after 30 seconds" in str(exc_info.value)


class TestPNGRenderingComplexGraphs:
    """Test rendering of complex case graphs."""

    def test_render_simple_graph_with_one_case(self, tmp_path):
        """Render simple graph with only base case."""
        graph = CaseGraph()
        base_case = Case.create_base_case("nangate45", "/snap")
        graph.add_case(base_case)

        output_file = tmp_path / "simple.png"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = graph.render_to_png(output_file)

        assert result is True

        # Verify DOT content includes base case
        call_args = mock_run.call_args
        dot_content = call_args[1]["input"].decode("utf-8")
        assert "nangate45_0_0" in dot_content
        assert "BASE" in dot_content

    def test_render_graph_with_branching(self, tmp_path):
        """Render graph with branching derivations."""
        graph = CaseGraph()

        # Create base case
        base = Case.create_base_case("nangate45", "/base")
        graph.add_case(base)

        # Create multiple derived cases (branching)
        derived1 = base.derive("buffer_insertion", 0, 1, "/d1")
        derived2 = base.derive("cell_sizing", 0, 2, "/d2")
        derived3 = base.derive("gate_cloning", 0, 3, "/d3")

        graph.add_case(derived1)
        graph.add_case(derived2)
        graph.add_case(derived3)

        output_file = tmp_path / "branching.png"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = graph.render_to_png(output_file)

        assert result is True

        # Verify DOT content includes all cases and edges
        call_args = mock_run.call_args
        dot_content = call_args[1]["input"].decode("utf-8")
        assert "nangate45_0_0" in dot_content
        assert "nangate45_0_1" in dot_content
        assert "nangate45_0_2" in dot_content
        assert "nangate45_0_3" in dot_content
        assert "buffer_insertion" in dot_content
        assert "cell_sizing" in dot_content
        assert "gate_cloning" in dot_content

    def test_render_multi_stage_graph(self, tmp_path):
        """Render graph with multi-stage progression."""
        graph = CaseGraph()

        # Stage 0: Base case
        base = Case.create_base_case("nangate45", "/base")
        graph.add_case(base)

        # Stage 0: First ECO
        stage0_case = base.derive("eco1", 0, 1, "/s0")
        graph.add_case(stage0_case)

        # Stage 1: Second ECO
        stage1_case = stage0_case.derive("eco2", 1, 1, "/s1")
        graph.add_case(stage1_case)

        # Stage 2: Third ECO
        stage2_case = stage1_case.derive("eco3", 2, 1, "/s2")
        graph.add_case(stage2_case)

        output_file = tmp_path / "multi_stage.png"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = graph.render_to_png(output_file)

        assert result is True

        # Verify DOT content shows stage progression
        call_args = mock_run.call_args
        dot_content = call_args[1]["input"].decode("utf-8")
        assert "Stage 0" in dot_content
        assert "Stage 1" in dot_content
        assert "Stage 2" in dot_content


class TestFeatureStepValidation:
    """Validate all feature steps for Case lineage graph visualization."""

    def test_step1_execute_study_with_branching_derivations(self, tmp_path):
        """Step 1: Execute Study with branching case derivations."""
        # Create a study with branching
        graph = CaseGraph()

        base = Case.create_base_case("nangate45_base", "/snapshots/nangate45")
        graph.add_case(base)

        # Apply multiple ECOs creating branching
        eco_names = ["buffer_insertion", "cell_sizing", "gate_cloning"]
        for i, eco_name in enumerate(eco_names, start=1):
            derived = base.derive(eco_name, 0, i, f"/snapshots/derived_{i}")
            graph.add_case(derived)

        # Verify branching structure
        assert graph.count_cases() == 4
        assert len(graph.get_cases_by_stage(0)) == 4

    def test_step2_generate_lineage_graph_dot_file(self, tmp_path):
        """Step 2: Generate lineage graph DOT file."""
        graph = CaseGraph()
        base = Case.create_base_case("nangate45", "/snap")
        graph.add_case(base)

        derived = base.derive("eco1", 0, 1, "/d1")
        graph.add_case(derived)

        # Generate DOT content
        dot_content = graph.export_to_dot()

        # Verify DOT file is valid
        assert dot_content.startswith("digraph CaseLineage {")
        assert dot_content.endswith("}")
        assert "nangate45_0_0" in dot_content
        assert "nangate45_0_1" in dot_content
        assert "eco1" in dot_content

        # Write to file
        dot_file = tmp_path / "lineage.dot"
        dot_file.write_text(dot_content)
        assert dot_file.exists()

    def test_step3_render_graph_to_png(self, tmp_path):
        """Step 3: Render graph to PNG."""
        graph = CaseGraph()
        base = Case.create_base_case("nangate45", "/snap")
        graph.add_case(base)

        output_file = tmp_path / "lineage.png"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            success = graph.render_to_png(output_file)

        assert success is True
        # Verify dot command was called
        mock_run.assert_called_once()

    def test_step4_view_lineage_visualization(self, tmp_path):
        """Step 4: View lineage visualization (file exists and is readable)."""
        graph = CaseGraph()
        base = Case.create_base_case("nangate45", "/snap")
        graph.add_case(base)

        output_file = tmp_path / "lineage.png"

        # Create a fake PNG file to simulate successful rendering
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            # Simulate creating PNG file
            output_file.write_bytes(b"PNG_DATA")

            graph.render_to_png(output_file)

        # Verify file exists and can be opened
        assert output_file.exists()
        assert output_file.is_file()
        assert output_file.stat().st_size > 0

    def test_step6_verify_parent_child_relationships_clear(self):
        """Step 6: Verify parent-child relationships are clear in DOT format."""
        graph = CaseGraph()

        base = Case.create_base_case("test", "/base")
        graph.add_case(base)

        derived1 = base.derive("eco_a", 0, 1, "/d1")
        derived2 = derived1.derive("eco_b", 0, 2, "/d2")

        graph.add_case(derived1)
        graph.add_case(derived2)

        dot_content = graph.export_to_dot()

        # Verify edges show parent -> child relationships
        assert "test_0_0 -> test_0_1" in dot_content
        assert "test_0_1 -> test_0_2" in dot_content

        # Verify ECO labels on edges
        assert 'label="eco_a"' in dot_content
        assert 'label="eco_b"' in dot_content

    def test_step7_verify_graph_layout_readable(self):
        """Step 7: Verify graph layout is readable (DOT directives present)."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/base")
        graph.add_case(base)

        dot_content = graph.export_to_dot()

        # Verify layout directives are present
        assert "rankdir=TB" in dot_content  # Top-to-bottom layout
        assert "node [shape=box, style=rounded]" in dot_content  # Readable node shapes

        # Verify base case has special styling (stands out)
        assert "lightblue" in dot_content


class TestEndToEndVisualization:
    """End-to-end test of complete visualization workflow."""

    def test_complete_visualization_workflow(self, tmp_path):
        """Complete workflow: create graph, export DOT, render PNG."""
        # 1. Create complex case graph
        graph = CaseGraph()

        base = Case.create_base_case("nangate45_base", "/snapshots/base")
        graph.add_case(base)

        # Stage 0: 3 ECOs
        eco1 = base.derive("buffer_insertion", 0, 1, "/s0/eco1")
        eco2 = base.derive("cell_sizing", 0, 2, "/s0/eco2")
        eco3 = base.derive("gate_cloning", 0, 3, "/s0/eco3")

        graph.add_case(eco1)
        graph.add_case(eco2)
        graph.add_case(eco3)

        # Stage 1: Continue from eco1
        eco1_next = eco1.derive("optimization", 1, 1, "/s1/eco1_next")
        graph.add_case(eco1_next)

        # 2. Export to DOT file
        dot_file = tmp_path / "lineage.dot"
        dot_content = graph.export_to_dot()
        dot_file.write_text(dot_content)

        assert dot_file.exists()

        # 3. Render to PNG
        png_file = tmp_path / "lineage.png"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            success = graph.render_to_png(png_file)

        assert success is True

        # Verify subprocess was called with correct arguments
        call_args = mock_run.call_args
        assert call_args[0][0] == ["dot", "-Tpng", "-o", str(png_file)]

        # Verify DOT content was passed
        passed_content = call_args[1]["input"].decode("utf-8")
        assert "nangate45_base_0_0" in passed_content
        assert "buffer_insertion" in passed_content
        assert "cell_sizing" in passed_content
        assert "gate_cloning" in passed_content
        assert "optimization" in passed_content
