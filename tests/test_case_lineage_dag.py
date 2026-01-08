"""Tests for case lineage DAG generation and export - Feature #23.

Tests the ability to generate, visualize, and export case lineage graphs
showing derivation relationships in a multi-stage Study.
"""

import pytest

from src.controller.case import Case, CaseGraph


class TestCaseLineageDAGGeneration:
    """Test case lineage DAG generation for multi-stage Studies."""

    def test_generate_dag_for_simple_study(self) -> None:
        """Generate DAG for a simple study with one base case and one derived case."""
        graph = CaseGraph()

        # Base case
        base = Case.create_base_case("nangate45", "/path/to/base", {})
        graph.add_case(base)

        # Derived case
        derived = base.derive(
            eco_name="buffer_insertion",
            new_stage_index=0,
            derived_index=1,
            snapshot_path="/path/to/derived",
        )
        graph.add_case(derived)

        # Generate DAG
        dag = graph.export_dag()

        assert len(dag["nodes"]) == 2
        assert len(dag["edges"]) == 1
        assert dag["statistics"]["total_cases"] == 2
        assert dag["statistics"]["total_edges"] == 1

    def test_dag_shows_parent_child_relationships(self) -> None:
        """Verify DAG correctly shows parent-child relationships."""
        graph = CaseGraph()

        base = Case.create_base_case("test", "/base", {})
        graph.add_case(base)

        derived1 = base.derive("eco1", 0, 1, "/d1")
        graph.add_case(derived1)

        derived2 = derived1.derive("eco2", 0, 2, "/d2")
        graph.add_case(derived2)

        dag = graph.export_dag()

        # Check edges show correct relationships
        edges = dag["edges"]
        assert len(edges) == 2

        # First edge: base -> derived1
        assert edges[0]["source"] == base.case_id
        assert edges[0]["target"] == derived1.case_id
        assert edges[0]["eco"] == "eco1"

        # Second edge: derived1 -> derived2
        assert edges[1]["source"] == derived1.case_id
        assert edges[1]["target"] == derived2.case_id
        assert edges[1]["eco"] == "eco2"

    def test_dag_with_branching_derivations(self) -> None:
        """Test DAG generation with branching (multiple children from one parent)."""
        graph = CaseGraph()

        base = Case.create_base_case("nangate45", "/base", {})
        graph.add_case(base)

        # Create multiple derived cases from base (branching)
        derived1 = base.derive("eco_a", 0, 1, "/d1")
        derived2 = base.derive("eco_b", 0, 2, "/d2")
        derived3 = base.derive("eco_c", 0, 3, "/d3")

        graph.add_case(derived1)
        graph.add_case(derived2)
        graph.add_case(derived3)

        dag = graph.export_dag()

        assert len(dag["nodes"]) == 4
        assert len(dag["edges"]) == 3

        # All edges should have base case as source
        for edge in dag["edges"]:
            assert edge["source"] == base.case_id

    def test_dag_multi_stage_progression(self) -> None:
        """Test DAG for multi-stage Study with stage progression."""
        graph = CaseGraph()

        # Stage 0: Base case
        base = Case.create_base_case("nangate45", "/base", {})
        graph.add_case(base)

        # Stage 0: Derived cases
        stage0_d1 = base.derive("eco1", 0, 1, "/s0_d1")
        stage0_d2 = base.derive("eco2", 0, 2, "/s0_d2")
        graph.add_case(stage0_d1)
        graph.add_case(stage0_d2)

        # Stage 1: Derived from stage 0 survivors
        stage1_d1 = stage0_d1.derive("eco3", 1, 0, "/s1_d0")
        stage1_d2 = stage0_d1.derive("eco4", 1, 1, "/s1_d1")
        graph.add_case(stage1_d1)
        graph.add_case(stage1_d2)

        dag = graph.export_dag()

        # Verify stage statistics
        assert dag["statistics"]["max_stage"] == 1
        assert dag["statistics"]["cases_per_stage"][0] == 3  # base + 2 derived
        assert dag["statistics"]["cases_per_stage"][1] == 2  # 2 derived

        # Verify lineage is preserved
        assert len(dag["edges"]) == 4

    def test_dag_export_includes_eco_information(self) -> None:
        """Verify exported DAG includes ECO information on edges."""
        graph = CaseGraph()

        base = Case.create_base_case("test", "/base", {})
        graph.add_case(base)

        derived = base.derive("buffer_insertion", 0, 1, "/d1")
        graph.add_case(derived)

        dag = graph.export_dag()

        edge = dag["edges"][0]
        assert edge["eco"] == "buffer_insertion"

    def test_dag_export_includes_node_metadata(self) -> None:
        """Verify exported DAG includes case metadata in nodes."""
        graph = CaseGraph()

        metadata = {"wns_ps": -250.0, "custom_field": "test_value"}
        base = Case.create_base_case("test", "/base", metadata)
        graph.add_case(base)

        dag = graph.export_dag()

        node = dag["nodes"][0]
        assert node["case_id"] == base.case_id
        assert node["case_name"] == "test"
        assert node["is_base_case"] is True
        assert node["metadata"] == metadata
        assert node["eco_applied"] is None


class TestDAGIntegrityVerification:
    """Test DAG integrity verification (cycle detection, parent validation)."""

    def test_valid_dag_passes_integrity_check(self) -> None:
        """A valid DAG should pass integrity verification."""
        graph = CaseGraph()

        base = Case.create_base_case("test", "/base", {})
        graph.add_case(base)

        derived1 = base.derive("eco1", 0, 1, "/d1")
        derived2 = base.derive("eco2", 0, 2, "/d2")
        graph.add_case(derived1)
        graph.add_case(derived2)

        is_valid, errors = graph.verify_dag_integrity()
        assert is_valid
        assert len(errors) == 0

    def test_empty_dag_is_valid(self) -> None:
        """An empty DAG should be valid."""
        graph = CaseGraph()
        is_valid, errors = graph.verify_dag_integrity()
        assert is_valid
        assert len(errors) == 0

    def test_single_node_dag_is_valid(self) -> None:
        """A DAG with single node (base case) is valid."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/base", {})
        graph.add_case(base)

        is_valid, errors = graph.verify_dag_integrity()
        assert is_valid
        assert len(errors) == 0

    def test_complex_valid_dag(self) -> None:
        """A complex multi-level DAG should be valid."""
        graph = CaseGraph()

        # Build a 3-level tree
        base = Case.create_base_case("test", "/base", {})
        graph.add_case(base)

        # Level 1
        l1_a = base.derive("eco_a", 0, 1, "/l1_a")
        l1_b = base.derive("eco_b", 0, 2, "/l1_b")
        graph.add_case(l1_a)
        graph.add_case(l1_b)

        # Level 2
        l2_a = l1_a.derive("eco_c", 1, 0, "/l2_a")
        l2_b = l1_a.derive("eco_d", 1, 1, "/l2_b")
        l2_c = l1_b.derive("eco_e", 1, 2, "/l2_c")
        graph.add_case(l2_a)
        graph.add_case(l2_b)
        graph.add_case(l2_c)

        is_valid, errors = graph.verify_dag_integrity()
        assert is_valid
        assert len(errors) == 0


class TestDAGDepthCalculation:
    """Test DAG depth calculation."""

    def test_empty_dag_has_zero_depth(self) -> None:
        """An empty DAG has depth 0."""
        graph = CaseGraph()
        assert graph.get_dag_depth() == 0

    def test_base_case_only_has_depth_zero(self) -> None:
        """A DAG with only base case has depth 0."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/base", {})
        graph.add_case(base)
        assert graph.get_dag_depth() == 0

    def test_single_derivation_has_depth_one(self) -> None:
        """A DAG with one derivation has depth 1."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/base", {})
        graph.add_case(base)

        derived = base.derive("eco1", 0, 1, "/d1")
        graph.add_case(derived)

        assert graph.get_dag_depth() == 1

    def test_multi_level_dag_depth(self) -> None:
        """Test depth calculation for multi-level DAG."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/base", {})
        graph.add_case(base)

        d1 = base.derive("eco1", 0, 1, "/d1")
        graph.add_case(d1)

        d2 = d1.derive("eco2", 0, 2, "/d2")
        graph.add_case(d2)

        d3 = d2.derive("eco3", 1, 0, "/d3")
        graph.add_case(d3)

        assert graph.get_dag_depth() == 3

    def test_dag_depth_with_branching(self) -> None:
        """DAG depth should be the longest path, not total nodes."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/base", {})
        graph.add_case(base)

        # Branch 1: depth 1
        d1 = base.derive("eco1", 0, 1, "/d1")
        graph.add_case(d1)

        # Branch 2: depth 3
        d2 = base.derive("eco2", 0, 2, "/d2")
        graph.add_case(d2)

        d3 = d2.derive("eco3", 1, 0, "/d3")
        graph.add_case(d3)

        d4 = d3.derive("eco4", 1, 1, "/d4")
        graph.add_case(d4)

        # Maximum depth is 3 (base -> d2 -> d3 -> d4)
        assert graph.get_dag_depth() == 3


class TestDAGLeafCases:
    """Test identification of leaf cases (cases with no children)."""

    def test_base_case_only_is_leaf(self) -> None:
        """Base case with no children is a leaf."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/base", {})
        graph.add_case(base)

        leaves = graph.get_leaf_cases()
        assert len(leaves) == 1
        assert leaves[0].case_id == base.case_id

    def test_derived_case_with_no_children_is_leaf(self) -> None:
        """Derived cases with no children are leaves."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/base", {})
        graph.add_case(base)

        d1 = base.derive("eco1", 0, 1, "/d1")
        d2 = base.derive("eco2", 0, 2, "/d2")
        graph.add_case(d1)
        graph.add_case(d2)

        leaves = graph.get_leaf_cases()
        assert len(leaves) == 2
        leaf_ids = {leaf.case_id for leaf in leaves}
        assert d1.case_id in leaf_ids
        assert d2.case_id in leaf_ids

    def test_intermediate_cases_are_not_leaves(self) -> None:
        """Cases with children are not leaves."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/base", {})
        graph.add_case(base)

        d1 = base.derive("eco1", 0, 1, "/d1")
        graph.add_case(d1)

        d2 = d1.derive("eco2", 0, 2, "/d2")
        graph.add_case(d2)

        leaves = graph.get_leaf_cases()
        assert len(leaves) == 1
        assert leaves[0].case_id == d2.case_id

    def test_leaves_in_multi_branch_dag(self) -> None:
        """Identify all leaves in a multi-branch DAG."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/base", {})
        graph.add_case(base)

        # Branch 1
        d1 = base.derive("eco1", 0, 1, "/d1")
        graph.add_case(d1)
        d1_child = d1.derive("eco2", 1, 0, "/d1_child")
        graph.add_case(d1_child)

        # Branch 2
        d2 = base.derive("eco3", 0, 2, "/d2")
        graph.add_case(d2)

        # Branch 3
        d3 = base.derive("eco4", 0, 3, "/d3")
        graph.add_case(d3)

        leaves = graph.get_leaf_cases()
        assert len(leaves) == 3
        leaf_ids = {leaf.case_id for leaf in leaves}
        assert d1_child.case_id in leaf_ids
        assert d2.case_id in leaf_ids
        assert d3.case_id in leaf_ids


class TestDAGStatistics:
    """Test DAG statistics calculation."""

    def test_dag_statistics_for_simple_graph(self) -> None:
        """Calculate statistics for a simple graph."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/base", {})
        graph.add_case(base)

        d1 = base.derive("eco1", 0, 1, "/d1")
        graph.add_case(d1)

        dag = graph.export_dag()
        stats = dag["statistics"]

        assert stats["total_cases"] == 2
        assert stats["total_edges"] == 1
        assert stats["max_stage"] == 0
        assert stats["cases_per_stage"][0] == 2

    def test_dag_statistics_multi_stage(self) -> None:
        """Calculate statistics for multi-stage graph."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/base", {})
        graph.add_case(base)

        # Stage 0
        d1 = base.derive("eco1", 0, 1, "/s0_d1")
        d2 = base.derive("eco2", 0, 2, "/s0_d2")
        graph.add_case(d1)
        graph.add_case(d2)

        # Stage 1
        d3 = d1.derive("eco3", 1, 0, "/s1_d0")
        graph.add_case(d3)

        dag = graph.export_dag()
        stats = dag["statistics"]

        assert stats["total_cases"] == 4
        assert stats["total_edges"] == 3
        assert stats["max_stage"] == 1
        assert stats["cases_per_stage"][0] == 3
        assert stats["cases_per_stage"][1] == 1


class TestDAGMachineReadableExport:
    """Test machine-readable export format."""

    def test_dag_export_is_json_serializable(self) -> None:
        """Exported DAG should be JSON-serializable."""
        import json

        graph = CaseGraph()
        base = Case.create_base_case("test", "/base", {})
        graph.add_case(base)

        d1 = base.derive("eco1", 0, 1, "/d1")
        graph.add_case(d1)

        dag = graph.export_dag()

        # Should not raise
        json_str = json.dumps(dag)
        assert len(json_str) > 0

        # Should round-trip
        loaded = json.loads(json_str)
        assert loaded["statistics"]["total_cases"] == 2

    def test_dag_export_format_has_required_fields(self) -> None:
        """Exported DAG should have all required fields."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/base", {})
        graph.add_case(base)

        dag = graph.export_dag()

        # Top-level keys
        assert "nodes" in dag
        assert "edges" in dag
        assert "statistics" in dag

        # Node fields
        if dag["nodes"]:
            node = dag["nodes"][0]
            assert "case_id" in node
            assert "case_name" in node
            assert "stage_index" in node
            assert "derived_index" in node
            assert "is_base_case" in node
            assert "eco_applied" in node
            assert "snapshot_path" in node
            assert "metadata" in node

        # Statistics fields
        stats = dag["statistics"]
        assert "total_cases" in stats
        assert "total_edges" in stats
        assert "max_stage" in stats
        assert "cases_per_stage" in stats

    def test_dag_can_be_reconstructed_from_export(self) -> None:
        """Verify DAG export contains enough information to reconstruct the graph."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/base", {})
        graph.add_case(base)

        d1 = base.derive("eco1", 0, 1, "/d1")
        d2 = d1.derive("eco2", 1, 0, "/d2")
        graph.add_case(d1)
        graph.add_case(d2)

        dag = graph.export_dag()

        # Should have complete information about all cases
        assert len(dag["nodes"]) == 3
        assert len(dag["edges"]) == 2

        # Verify edges provide parent-child mapping
        edges_map = {edge["target"]: edge["source"] for edge in dag["edges"]}
        assert edges_map[d1.case_id] == base.case_id
        assert edges_map[d2.case_id] == d1.case_id
