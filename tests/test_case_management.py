"""Tests for case management and lineage tracking."""

import pytest

from controller.case import Case, CaseGraph, CaseLineage
from controller.types import CaseIdentifier
from controller.exceptions import (
    CaseNotFoundError,
    DuplicateCaseError,
    InvalidCaseIdentifierError,
    ParentCaseNotFoundError,
)


class TestCaseIdentifier:
    """Test deterministic case naming contract."""

    def test_case_identifier_str(self):
        """Test string representation follows contract."""
        identifier = CaseIdentifier(
            case_name="nangate45_base",
            stage_index=0,
            derived_index=0,
        )
        assert str(identifier) == "nangate45_base_0_0"

    def test_case_identifier_with_stage_progression(self):
        """Test naming with stage progression."""
        identifier = CaseIdentifier(
            case_name="nangate45_base",
            stage_index=2,
            derived_index=5,
        )
        assert str(identifier) == "nangate45_base_2_5"

    def test_case_identifier_from_string(self):
        """Test parsing case ID from string."""
        case_id = "nangate45_base_1_3"
        identifier = CaseIdentifier.from_string(case_id)

        assert identifier.case_name == "nangate45_base"
        assert identifier.stage_index == 1
        assert identifier.derived_index == 3

    def test_case_identifier_from_string_with_underscores(self):
        """Test parsing case ID with underscores in base name."""
        case_id = "asap7_broken_design_0_1"
        identifier = CaseIdentifier.from_string(case_id)

        assert identifier.case_name == "asap7_broken_design"
        assert identifier.stage_index == 0
        assert identifier.derived_index == 1

    def test_case_identifier_from_string_invalid(self):
        """Test parsing invalid case ID raises error."""
        with pytest.raises(InvalidCaseIdentifierError, match=r"\[N2-E-100\].*Invalid case identifier format"):
            CaseIdentifier.from_string("invalid_name")

    def test_case_identifier_from_string_non_numeric(self):
        """Test parsing case ID with non-numeric indices."""
        with pytest.raises(InvalidCaseIdentifierError, match=r"\[N2-E-100\].*Invalid case identifier format"):
            CaseIdentifier.from_string("nangate45_base_0_abc")

    def test_case_identifier_roundtrip(self):
        """Test that str -> parse -> str is stable."""
        original = CaseIdentifier(
            case_name="sky130_test",
            stage_index=3,
            derived_index=7,
        )
        parsed = CaseIdentifier.from_string(str(original))

        assert parsed.case_name == original.case_name
        assert parsed.stage_index == original.stage_index
        assert parsed.derived_index == original.derived_index
        assert str(parsed) == str(original)


class TestCase:
    """Test Case dataclass and methods."""

    def test_create_base_case(self):
        """Test creating base case."""
        base = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/path/to/snapshot",
        )

        assert base.is_base_case
        assert base.parent_id is None
        assert base.eco_applied is None
        assert base.stage_index == 0
        assert base.case_id == "nangate45_base_0_0"
        assert base.snapshot_path == "/path/to/snapshot"

    def test_base_case_with_metadata(self):
        """Test base case with metadata."""
        metadata = {"pdk": "Nangate45", "version": "1.0"}
        base = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/path/to/snapshot",
            metadata=metadata,
        )

        assert base.metadata == metadata

    def test_derive_case(self):
        """Test deriving a case from base case."""
        base = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/path/to/base",
        )

        derived = base.derive(
            eco_name="buffer_fanout",
            new_stage_index=0,
            derived_index=1,
            snapshot_path="/path/to/derived",
        )

        assert not derived.is_base_case
        assert derived.parent_id == base.case_id
        assert derived.eco_applied == "buffer_fanout"
        assert derived.stage_index == 0
        assert derived.case_id == "nangate45_base_0_1"

    def test_derive_multiple_cases_same_stage(self):
        """Test deriving multiple cases in the same stage."""
        base = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/path/to/base",
        )

        derived1 = base.derive(
            eco_name="eco1",
            new_stage_index=0,
            derived_index=1,
            snapshot_path="/path/to/d1",
        )
        derived2 = base.derive(
            eco_name="eco2",
            new_stage_index=0,
            derived_index=2,
            snapshot_path="/path/to/d2",
        )

        assert derived1.case_id == "nangate45_base_0_1"
        assert derived2.case_id == "nangate45_base_0_2"
        assert derived1.eco_applied == "eco1"
        assert derived2.eco_applied == "eco2"

    def test_derive_across_stages(self):
        """Test deriving cases across stage boundaries."""
        base = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/path/to/base",
        )

        stage0_case = base.derive(
            eco_name="coarse_eco",
            new_stage_index=0,
            derived_index=1,
            snapshot_path="/path/to/s0",
        )

        stage1_case = stage0_case.derive(
            eco_name="refined_eco",
            new_stage_index=1,
            derived_index=0,
            snapshot_path="/path/to/s1",
        )

        assert stage0_case.case_id == "nangate45_base_0_1"
        assert stage1_case.case_id == "nangate45_base_1_0"
        assert stage1_case.parent_id == stage0_case.case_id

    def test_derive_with_metadata(self):
        """Test deriving case with metadata."""
        base = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/path/to/base",
        )

        metadata = {"improvement": "10%", "notes": "test"}
        derived = base.derive(
            eco_name="test_eco",
            new_stage_index=0,
            derived_index=1,
            snapshot_path="/path/to/derived",
            metadata=metadata,
        )

        assert derived.metadata == metadata


class TestCaseGraph:
    """Test CaseGraph for managing case DAG."""

    def test_empty_graph(self):
        """Test empty graph initialization."""
        graph = CaseGraph()
        assert graph.count_cases() == 0
        assert graph.get_base_case() is None

    def test_add_base_case(self):
        """Test adding base case to graph."""
        graph = CaseGraph()
        base = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/path/to/base",
        )

        graph.add_case(base)

        assert graph.count_cases() == 1
        assert graph.get_base_case() == base
        assert graph.get_case(base.case_id) == base

    def test_add_derived_case(self):
        """Test adding derived cases to graph."""
        graph = CaseGraph()
        base = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/path/to/base",
        )
        graph.add_case(base)

        derived = base.derive(
            eco_name="test_eco",
            new_stage_index=0,
            derived_index=1,
            snapshot_path="/path/to/derived",
        )
        graph.add_case(derived)

        assert graph.count_cases() == 2
        assert graph.get_case(derived.case_id) == derived

    def test_add_duplicate_case_raises_error(self):
        """Test adding duplicate case raises error."""
        graph = CaseGraph()
        base = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/path/to/base",
        )
        graph.add_case(base)

        # Try to add same case again
        with pytest.raises(DuplicateCaseError, match=r"\[N2-E-101\].*already exists"):
            graph.add_case(base)

    def test_add_case_without_parent_raises_error(self):
        """Test adding case with missing parent raises error."""
        graph = CaseGraph()
        base = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/path/to/base",
        )

        # Create derived but don't add base first
        derived = base.derive(
            eco_name="test_eco",
            new_stage_index=0,
            derived_index=1,
            snapshot_path="/path/to/derived",
        )

        with pytest.raises(ParentCaseNotFoundError, match=r"\[N2-E-102\].*Parent case.*not found"):
            graph.add_case(derived)

    def test_get_cases_by_stage(self):
        """Test getting all cases at a specific stage."""
        graph = CaseGraph()
        base = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/path/to/base",
        )
        graph.add_case(base)

        # Add multiple stage 0 cases
        for i in range(1, 4):
            derived = base.derive(
                eco_name=f"eco{i}",
                new_stage_index=0,
                derived_index=i,
                snapshot_path=f"/path/to/d{i}",
            )
            graph.add_case(derived)

        # Add a stage 1 case
        stage1_case = base.derive(
            eco_name="stage1_eco",
            new_stage_index=1,
            derived_index=0,
            snapshot_path="/path/to/s1",
        )
        graph.add_case(stage1_case)

        stage0_cases = graph.get_cases_by_stage(0)
        stage1_cases = graph.get_cases_by_stage(1)

        assert len(stage0_cases) == 4  # base + 3 derived
        assert len(stage1_cases) == 1

    def test_count_cases_by_stage(self):
        """Test counting cases at a specific stage."""
        graph = CaseGraph()
        base = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/path/to/base",
        )
        graph.add_case(base)

        for i in range(1, 6):
            derived = base.derive(
                eco_name=f"eco{i}",
                new_stage_index=0,
                derived_index=i,
                snapshot_path=f"/path/to/d{i}",
            )
            graph.add_case(derived)

        assert graph.count_cases_by_stage(0) == 6
        assert graph.count_cases_by_stage(1) == 0

    def test_get_lineage_base_case(self):
        """Test lineage for base case."""
        graph = CaseGraph()
        base = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/path/to/base",
        )
        graph.add_case(base)

        lineage = graph.get_lineage(base.case_id)

        assert lineage.case_id == base.case_id
        assert lineage.ancestors == []
        assert lineage.ecos_applied == []

    def test_get_lineage_single_derivation(self):
        """Test lineage for single-level derivation."""
        graph = CaseGraph()
        base = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/path/to/base",
        )
        graph.add_case(base)

        derived = base.derive(
            eco_name="test_eco",
            new_stage_index=0,
            derived_index=1,
            snapshot_path="/path/to/derived",
        )
        graph.add_case(derived)

        lineage = graph.get_lineage(derived.case_id)

        assert lineage.case_id == derived.case_id
        assert lineage.ancestors == [base.case_id]
        assert lineage.ecos_applied == ["test_eco"]

    def test_get_lineage_multi_stage(self):
        """Test lineage across multiple stages."""
        graph = CaseGraph()
        base = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/path/to/base",
        )
        graph.add_case(base)

        # Stage 0 derivation
        stage0 = base.derive(
            eco_name="coarse_opt",
            new_stage_index=0,
            derived_index=1,
            snapshot_path="/path/to/s0",
        )
        graph.add_case(stage0)

        # Stage 1 derivation
        stage1 = stage0.derive(
            eco_name="refined_opt",
            new_stage_index=1,
            derived_index=0,
            snapshot_path="/path/to/s1",
        )
        graph.add_case(stage1)

        # Stage 2 derivation
        stage2 = stage1.derive(
            eco_name="final_opt",
            new_stage_index=2,
            derived_index=0,
            snapshot_path="/path/to/s2",
        )
        graph.add_case(stage2)

        lineage = graph.get_lineage(stage2.case_id)

        assert lineage.case_id == stage2.case_id
        assert lineage.ancestors == [base.case_id, stage0.case_id, stage1.case_id]
        assert lineage.ecos_applied == ["coarse_opt", "refined_opt", "final_opt"]

    def test_get_lineage_nonexistent_case(self):
        """Test lineage for nonexistent case raises error."""
        graph = CaseGraph()

        with pytest.raises(CaseNotFoundError, match=r"\[N2-E-103\].*not found in case graph"):
            graph.get_lineage("nonexistent_0_0")

    def test_lineage_str_base_case(self):
        """Test lineage string representation for base case."""
        lineage = CaseLineage(
            case_id="nangate45_base_0_0",
            ancestors=[],
            ecos_applied=[],
        )

        assert str(lineage) == "nangate45_base_0_0 (base case)"

    def test_lineage_str_derived_case(self):
        """Test lineage string representation for derived case."""
        lineage = CaseLineage(
            case_id="nangate45_base_1_0",
            ancestors=["nangate45_base_0_0", "nangate45_base_0_1"],
            ecos_applied=["eco1", "eco2"],
        )

        result = str(lineage)
        assert "nangate45_base_0_0" in result
        assert "nangate45_base_0_1" in result
        assert "nangate45_base_1_0" in result
        assert "[eco1]" in result
        assert "[eco2]" in result
