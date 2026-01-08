"""Tests for machine-readable provenance chain generation."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.controller.case import Case, CaseGraph, CaseLineage
from src.controller.eco import ECOMetadata
from src.trial_runner.provenance import ToolProvenance
from src.trial_runner.provenance_chain import (
    CaseProvenanceRecord,
    ECOApplicationRecord,
    ProvenanceChain,
    SnapshotProvenance,
    export_provenance_chain,
    generate_provenance_chain,
)


class TestSnapshotProvenance:
    """Test snapshot provenance recording."""

    def test_snapshot_provenance_creation(self):
        """Test creating snapshot provenance record."""
        snapshot = SnapshotProvenance(
            snapshot_path="/path/to/snapshot",
            snapshot_hash="abc123def456",
            pdk_name="nangate45",
            pdk_version="1.0",
        )

        assert snapshot.snapshot_path == "/path/to/snapshot"
        assert snapshot.snapshot_hash == "abc123def456"
        assert snapshot.pdk_name == "nangate45"
        assert snapshot.pdk_version == "1.0"

    def test_snapshot_provenance_to_dict(self):
        """Test snapshot provenance serialization."""
        snapshot = SnapshotProvenance(
            snapshot_path="/path/to/snapshot",
            snapshot_hash="abc123",
            pdk_name="asap7",
        )

        data = snapshot.to_dict()

        assert data["snapshot_path"] == "/path/to/snapshot"
        assert data["snapshot_hash"] == "abc123"
        assert data["pdk_name"] == "asap7"
        assert "pdk_version" in data


class TestECOApplicationRecord:
    """Test ECO application recording."""

    def test_eco_application_record_creation(self):
        """Test creating ECO application record."""
        eco_record = ECOApplicationRecord(
            eco_name="buffer_insertion",
            eco_class="placement_local",
            parameters={"max_capacitance": 50.0},
            applied_at_stage=0,
            timestamp="2026-01-08T12:00:00Z",
        )

        assert eco_record.eco_name == "buffer_insertion"
        assert eco_record.eco_class == "placement_local"
        assert eco_record.parameters == {"max_capacitance": 50.0}
        assert eco_record.applied_at_stage == 0

    def test_eco_application_record_to_dict(self):
        """Test ECO application record serialization."""
        eco_record = ECOApplicationRecord(
            eco_name="buffer_insertion",
            eco_class="placement_local",
            parameters={"max_capacitance": 50.0},
            applied_at_stage=0,
            timestamp="2026-01-08T12:00:00Z",
        )

        data = eco_record.to_dict()

        assert data["eco_name"] == "buffer_insertion"
        assert data["eco_class"] == "placement_local"
        assert data["parameters"] == {"max_capacitance": 50.0}
        assert data["applied_at_stage"] == 0
        assert data["timestamp"] == "2026-01-08T12:00:00Z"


class TestCaseProvenanceRecord:
    """Test case-level provenance recording."""

    def test_case_provenance_creation(self):
        """Test creating case provenance record."""
        case_prov = CaseProvenanceRecord(
            case_id="nangate45_0_1",
            parent_case_id="nangate45_base",
            stage_index=0,
            derived_index=1,
            eco_applied=ECOApplicationRecord(
                eco_name="buffer_insertion",
                eco_class="placement_local",
                parameters={},
                applied_at_stage=0,
                timestamp="2026-01-08T12:00:00Z",
            ),
        )

        assert case_prov.case_id == "nangate45_0_1"
        assert case_prov.parent_case_id == "nangate45_base"
        assert case_prov.stage_index == 0
        assert case_prov.eco_applied is not None

    def test_base_case_provenance_no_parent(self):
        """Test base case has no parent or ECO."""
        case_prov = CaseProvenanceRecord(
            case_id="nangate45_base",
            parent_case_id=None,
            stage_index=0,
            derived_index=0,
            eco_applied=None,
        )

        assert case_prov.parent_case_id is None
        assert case_prov.eco_applied is None

    def test_case_provenance_to_dict(self):
        """Test case provenance serialization."""
        case_prov = CaseProvenanceRecord(
            case_id="nangate45_0_1",
            parent_case_id="nangate45_base",
            stage_index=0,
            derived_index=1,
            eco_applied=ECOApplicationRecord(
                eco_name="buffer_insertion",
                eco_class="placement_local",
                parameters={},
                applied_at_stage=0,
                timestamp="2026-01-08T12:00:00Z",
            ),
        )

        data = case_prov.to_dict()

        assert data["case_id"] == "nangate45_0_1"
        assert data["parent_case_id"] == "nangate45_base"
        assert data["stage_index"] == 0
        assert data["eco_applied"] is not None


class TestProvenanceChain:
    """Test complete provenance chain generation."""

    def test_provenance_chain_creation(self):
        """Test creating complete provenance chain."""
        snapshot = SnapshotProvenance(
            snapshot_path="/path/to/snapshot",
            snapshot_hash="abc123",
            pdk_name="nangate45",
        )

        tool_prov = ToolProvenance(
            container_image="efabless/openlane",
            container_tag="ci2504-dev-amd64",
            tool_version="2.0.0",
        )

        case_lineage = [
            CaseProvenanceRecord(
                case_id="nangate45_base",
                parent_case_id=None,
                stage_index=0,
                derived_index=0,
                eco_applied=None,
            ),
            CaseProvenanceRecord(
                case_id="nangate45_0_1",
                parent_case_id="nangate45_base",
                stage_index=0,
                derived_index=1,
                eco_applied=ECOApplicationRecord(
                    eco_name="buffer_insertion",
                    eco_class="placement_local",
                    parameters={},
                    applied_at_stage=0,
                    timestamp="2026-01-08T12:00:00Z",
                ),
            ),
        ]

        study_config = {
            "study_name": "test_study",
            "safety_domain": "sandbox",
            "stages": [{"budget": 10}],
        }

        chain = ProvenanceChain(
            snapshot=snapshot,
            tool_provenance=tool_prov,
            case_lineage=case_lineage,
            study_config=study_config,
            generated_at="2026-01-08T12:00:00Z",
        )

        assert chain.snapshot.snapshot_hash == "abc123"
        assert chain.tool_provenance.container_image == "efabless/openlane"
        assert len(chain.case_lineage) == 2
        assert chain.study_config["study_name"] == "test_study"

    def test_provenance_chain_to_dict(self):
        """Test provenance chain serialization."""
        snapshot = SnapshotProvenance(
            snapshot_path="/path/to/snapshot",
            snapshot_hash="abc123",
            pdk_name="nangate45",
        )

        tool_prov = ToolProvenance(
            container_image="efabless/openlane",
            container_tag="ci2504-dev-amd64",
        )

        case_lineage = [
            CaseProvenanceRecord(
                case_id="nangate45_base",
                parent_case_id=None,
                stage_index=0,
                derived_index=0,
                eco_applied=None,
            ),
        ]

        chain = ProvenanceChain(
            snapshot=snapshot,
            tool_provenance=tool_prov,
            case_lineage=case_lineage,
            study_config={"study_name": "test"},
            generated_at="2026-01-08T12:00:00Z",
        )

        data = chain.to_dict()

        assert "snapshot" in data
        assert "tool_provenance" in data
        assert "case_lineage" in data
        assert "study_config" in data
        assert "generated_at" in data
        assert data["format_version"] == "1.0"

    def test_provenance_chain_eco_sequence(self):
        """Test provenance chain tracks ECO sequence."""
        case_lineage = [
            CaseProvenanceRecord(
                case_id="nangate45_base",
                parent_case_id=None,
                stage_index=0,
                derived_index=0,
                eco_applied=None,
            ),
            CaseProvenanceRecord(
                case_id="nangate45_0_1",
                parent_case_id="nangate45_base",
                stage_index=0,
                derived_index=1,
                eco_applied=ECOApplicationRecord(
                    eco_name="buffer_insertion",
                    eco_class="placement_local",
                    parameters={},
                    applied_at_stage=0,
                    timestamp="2026-01-08T12:00:00Z",
                ),
            ),
            CaseProvenanceRecord(
                case_id="nangate45_1_1",
                parent_case_id="nangate45_0_1",
                stage_index=1,
                derived_index=1,
                eco_applied=ECOApplicationRecord(
                    eco_name="cell_sizing",
                    eco_class="topology_neutral",
                    parameters={"target_slack": 100},
                    applied_at_stage=1,
                    timestamp="2026-01-08T12:05:00Z",
                ),
            ),
        ]

        eco_sequence = [c.eco_applied for c in case_lineage if c.eco_applied]

        assert len(eco_sequence) == 2
        assert eco_sequence[0].eco_name == "buffer_insertion"
        assert eco_sequence[1].eco_name == "cell_sizing"


class TestGenerateProvenanceChain:
    """Test provenance chain generation from case graph."""

    def test_generate_provenance_for_base_case(self):
        """Test generating provenance for base case."""
        case_graph = CaseGraph()
        base_case = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/path/to/snapshot",
        )
        case_graph.add_case(base_case)

        snapshot = SnapshotProvenance(
            snapshot_path="/path/to/snapshot",
            snapshot_hash="abc123",
            pdk_name="nangate45",
        )

        tool_prov = ToolProvenance(
            container_image="efabless/openlane",
            container_tag="ci2504-dev-amd64",
        )

        study_config = {
            "study_name": "test_study",
            "safety_domain": "sandbox",
            "base_case_id": "nangate45_base",
            "stages": [],
        }

        chain = generate_provenance_chain(
            case_id=base_case.case_id,  # Will be nangate45_base_0_0
            case_graph=case_graph,
            snapshot=snapshot,
            tool_provenance=tool_prov,
            study_config=study_config,
        )

        assert len(chain.case_lineage) == 1
        assert chain.case_lineage[0].case_id == base_case.case_id
        assert chain.case_lineage[0].parent_case_id is None
        assert chain.case_lineage[0].eco_applied is None

    def test_generate_provenance_for_derived_case(self):
        """Test generating provenance for derived case with lineage."""
        case_graph = CaseGraph()

        # Add base case
        base_case = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/path/to/snapshot",
        )
        case_graph.add_case(base_case)

        # Add derived case
        eco_meta = ECOMetadata(
            name="buffer_insertion",
            eco_class="placement_local",
            description="Insert buffers",
        )

        derived_case = base_case.derive(
            eco_name="buffer_insertion",
            new_stage_index=1,
            derived_index=1,
            snapshot_path="/path/to/derived",
        )
        derived_case.eco_metadata = eco_meta
        case_graph.add_case(derived_case)

        snapshot = SnapshotProvenance(
            snapshot_path="/path/to/snapshot",
            snapshot_hash="abc123",
            pdk_name="nangate45",
        )

        tool_prov = ToolProvenance(
            container_image="efabless/openlane",
            container_tag="ci2504-dev-amd64",
        )

        study_config = {
            "study_name": "test_study",
            "safety_domain": "sandbox",
            "base_case_id": "nangate45_base",
            "stages": [],
        }

        chain = generate_provenance_chain(
            case_id=derived_case.case_id,
            case_graph=case_graph,
            snapshot=snapshot,
            tool_provenance=tool_prov,
            study_config=study_config,
        )

        assert len(chain.case_lineage) == 2
        # First entry is base case
        assert chain.case_lineage[0].case_id == base_case.case_id
        # Second entry is derived case
        assert chain.case_lineage[1].case_id == derived_case.case_id
        assert chain.case_lineage[1].parent_case_id == base_case.case_id
        assert chain.case_lineage[1].eco_applied is not None
        assert chain.case_lineage[1].eco_applied.eco_name == "buffer_insertion"


class TestExportProvenanceChain:
    """Test exporting provenance chain to file."""

    def test_export_provenance_to_json(self):
        """Test exporting provenance chain to JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot = SnapshotProvenance(
                snapshot_path="/path/to/snapshot",
                snapshot_hash="abc123",
                pdk_name="nangate45",
            )

            tool_prov = ToolProvenance(
                container_image="efabless/openlane",
                container_tag="ci2504-dev-amd64",
            )

            case_lineage = [
                CaseProvenanceRecord(
                    case_id="nangate45_base",
                    parent_case_id=None,
                    stage_index=0,
                    derived_index=0,
                    eco_applied=None,
                ),
            ]

            chain = ProvenanceChain(
                snapshot=snapshot,
                tool_provenance=tool_prov,
                case_lineage=case_lineage,
                study_config={"study_name": "test"},
                generated_at="2026-01-08T12:00:00Z",
            )

            output_path = Path(tmpdir) / "provenance_chain.json"
            export_provenance_chain(chain, output_path)

            assert output_path.exists()

            # Verify JSON is valid
            with open(output_path) as f:
                data = json.load(f)

            assert data["format_version"] == "1.0"
            assert "snapshot" in data
            assert "tool_provenance" in data
            assert "case_lineage" in data

    def test_export_provenance_is_human_readable(self):
        """Test exported provenance is human-readable (pretty-printed)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot = SnapshotProvenance(
                snapshot_path="/path/to/snapshot",
                snapshot_hash="abc123",
                pdk_name="nangate45",
            )

            tool_prov = ToolProvenance(
                container_image="efabless/openlane",
                container_tag="ci2504-dev-amd64",
            )

            case_lineage = [
                CaseProvenanceRecord(
                    case_id="nangate45_base",
                    parent_case_id=None,
                    stage_index=0,
                    derived_index=0,
                    eco_applied=None,
                ),
            ]

            chain = ProvenanceChain(
                snapshot=snapshot,
                tool_provenance=tool_prov,
                case_lineage=case_lineage,
                study_config={"study_name": "test"},
                generated_at="2026-01-08T12:00:00Z",
            )

            output_path = Path(tmpdir) / "provenance_chain.json"
            export_provenance_chain(chain, output_path)

            # Check file is human-readable (has newlines/indentation)
            with open(output_path) as f:
                content = f.read()

            # Pretty-printed JSON has multiple lines
            assert content.count("\n") > 10
            # Has indentation
            assert "  " in content or "\t" in content


class TestProvenanceChainCompleteness:
    """Test provenance chain includes all required information."""

    def test_provenance_includes_snapshot_hash(self):
        """Step 2: Record provenance includes snapshot hash."""
        snapshot = SnapshotProvenance(
            snapshot_path="/path/to/snapshot",
            snapshot_hash="abc123def456",
            pdk_name="nangate45",
        )

        assert snapshot.snapshot_hash == "abc123def456"

    def test_provenance_includes_container_image(self):
        """Step 2: Record provenance includes container image."""
        tool_prov = ToolProvenance(
            container_image="efabless/openlane",
            container_tag="ci2504-dev-amd64",
        )

        assert tool_prov.container_image == "efabless/openlane"
        assert tool_prov.container_tag == "ci2504-dev-amd64"

    def test_provenance_includes_tool_version(self):
        """Step 2: Record provenance includes tool versions."""
        tool_prov = ToolProvenance(
            container_image="efabless/openlane",
            container_tag="ci2504-dev-amd64",
            tool_version="2.0.0",
        )

        assert tool_prov.tool_version == "2.0.0"

    def test_provenance_includes_parent_case_lineage(self):
        """Step 3: Record parent case lineage."""
        case_lineage = [
            CaseProvenanceRecord(
                case_id="nangate45_base",
                parent_case_id=None,
                stage_index=0,
                derived_index=0,
                eco_applied=None,
            ),
            CaseProvenanceRecord(
                case_id="nangate45_0_1",
                parent_case_id="nangate45_base",
                stage_index=0,
                derived_index=1,
                eco_applied=None,
            ),
        ]

        assert case_lineage[1].parent_case_id == "nangate45_base"

    def test_provenance_includes_eco_sequence(self):
        """Step 4: Record ECO sequence applied."""
        case_lineage = [
            CaseProvenanceRecord(
                case_id="nangate45_base",
                parent_case_id=None,
                stage_index=0,
                derived_index=0,
                eco_applied=None,
            ),
            CaseProvenanceRecord(
                case_id="nangate45_0_1",
                parent_case_id="nangate45_base",
                stage_index=0,
                derived_index=1,
                eco_applied=ECOApplicationRecord(
                    eco_name="buffer_insertion",
                    eco_class="placement_local",
                    parameters={},
                    applied_at_stage=0,
                    timestamp="2026-01-08T12:00:00Z",
                ),
            ),
        ]

        eco_sequence = [c.eco_applied for c in case_lineage if c.eco_applied]
        assert len(eco_sequence) == 1
        assert eco_sequence[0].eco_name == "buffer_insertion"

    def test_provenance_includes_study_config(self):
        """Step 5: Record configuration and policy state."""
        study_config = {
            "study_name": "test_study",
            "safety_domain": "sandbox",
            "stages": [{"budget": 10}],
        }

        chain = ProvenanceChain(
            snapshot=SnapshotProvenance(
                snapshot_path="/path",
                snapshot_hash="abc",
                pdk_name="nangate45",
            ),
            tool_provenance=ToolProvenance(
                container_image="efabless/openlane",
                container_tag="ci2504-dev-amd64",
            ),
            case_lineage=[],
            study_config=study_config,
            generated_at="2026-01-08T12:00:00Z",
        )

        assert chain.study_config["study_name"] == "test_study"
        assert chain.study_config["safety_domain"] == "sandbox"

    def test_provenance_exports_as_structured_document(self):
        """Step 6: Export provenance chain as structured document."""
        with tempfile.TemporaryDirectory() as tmpdir:
            chain = ProvenanceChain(
                snapshot=SnapshotProvenance(
                    snapshot_path="/path",
                    snapshot_hash="abc",
                    pdk_name="nangate45",
                ),
                tool_provenance=ToolProvenance(
                    container_image="efabless/openlane",
                    container_tag="ci2504-dev-amd64",
                ),
                case_lineage=[],
                study_config={"study_name": "test"},
                generated_at="2026-01-08T12:00:00Z",
            )

            output_path = Path(tmpdir) / "provenance.json"
            export_provenance_chain(chain, output_path)

            assert output_path.exists()

            # Verify it's structured JSON
            with open(output_path) as f:
                data = json.load(f)

            assert "snapshot" in data
            assert "tool_provenance" in data
            assert "case_lineage" in data
            assert "study_config" in data
