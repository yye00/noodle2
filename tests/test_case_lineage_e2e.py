"""End-to-end test for Case lineage tracking and DAG visualization.

This module implements comprehensive E2E testing for the case lineage tracking
and DAG visualization workflow, covering all 14 steps of the feature requirement.

Feature: End-to-end: Case lineage tracking and DAG visualization across complex Study
"""

import pytest
from pathlib import Path
from unittest.mock import patch, Mock

from src.controller.case import Case, CaseGraph
from src.controller.types import CaseIdentifier


class TestComplexStudyWithBranchingCaseDerivations:
    """Step 1: Create Study with branching case derivations."""

    def test_create_study_with_branching_structure(self):
        """Study can be created with branching case derivation structure."""
        graph = CaseGraph()

        # Create base case
        base_case = Case.create_base_case(
            base_name="gcd_base",
            snapshot_path="/snapshots/gcd_base",
            metadata={"wns_ps": -500, "congestion_score": 0.75}
        )
        graph.add_case(base_case)

        assert graph.count_cases() == 1
        assert graph.get_base_case() is not None

    def test_study_supports_multiple_stages(self):
        """Study structure supports multiple stages with survivors."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/snap")
        graph.add_case(base)

        # Stage 0: 5 derivations (derived_index starts from 1 since base is 0)
        for i in range(5):
            derived = base.derive(
                eco_name=f"eco_{i}",
                new_stage_index=0,
                derived_index=i + 1,  # Start from 1 to avoid conflict with base
                snapshot_path=f"/snap/s0_{i}"
            )
            graph.add_case(derived)

        assert graph.count_cases_by_stage(0) == 6  # base + 5 derived
        assert graph.count_cases() == 6


class TestSingleBaseCase:
    """Step 2: Start with single base case."""

    def test_study_starts_with_single_base_case(self):
        """Study begins with exactly one base case."""
        graph = CaseGraph()
        base_case = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/snapshots/nangate45",
            metadata={"wns_ps": -1000, "area": 50000}
        )
        graph.add_case(base_case)

        assert graph.count_cases() == 1
        base = graph.get_base_case()
        assert base is not None
        assert base.is_base_case
        assert base.parent_id is None

    def test_base_case_has_no_parent(self):
        """Base case has no parent and no ECO applied."""
        graph = CaseGraph()
        base = Case.create_base_case("test_base", "/snap")
        graph.add_case(base)

        retrieved = graph.get_base_case()
        assert retrieved is not None
        assert retrieved.parent_id is None
        assert retrieved.eco_applied is None
        assert retrieved.is_base_case


class TestFiveDifferentECOsCreatingDerivedCases:
    """Step 3: Apply 5 different ECOs creating 5 derived cases in Stage 0."""

    def test_apply_five_ecos_to_base_case(self):
        """Can apply 5 different ECOs to base case, creating 5 derived cases."""
        graph = CaseGraph()
        base = Case.create_base_case(
            base_name="gcd",
            snapshot_path="/snap/base",
            metadata={"wns_ps": -500}
        )
        graph.add_case(base)

        # Apply 5 different ECOs
        eco_names = ["buffer_insertion", "gate_sizing", "vt_swap", "pin_swap", "clock_skew"]

        for i, eco_name in enumerate(eco_names):
            derived = base.derive(
                eco_name=eco_name,
                new_stage_index=0,
                derived_index=i + 1,
                snapshot_path=f"/snap/s0_{i}",
                metadata={"wns_ps": -500 + (i + 1) * 50}  # Varying improvements
            )
            graph.add_case(derived)

        # Verify 5 derived cases created
        stage0_cases = graph.get_cases_by_stage(0)
        assert len(stage0_cases) == 6  # base + 5 derived

        # Verify all have base as parent
        derived_cases = [c for c in stage0_cases if not c.is_base_case]
        assert len(derived_cases) == 5
        for case in derived_cases:
            assert case.parent_id == base.case_id

    def test_each_eco_produces_unique_case(self):
        """Each ECO produces a unique case with different characteristics."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/snap", metadata={"wns_ps": -1000})
        graph.add_case(base)

        ecos = ["eco_a", "eco_b", "eco_c", "eco_d", "eco_e"]
        for i, eco in enumerate(ecos):
            derived = base.derive(
                eco_name=eco,
                new_stage_index=0,
                derived_index=i + 1,
                snapshot_path=f"/snap/{i}",
                metadata={"wns_ps": -1000 + i * 100}
            )
            graph.add_case(derived)

        # Verify all cases are unique
        case_ids = [c.case_id for c in graph.cases.values()]
        assert len(case_ids) == len(set(case_ids))  # All unique


class TestSelectTopSurvivors:
    """Step 4: Select top 3 survivors."""

    def test_select_top_three_survivors_from_stage0(self):
        """Can identify and select top 3 survivors based on metrics."""
        graph = CaseGraph()
        base = Case.create_base_case("gcd", "/snap", metadata={"wns_ps": -500})
        graph.add_case(base)

        # Create 5 derived cases with varying WNS
        wns_values = [-450, -480, -420, -460, -440]  # -420, -440, -450 are best
        for i, wns in enumerate(wns_values):
            derived = base.derive(
                eco_name=f"eco_{i}",
                new_stage_index=0,
                derived_index=i + 1,
                snapshot_path=f"/snap/{i}",
                metadata={"wns_ps": wns}
            )
            graph.add_case(derived)

        # Select top 3 by WNS (higher is better)
        stage0_cases = [c for c in graph.get_cases_by_stage(0) if not c.is_base_case]
        sorted_cases = sorted(stage0_cases, key=lambda c: c.metadata["wns_ps"], reverse=True)
        top3_survivors = sorted_cases[:3]

        assert len(top3_survivors) == 3
        assert top3_survivors[0].metadata["wns_ps"] == -420
        assert top3_survivors[1].metadata["wns_ps"] == -440
        assert top3_survivors[2].metadata["wns_ps"] == -450

    def test_survivor_selection_preserves_lineage(self):
        """Survivor selection preserves parent-child lineage."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/snap")
        graph.add_case(base)

        # Create derived cases
        for i in range(5):
            derived = base.derive(
                eco_name=f"eco_{i}",
                new_stage_index=0,
                derived_index=i + 1,
                snapshot_path=f"/snap/{i}"
            )
            graph.add_case(derived)

        # Select survivors
        stage0_cases = [c for c in graph.get_cases_by_stage(0) if not c.is_base_case]
        survivors = stage0_cases[:3]

        # Verify lineage is intact
        for survivor in survivors:
            lineage = graph.get_lineage(survivor.case_id)
            assert len(lineage.ancestors) == 1
            assert lineage.ancestors[0] == base.case_id


class TestApplyECOsToSurvivors:
    """Step 5: Apply 3 different ECOs to each survivor (9 cases in Stage 1)."""

    def test_apply_three_ecos_to_each_survivor(self):
        """Apply 3 different ECOs to each of 3 survivors, creating 9 Stage 1 cases."""
        graph = CaseGraph()
        base = Case.create_base_case("gcd", "/snap", metadata={"wns_ps": -500})
        graph.add_case(base)

        # Stage 0: Create 5 cases, select 3 survivors
        survivors = []
        for i in range(5):
            derived = base.derive(
                eco_name=f"s0_eco_{i}",
                new_stage_index=0,
                derived_index=i + 1,
                snapshot_path=f"/snap/s0_{i}",
                metadata={"wns_ps": -500 + i * 50}
            )
            graph.add_case(derived)
            if i in [2, 3, 4]:  # Top 3
                survivors.append(derived)

        # Stage 1: Apply 3 ECOs to each survivor
        stage1_cases = []
        for surv_idx, survivor in enumerate(survivors):
            for eco_idx in range(3):
                stage1_case = survivor.derive(
                    eco_name=f"s1_eco_{eco_idx}",
                    new_stage_index=1,
                    derived_index=surv_idx * 3 + eco_idx,
                    snapshot_path=f"/snap/s1_{surv_idx}_{eco_idx}",
                    metadata={"wns_ps": survivor.metadata["wns_ps"] + 20}
                )
                graph.add_case(stage1_case)
                stage1_cases.append(stage1_case)

        # Verify 9 Stage 1 cases created
        assert len(stage1_cases) == 9
        assert graph.count_cases_by_stage(1) == 9

    def test_stage1_cases_have_correct_parents(self):
        """Stage 1 cases have Stage 0 survivors as parents."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/snap")
        graph.add_case(base)

        # Create Stage 0 survivors
        survivors = []
        for i in range(3):
            s0 = base.derive(f"s0_eco_{i}", 0, i + 1, f"/snap/s0_{i}")
            graph.add_case(s0)
            survivors.append(s0)

        # Create Stage 1 cases
        for surv_idx, survivor in enumerate(survivors):
            for eco_idx in range(3):
                s1 = survivor.derive(
                    f"s1_eco_{eco_idx}",
                    1,
                    surv_idx * 3 + eco_idx,
                    f"/snap/s1_{surv_idx}_{eco_idx}"
                )
                graph.add_case(s1)

                # Verify parent is the survivor
                assert s1.parent_id == survivor.case_id


class TestParentChildRelationships:
    """Step 6: Track parent-child relationships for all cases."""

    def test_track_all_parent_child_relationships(self):
        """All parent-child relationships are tracked correctly."""
        graph = CaseGraph()
        base = Case.create_base_case("gcd", "/snap")
        graph.add_case(base)

        # Build complex tree
        stage0_cases = []
        for i in range(5):
            s0 = base.derive(f"eco_{i}", 0, i + 1, f"/s0/{i}")
            graph.add_case(s0)
            stage0_cases.append(s0)

        # Stage 1 from top 3
        for i in range(3):
            parent = stage0_cases[i]
            for j in range(3):
                s1 = parent.derive(f"eco_{j}", 1, i*3+j, f"/s1/{i}_{j}")
                graph.add_case(s1)

        # Verify all relationships
        for case in graph.cases.values():
            if not case.is_base_case:
                # Parent must exist
                assert case.parent_id in graph.cases
                parent = graph.cases[case.parent_id]
                assert parent is not None

    def test_get_lineage_traces_back_to_base(self):
        """get_lineage() correctly traces ancestry back to base case."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/snap")
        graph.add_case(base)

        # Create chain: base -> s0 -> s1
        s0 = base.derive("eco_a", 0, 1, "/s0")
        graph.add_case(s0)

        s1 = s0.derive("eco_b", 1, 0, "/s1")
        graph.add_case(s1)

        # Get lineage for s1
        lineage = graph.get_lineage(s1.case_id)

        assert len(lineage.ancestors) == 2
        assert lineage.ancestors[0] == base.case_id
        assert lineage.ancestors[1] == s0.case_id
        assert lineage.ecos_applied == ["eco_a", "eco_b"]


class TestDeterministicCaseNaming:
    """Step 7: Verify deterministic case naming at each stage."""

    def test_case_naming_is_deterministic(self):
        """Case naming follows deterministic pattern: <name>_<stage>_<derived>."""
        graph = CaseGraph()
        base = Case.create_base_case("gcd_base", "/snap")
        graph.add_case(base)

        # Create derived case
        derived = base.derive("eco_1", 0, 5, "/snap/derived")
        graph.add_case(derived)

        # Verify naming pattern
        assert "gcd_base" in derived.case_id
        assert "_0_" in derived.case_id  # stage_index
        assert "_5" in derived.case_id  # derived_index

    def test_case_naming_is_unique_across_stages(self):
        """Case names are unique even across different stages."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/snap")
        graph.add_case(base)

        # Create cases at different stages
        s0 = base.derive("eco_a", 0, 1, "/s0")
        graph.add_case(s0)

        s1 = s0.derive("eco_b", 1, 0, "/s1")
        graph.add_case(s1)

        # All IDs should be unique
        all_ids = [c.case_id for c in graph.cases.values()]
        assert len(all_ids) == len(set(all_ids))
        assert s0.case_id != s1.case_id


class TestBuildCompleteCaseLineageDAG:
    """Step 8: Build complete case lineage DAG."""

    def test_build_complete_dag_structure(self):
        """Can build complete DAG with all cases and relationships."""
        graph = CaseGraph()
        base = Case.create_base_case("gcd", "/snap", metadata={"wns_ps": -500})
        graph.add_case(base)

        # Stage 0: 5 cases
        survivors = []
        for i in range(5):
            s0 = base.derive(f"eco_{i}", 0, i + 1, f"/s0/{i}", metadata={"wns_ps": -500 + i*50})
            graph.add_case(s0)
            if i >= 2:
                survivors.append(s0)

        # Stage 1: 9 cases (3 from each survivor)
        for sidx, surv in enumerate(survivors):
            for eidx in range(3):
                s1 = surv.derive(f"s1_eco_{eidx}", 1, sidx*3+eidx, f"/s1/{sidx}_{eidx}",
                               metadata={"wns_ps": surv.metadata["wns_ps"] + 30})
                graph.add_case(s1)

        # Export DAG
        dag = graph.export_dag()

        assert "nodes" in dag
        assert "edges" in dag
        assert "statistics" in dag
        assert len(dag["nodes"]) == 15  # 1 base + 5 s0 + 9 s1
        assert len(dag["edges"]) == 14  # 5 from base + 9 from survivors

    def test_dag_contains_all_metadata(self):
        """DAG export includes all case metadata."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/snap", metadata={"wns_ps": -1000, "area": 5000})
        graph.add_case(base)

        derived = base.derive("eco_1", 0, 1, "/snap", metadata={"wns_ps": -900, "area": 5100})
        graph.add_case(derived)

        dag = graph.export_dag()

        # Find derived case node
        derived_node = next(n for n in dag["nodes"] if n["case_id"] == derived.case_id)
        assert derived_node["metadata"]["wns_ps"] == -900
        assert derived_node["metadata"]["area"] == 5100


class TestExportDAGInGraphvizDOT:
    """Step 9: Export DAG in Graphviz DOT format."""

    def test_export_dag_to_dot_format(self):
        """Can export DAG in Graphviz DOT format."""
        graph = CaseGraph()
        base = Case.create_base_case("gcd_base", "/snap")
        graph.add_case(base)

        derived = base.derive("buffer_insertion", 0, 1, "/snap/derived")
        graph.add_case(derived)

        dot_content = graph.export_to_dot()

        # Verify DOT format structure
        assert "digraph CaseLineage" in dot_content
        assert "rankdir=TB" in dot_content
        assert "gcd_base" in dot_content
        assert "buffer_insertion" in dot_content

    def test_dot_export_includes_edges(self):
        """DOT export includes edges representing parent-child relationships."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/snap")
        graph.add_case(base)

        derived = base.derive("eco_a", 0, 1, "/snap")
        graph.add_case(derived)

        dot_content = graph.export_to_dot()

        # Should have arrow from base to derived
        assert "->" in dot_content
        assert "eco_a" in dot_content  # Edge label


class TestRenderDAGAsPNG:
    """Step 10: Render DAG as PNG visualization."""

    def test_render_dag_to_png_file(self, tmp_path):
        """Can render DAG to PNG file using Graphviz."""
        graph = CaseGraph()
        base = Case.create_base_case("gcd", "/snap")
        graph.add_case(base)

        derived = base.derive("eco_1", 0, 1, "/snap")
        graph.add_case(derived)

        output_file = tmp_path / "lineage.png"

        # Mock subprocess to simulate successful rendering
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = graph.render_to_png(output_file)

        assert result is True
        mock_run.assert_called_once()

    def test_render_invokes_dot_command(self, tmp_path):
        """PNG rendering invokes 'dot' command with correct arguments."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/snap")
        graph.add_case(base)

        output_file = tmp_path / "dag.png"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            graph.render_to_png(output_file)

            # Verify command
            args = mock_run.call_args[0][0]
            assert args[0] == "dot"
            assert "-Tpng" in args
            assert str(output_file) in args


class TestDAGShowsAllDerivationPaths:
    """Step 11: Verify DAG shows all derivation paths."""

    def test_dag_shows_all_paths_from_base_to_leaves(self):
        """DAG visualization shows all derivation paths."""
        graph = CaseGraph()
        base = Case.create_base_case("gcd", "/snap")
        graph.add_case(base)

        # Create branching structure
        s0_a = base.derive("eco_a", 0, 1, "/s0_a")
        s0_b = base.derive("eco_b", 0, 2, "/s0_b")
        graph.add_case(s0_a)
        graph.add_case(s0_b)

        s1_a1 = s0_a.derive("eco_a1", 1, 0, "/s1_a1")
        s1_a2 = s0_a.derive("eco_a2", 1, 1, "/s1_a2")
        graph.add_case(s1_a1)
        graph.add_case(s1_a2)

        # Export and verify all paths are represented
        dag = graph.export_dag()

        # Should have 4 edges: base->s0_a, base->s0_b, s0_a->s1_a1, s0_a->s1_a2
        assert len(dag["edges"]) == 4

        # Verify specific edges exist
        edge_pairs = [(e["source"], e["target"]) for e in dag["edges"]]
        assert (base.case_id, s0_a.case_id) in edge_pairs
        assert (base.case_id, s0_b.case_id) in edge_pairs
        assert (s0_a.case_id, s1_a1.case_id) in edge_pairs
        assert (s0_a.case_id, s1_a2.case_id) in edge_pairs

    def test_leaf_cases_are_correctly_identified(self):
        """Leaf cases (no children) are correctly identified."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/snap")
        graph.add_case(base)

        intermediate = base.derive("eco_a", 0, 1, "/inter")
        graph.add_case(intermediate)

        leaf1 = intermediate.derive("eco_b", 1, 0, "/leaf1")
        leaf2 = intermediate.derive("eco_c", 1, 1, "/leaf2")
        graph.add_case(leaf1)
        graph.add_case(leaf2)

        # Get leaf cases
        leaves = graph.get_leaf_cases()

        assert len(leaves) == 2
        leaf_ids = {l.case_id for l in leaves}
        assert leaf1.case_id in leaf_ids
        assert leaf2.case_id in leaf_ids
        assert base.case_id not in leaf_ids
        assert intermediate.case_id not in leaf_ids


class TestAnnotateDAGNodesWithMetrics:
    """Step 12: Annotate DAG nodes with metrics (WNS, congestion)."""

    def test_export_dot_with_metric_annotation(self):
        """DOT export can include metric annotations in node labels."""
        graph = CaseGraph()
        base = Case.create_base_case(
            "gcd",
            "/snap",
            metadata={"wns_ps": -500, "congestion_score": 0.8}
        )
        graph.add_case(base)

        derived = base.derive(
            "buffer_insert",
            0, 1, "/snap",
            metadata={"wns_ps": -400, "congestion_score": 0.75}
        )
        graph.add_case(derived)

        # Export with metrics
        dot_with_metrics = graph.export_to_dot(annotate_metrics=True)

        # Verify metrics appear in labels
        assert "WNS:" in dot_with_metrics
        assert "-500" in dot_with_metrics or "-400" in dot_with_metrics
        assert "Cong:" in dot_with_metrics

    def test_metrics_not_included_by_default(self):
        """Metrics are not included in DOT export by default."""
        graph = CaseGraph()
        base = Case.create_base_case(
            "test",
            "/snap",
            metadata={"wns_ps": -1000}
        )
        graph.add_case(base)

        dot_default = graph.export_to_dot(annotate_metrics=False)

        # WNS should not appear
        assert "WNS:" not in dot_default

    def test_render_png_with_metrics(self, tmp_path):
        """PNG rendering can include metric annotations."""
        graph = CaseGraph()
        base = Case.create_base_case(
            "gcd",
            "/snap",
            metadata={"wns_ps": -500, "area": 5000}
        )
        graph.add_case(base)

        output_file = tmp_path / "annotated.png"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            graph.render_to_png(output_file, annotate_metrics=True)

            # Verify DOT content passed to subprocess includes metrics
            call_kwargs = mock_run.call_args[1]
            dot_input = call_kwargs["input"].decode("utf-8")
            assert "WNS:" in dot_input


class TestIdentifyWinningPath:
    """Step 13: Identify winning path through DAG."""

    def test_identify_winning_path_by_wns(self):
        """Can identify winning path based on WNS metric."""
        graph = CaseGraph()
        base = Case.create_base_case("gcd", "/snap", metadata={"wns_ps": -500})
        graph.add_case(base)

        # Create paths with different outcomes
        # Path 1: base -> eco_a -> eco_a1 (WNS: -300)
        s0_a = base.derive("eco_a", 0, 1, "/s0_a", metadata={"wns_ps": -400})
        graph.add_case(s0_a)
        s1_a1 = s0_a.derive("eco_a1", 1, 0, "/s1_a1", metadata={"wns_ps": -300})
        graph.add_case(s1_a1)

        # Path 2: base -> eco_b -> eco_b1 (WNS: -350)
        s0_b = base.derive("eco_b", 0, 2, "/s0_b", metadata={"wns_ps": -450})
        graph.add_case(s0_b)
        s1_b1 = s0_b.derive("eco_b1", 1, 1, "/s1_b1", metadata={"wns_ps": -350})
        graph.add_case(s1_b1)

        # Identify winning path (best WNS = highest = -300)
        winning_path = graph.identify_winning_path(metric_key="wns_ps", minimize=False)

        # Should be: base -> s0_a -> s1_a1
        assert len(winning_path) == 3
        assert winning_path[0] == base.case_id
        assert winning_path[1] == s0_a.case_id
        assert winning_path[2] == s1_a1.case_id

    def test_identify_winning_path_by_congestion(self):
        """Can identify winning path by minimizing congestion."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/snap", metadata={"congestion_score": 1.0})
        graph.add_case(base)

        # Path 1: Lower congestion (better)
        leaf1 = base.derive("eco_a", 0, 1, "/leaf1", metadata={"congestion_score": 0.5})
        graph.add_case(leaf1)

        # Path 2: Higher congestion (worse)
        leaf2 = base.derive("eco_b", 0, 2, "/leaf2", metadata={"congestion_score": 0.8})
        graph.add_case(leaf2)

        # Minimize congestion
        winning_path = graph.identify_winning_path(metric_key="congestion_score", minimize=True)

        assert winning_path[-1] == leaf1.case_id


class TestGenerateLineageReport:
    """Step 14: Generate lineage report with ECO sequence for winner."""

    def test_generate_lineage_report_for_winning_path(self):
        """Can generate human-readable lineage report for winning path."""
        graph = CaseGraph()
        base = Case.create_base_case("gcd", "/snap", metadata={"wns_ps": -500})
        graph.add_case(base)

        # Create winning path
        s0 = base.derive("buffer_insert", 0, 1, "/s0", metadata={"wns_ps": -400})
        graph.add_case(s0)

        s1 = s0.derive("gate_size", 1, 0, "/s1", metadata={"wns_ps": -300})
        graph.add_case(s1)

        # Generate report
        report = graph.generate_lineage_report(
            winning_path=[base.case_id, s0.case_id, s1.case_id],
            metric_key="wns_ps"
        )

        # Verify report contents
        assert "LINEAGE REPORT" in report
        assert "WINNING PATH" in report
        assert "buffer_insert" in report
        assert "gate_size" in report
        assert "-300" in report  # Final WNS
        assert "SUMMARY" in report

    def test_lineage_report_includes_eco_sequence(self):
        """Lineage report clearly shows ECO application sequence."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/snap", metadata={"wns_ps": -1000})
        graph.add_case(base)

        s0 = base.derive("eco_1", 0, 1, "/s0", metadata={"wns_ps": -900})
        graph.add_case(s0)

        s1 = s0.derive("eco_2", 1, 0, "/s1", metadata={"wns_ps": -800})
        graph.add_case(s1)

        report = graph.generate_lineage_report(metric_key="wns_ps")

        # Should list ECOs in order
        assert "eco_1" in report
        assert "eco_2" in report
        assert report.index("eco_1") < report.index("eco_2")

    def test_lineage_report_shows_metric_progression(self):
        """Lineage report shows how metrics improve along the path."""
        graph = CaseGraph()
        base = Case.create_base_case("test", "/snap", metadata={"wns_ps": -1000, "area": 5000})
        graph.add_case(base)

        s0 = base.derive("eco_a", 0, 1, "/s0", metadata={"wns_ps": -800, "area": 5100})
        graph.add_case(s0)

        report = graph.generate_lineage_report(metric_key="wns_ps")

        # Should show metrics at each step
        assert "-1000" in report
        assert "-800" in report
        assert "area" in report


class TestCompleteE2EWorkflow:
    """Complete end-to-end workflow integration test."""

    def test_complete_case_lineage_e2e_workflow(self, tmp_path):
        """
        Complete E2E workflow: Create complex Study, track lineage, export DAG,
        render visualization, identify winner, generate report.
        """
        # Step 1-2: Create Study with base case
        graph = CaseGraph()
        base = Case.create_base_case(
            base_name="gcd_base",
            snapshot_path="/snapshots/gcd_base",
            metadata={"wns_ps": -500, "congestion_score": 0.8, "area": 10000}
        )
        graph.add_case(base)

        # Step 3: Apply 5 different ECOs in Stage 0
        eco_names = ["buffer_insertion", "gate_sizing", "vt_swap", "pin_swap", "clock_skew"]
        stage0_cases = []
        for i, eco_name in enumerate(eco_names):
            derived = base.derive(
                eco_name=eco_name,
                new_stage_index=0,
                derived_index=i + 1,
                snapshot_path=f"/snapshots/s0_{i}",
                metadata={
                    "wns_ps": -500 + (i + 1) * 50,
                    "congestion_score": 0.8 - i * 0.05,
                    "area": 10000 + i * 100
                }
            )
            graph.add_case(derived)
            stage0_cases.append(derived)

        # Step 4: Select top 3 survivors
        sorted_s0 = sorted(stage0_cases, key=lambda c: c.metadata["wns_ps"], reverse=True)
        survivors = sorted_s0[:3]

        # Step 5: Apply 3 ECOs to each survivor (9 Stage 1 cases)
        s1_eco_names = ["opt_a", "opt_b", "opt_c"]
        for surv_idx, survivor in enumerate(survivors):
            for eco_idx, eco_name in enumerate(s1_eco_names):
                s1_case = survivor.derive(
                    eco_name=eco_name,
                    new_stage_index=1,
                    derived_index=surv_idx * 3 + eco_idx,
                    snapshot_path=f"/snapshots/s1_{surv_idx}_{eco_idx}",
                    metadata={
                        "wns_ps": survivor.metadata["wns_ps"] + 30 + eco_idx * 10,
                        "congestion_score": survivor.metadata["congestion_score"] - 0.05,
                        "area": survivor.metadata["area"] + 50
                    }
                )
                graph.add_case(s1_case)

        # Step 6-7: Verify parent-child tracking and deterministic naming
        assert graph.count_cases() == 15  # 1 base + 5 s0 + 9 s1
        is_valid, errors = graph.verify_dag_integrity()
        assert is_valid, f"DAG integrity errors: {errors}"

        # Step 8: Build complete DAG
        dag = graph.export_dag()
        assert len(dag["nodes"]) == 15
        assert len(dag["edges"]) == 14

        # Step 9: Export to DOT format
        dot_basic = graph.export_to_dot(annotate_metrics=False)
        assert "digraph CaseLineage" in dot_basic

        # Step 10: Render to PNG
        png_file = tmp_path / "lineage.png"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            success = graph.render_to_png(png_file, annotate_metrics=False)
        assert success

        # Step 11: Verify all derivation paths visible
        leaves = graph.get_leaf_cases()
        assert len(leaves) == 11  # 9 Stage 1 cases + 2 non-survivor Stage 0 cases

        # Step 12: Export with metric annotations
        dot_annotated = graph.export_to_dot(annotate_metrics=True)
        assert "WNS:" in dot_annotated
        assert "Cong:" in dot_annotated

        # Render annotated version
        png_annotated = tmp_path / "lineage_annotated.png"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            success = graph.render_to_png(png_annotated, annotate_metrics=True)
        assert success

        # Step 13: Identify winning path
        winning_path = graph.identify_winning_path(metric_key="wns_ps", minimize=False)
        assert len(winning_path) >= 3  # base -> s0 -> s1
        assert winning_path[0] == base.case_id

        # Step 14: Generate lineage report
        report = graph.generate_lineage_report(
            winning_path=winning_path,
            metric_key="wns_ps",
            minimize=False
        )

        # Verify report contents
        assert "LINEAGE REPORT" in report
        assert "WINNING PATH" in report
        assert "SUMMARY" in report
        assert base.case_id in report

        # Verify ECO sequence is documented
        winning_case = graph.cases[winning_path[-1]]
        lineage = graph.get_lineage(winning_case.case_id)
        for eco in lineage.ecos_applied:
            assert eco in report

        print("\n" + report)  # Output for inspection

        # Success: Complete E2E workflow executed
        assert True
