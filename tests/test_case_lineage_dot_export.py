"""Tests for Case lineage graph DOT export functionality.

This module tests the export of Case lineage graphs to Graphviz DOT format,
enabling visualization of case DAGs.
"""

import pytest

from src.controller.case import Case, CaseGraph
from src.controller.types import CaseIdentifier


class TestDOTExportBasicFunctionality:
    """Test basic DOT export generation."""

    def test_export_to_dot_method_exists(self):
        """CaseGraph has export_to_dot() method."""
        graph = CaseGraph()
        assert hasattr(graph, "export_to_dot")
        assert callable(graph.export_to_dot)

    def test_export_empty_graph_to_dot(self):
        """Export empty graph produces valid DOT structure."""
        graph = CaseGraph()
        dot = graph.export_to_dot()

        # Should have basic DOT structure
        assert "digraph CaseLineage {" in dot
        assert "}" in dot
        assert "rankdir=TB" in dot

    def test_export_single_base_case_to_dot(self):
        """Export graph with only base case."""
        graph = CaseGraph()
        base_case = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/snapshots/nangate45"
        )
        graph.add_case(base_case)

        dot = graph.export_to_dot()

        # Should have digraph structure
        assert "digraph CaseLineage {" in dot
        assert "}" in dot

        # Should have base case node
        assert "nangate45_base_0_0" in dot
        assert "(BASE)" in dot

        # Base case should be highlighted
        assert "lightblue" in dot


class TestDOTExportNodeGeneration:
    """Test node generation in DOT format."""

    def test_dot_nodes_have_case_ids(self):
        """DOT nodes contain case IDs."""
        graph = CaseGraph()
        base_case = Case.create_base_case(
            base_name="test_base",
            snapshot_path="/snapshots/test"
        )
        graph.add_case(base_case)

        dot = graph.export_to_dot()

        assert "test_base_0_0" in dot

    def test_dot_nodes_sanitize_special_characters(self):
        """DOT node IDs sanitize dashes and dots to underscores."""
        graph = CaseGraph()
        # Create case with dash and dot in name
        identifier = CaseIdentifier(
            case_name="test-case.v2",
            stage_index=0,
            derived_index=0
        )
        case = Case(
            identifier=identifier,
            parent_id=None,
            snapshot_path="/snapshots/test"
        )
        graph.add_case(case)

        dot = graph.export_to_dot()

        # Should replace dashes and dots with underscores
        assert "test_case_v2_0_0" in dot

    def test_base_case_has_special_styling(self):
        """Base case nodes have fillcolor=lightblue."""
        graph = CaseGraph()
        base_case = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/snapshots/nangate45"
        )
        graph.add_case(base_case)

        dot = graph.export_to_dot()

        assert "fillcolor=lightblue" in dot
        assert "(BASE)" in dot

    def test_derived_case_shows_stage_index(self):
        """Derived case nodes show stage index."""
        graph = CaseGraph()
        base_case = Case.create_base_case(
            base_name="test_base",
            snapshot_path="/snapshots/test"
        )
        graph.add_case(base_case)

        derived = base_case.derive(
            eco_name="buffer_insertion",
            new_stage_index=1,
            derived_index=1,
            snapshot_path="/snapshots/test_1_1"
        )
        graph.add_case(derived)

        dot = graph.export_to_dot()

        # Derived case should show stage
        assert "Stage 1" in dot


class TestDOTExportEdgeGeneration:
    """Test edge generation in DOT format."""

    def test_dot_edges_connect_parent_to_child(self):
        """DOT edges connect parent cases to children."""
        graph = CaseGraph()
        base_case = Case.create_base_case(
            base_name="test_base",
            snapshot_path="/snapshots/test"
        )
        graph.add_case(base_case)

        derived = base_case.derive(
            eco_name="test_eco",
            new_stage_index=1,
            derived_index=1,
            snapshot_path="/snapshots/test_1_1"
        )
        graph.add_case(derived)

        dot = graph.export_to_dot()

        # Should have edge from base to derived
        assert "->" in dot
        assert "test_base_0_0 -> test_base_1_1" in dot

    def test_dot_edges_labeled_with_eco_name(self):
        """DOT edges are labeled with ECO names."""
        graph = CaseGraph()
        base_case = Case.create_base_case(
            base_name="test_base",
            snapshot_path="/snapshots/test"
        )
        graph.add_case(base_case)

        derived = base_case.derive(
            eco_name="buffer_insertion",
            new_stage_index=1,
            derived_index=1,
            snapshot_path="/snapshots/test_1_1"
        )
        graph.add_case(derived)

        dot = graph.export_to_dot()

        # Edge should be labeled with ECO name
        assert 'label="buffer_insertion"' in dot

    def test_multiple_edges_for_multiple_children(self):
        """Multiple children generate multiple edges."""
        graph = CaseGraph()
        base_case = Case.create_base_case(
            base_name="test_base",
            snapshot_path="/snapshots/test"
        )
        graph.add_case(base_case)

        # Create two derived cases
        derived1 = base_case.derive(
            eco_name="eco_a",
            new_stage_index=1,
            derived_index=1,
            snapshot_path="/snapshots/test_1_1"
        )
        graph.add_case(derived1)

        derived2 = base_case.derive(
            eco_name="eco_b",
            new_stage_index=1,
            derived_index=2,
            snapshot_path="/snapshots/test_1_2"
        )
        graph.add_case(derived2)

        dot = graph.export_to_dot()

        # Should have two edges
        assert dot.count("->") == 2
        assert "eco_a" in dot
        assert "eco_b" in dot


class TestDOTExportMultiStageCases:
    """Test DOT export with multi-stage case lineages."""

    def test_three_stage_linear_lineage(self):
        """Export linear 3-stage case lineage."""
        graph = CaseGraph()

        # Stage 0: Base case
        base = Case.create_base_case("base", "/snapshots/base")
        graph.add_case(base)

        # Stage 1: Derived from base
        stage1 = base.derive("eco1", 1, 1, "/snapshots/s1")
        graph.add_case(stage1)

        # Stage 2: Derived from stage1
        stage2 = stage1.derive("eco2", 2, 1, "/snapshots/s2")
        graph.add_case(stage2)

        dot = graph.export_to_dot()

        # Should have 3 cases total
        assert graph.count_cases() == 3
        # Should have 2 edges
        assert dot.count("->") == 2

        # All stages should be present
        assert "Stage 1" in dot
        assert "Stage 2" in dot
        assert "(BASE)" in dot

        # ECO names on edges
        assert "eco1" in dot
        assert "eco2" in dot

    def test_branching_case_tree(self):
        """Export branching case tree (multiple survivors per stage)."""
        graph = CaseGraph()

        base = Case.create_base_case("base", "/snapshots/base")
        graph.add_case(base)

        # Stage 1: Two survivors
        s1_case1 = base.derive("eco_a", 1, 1, "/snapshots/s1_1")
        graph.add_case(s1_case1)
        s1_case2 = base.derive("eco_b", 1, 2, "/snapshots/s1_2")
        graph.add_case(s1_case2)

        # Stage 2: Each stage 1 survivor produces a child
        s2_case1 = s1_case1.derive("eco_c", 2, 1, "/snapshots/s2_1")
        graph.add_case(s2_case1)
        s2_case2 = s1_case2.derive("eco_d", 2, 2, "/snapshots/s2_2")
        graph.add_case(s2_case2)

        dot = graph.export_to_dot()

        # Should have 5 cases total (1 base + 2 stage1 + 2 stage2)
        assert graph.count_cases() == 5

        # Should have 4 edges (base->2, stage1->2)
        assert dot.count("->") == 4

        # All ECOs should be present
        for eco in ["eco_a", "eco_b", "eco_c", "eco_d"]:
            assert eco in dot


class TestDOTExportFormatValidity:
    """Test that exported DOT format is syntactically valid."""

    def test_dot_has_opening_and_closing_braces(self):
        """DOT output has matching braces."""
        graph = CaseGraph()
        base = Case.create_base_case("base", "/snapshots/base")
        graph.add_case(base)

        dot = graph.export_to_dot()

        # Should start with opening brace and end with closing brace
        lines = dot.strip().split("\n")
        assert "{" in lines[0]
        assert lines[-1].strip() == "}"

    def test_dot_has_rankdir_attribute(self):
        """DOT output includes rankdir for layout."""
        graph = CaseGraph()
        base = Case.create_base_case("base", "/snapshots/base")
        graph.add_case(base)

        dot = graph.export_to_dot()

        # Should specify top-to-bottom layout
        assert "rankdir=TB" in dot

    def test_dot_has_default_node_style(self):
        """DOT output includes default node styling."""
        graph = CaseGraph()
        base = Case.create_base_case("base", "/snapshots/base")
        graph.add_case(base)

        dot = graph.export_to_dot()

        # Should have rounded box nodes
        assert "shape=box" in dot
        assert "rounded" in dot

    def test_dot_output_is_multiline_string(self):
        """DOT output is formatted with newlines."""
        graph = CaseGraph()
        base = Case.create_base_case("base", "/snapshots/base")
        graph.add_case(base)

        dot = graph.export_to_dot()

        # Should have multiple lines
        lines = dot.split("\n")
        assert len(lines) > 5


class TestDOTExportIntegration:
    """Integration tests for DOT export with StudyExecutor."""

    def test_dot_export_can_be_written_to_file(self, tmp_path):
        """DOT export can be saved to file."""
        graph = CaseGraph()
        base = Case.create_base_case("nangate45_base", "/snapshots/ng45")
        graph.add_case(base)

        derived = base.derive("eco1", 1, 1, "/snapshots/ng45_1_1")
        graph.add_case(derived)

        dot = graph.export_to_dot()

        # Write to file
        dot_file = tmp_path / "lineage.dot"
        dot_file.write_text(dot)

        # Verify file was written
        assert dot_file.exists()
        content = dot_file.read_text()
        assert "digraph CaseLineage" in content
        assert "nangate45_base_0_0" in content

    def test_dot_file_can_be_read_and_parsed(self, tmp_path):
        """DOT file is parseable (basic syntax check)."""
        graph = CaseGraph()
        base = Case.create_base_case("base", "/snapshots/base")
        graph.add_case(base)

        dot = graph.export_to_dot()
        dot_file = tmp_path / "lineage.dot"
        dot_file.write_text(dot)

        # Read back and verify structure
        content = dot_file.read_text()

        # Count braces to ensure balanced
        open_braces = content.count("{")
        close_braces = content.count("}")
        assert open_braces == close_braces
        assert open_braces >= 1  # At least the digraph brace


class TestDOTExportEdgeCases:
    """Test edge cases for DOT export."""

    def test_export_graph_with_many_cases(self):
        """Export graph with 50+ cases."""
        graph = CaseGraph()
        base = Case.create_base_case("base", "/snapshots/base")
        graph.add_case(base)

        # Create 50 derived cases
        for i in range(1, 51):
            derived = base.derive(
                eco_name=f"eco_{i}",
                new_stage_index=1,
                derived_index=i,
                snapshot_path=f"/snapshots/base_1_{i}"
            )
            graph.add_case(derived)

        dot = graph.export_to_dot()

        # Should have 51 cases total and 50 edges
        assert graph.count_cases() == 51
        assert dot.count("->") == 50

    def test_export_deep_lineage_chain(self):
        """Export deep lineage (10 stages)."""
        graph = CaseGraph()
        current = Case.create_base_case("base", "/snapshots/base")
        graph.add_case(current)

        # Create 10-stage linear chain
        for stage in range(1, 11):
            current = current.derive(
                eco_name=f"eco_stage_{stage}",
                new_stage_index=stage,
                derived_index=1,
                snapshot_path=f"/snapshots/base_{stage}_1"
            )
            graph.add_case(current)

        dot = graph.export_to_dot()

        # Should have 11 cases total and 10 edges
        assert graph.count_cases() == 11
        assert dot.count("->") == 10

        # All stage indices should be present
        for stage in range(1, 11):
            assert f"Stage {stage}" in dot

    def test_export_with_no_eco_name(self):
        """Export handles cases with no ECO name (None)."""
        graph = CaseGraph()
        base = Case.create_base_case("base", "/snapshots/base")
        graph.add_case(base)

        # Create derived case with eco_applied=None
        identifier = CaseIdentifier("base", 1, 1)
        derived = Case(
            identifier=identifier,
            parent_id=base.case_id,
            eco_applied=None,
            stage_index=1,
            snapshot_path="/snapshots/base_1_1"
        )
        graph.add_case(derived)

        dot = graph.export_to_dot()

        # Should use "unknown" for missing ECO name
        assert 'label="unknown"' in dot
