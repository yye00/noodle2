"""Tests for PDK override functionality."""

import json
import tempfile
from pathlib import Path

import pytest

from src.pdk.override import (
    PDKOverride,
    create_pdk_override,
    document_pdk_override_in_provenance,
    verify_pdk_accessibility,
)


class TestPDKOverride:
    """Tests for PDKOverride dataclass."""

    def test_create_pdk_override(self, tmp_path: Path) -> None:
        """Test creating a PDKOverride instance."""
        pdk_dir = tmp_path / "custom_pdk"
        pdk_dir.mkdir()

        override = PDKOverride(
            host_path=str(pdk_dir),
            container_path="/opt/pdk/custom",
            pdk_version="1.2.3",
            metadata={"source": "internal", "variant": "hd"},
        )

        assert override.host_path == str(pdk_dir)
        assert override.container_path == "/opt/pdk/custom"
        assert override.pdk_version == "1.2.3"
        assert override.metadata["source"] == "internal"

    def test_validate_valid_override(self, tmp_path: Path) -> None:
        """Test validation passes for valid configuration."""
        pdk_dir = tmp_path / "valid_pdk"
        pdk_dir.mkdir()

        override = PDKOverride(
            host_path=str(pdk_dir),
            container_path="/opt/pdk",
            pdk_version="1.0.0",
        )

        is_valid, errors = override.validate()
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_host_path_not_exists(self, tmp_path: Path) -> None:
        """Test validation fails when host path doesn't exist."""
        nonexistent = tmp_path / "does_not_exist"

        override = PDKOverride(
            host_path=str(nonexistent),
            container_path="/opt/pdk",
            pdk_version="1.0.0",
        )

        is_valid, errors = override.validate()
        assert is_valid is False
        assert len(errors) == 1
        assert "does not exist" in errors[0]

    def test_validate_host_path_not_directory(self, tmp_path: Path) -> None:
        """Test validation fails when host path is a file."""
        file_path = tmp_path / "pdk_file.txt"
        file_path.write_text("not a directory")

        override = PDKOverride(
            host_path=str(file_path),
            container_path="/opt/pdk",
            pdk_version="1.0.0",
        )

        is_valid, errors = override.validate()
        assert is_valid is False
        assert len(errors) == 1
        assert "not a directory" in errors[0]

    def test_validate_container_path_not_absolute(self, tmp_path: Path) -> None:
        """Test validation fails when container path is relative."""
        pdk_dir = tmp_path / "pdk"
        pdk_dir.mkdir()

        override = PDKOverride(
            host_path=str(pdk_dir),
            container_path="relative/path",
            pdk_version="1.0.0",
        )

        is_valid, errors = override.validate()
        assert is_valid is False
        assert any("must be absolute" in e for e in errors)

    def test_validate_empty_version(self, tmp_path: Path) -> None:
        """Test validation fails when version is empty."""
        pdk_dir = tmp_path / "pdk"
        pdk_dir.mkdir()

        override = PDKOverride(
            host_path=str(pdk_dir),
            container_path="/opt/pdk",
            pdk_version="",
        )

        is_valid, errors = override.validate()
        assert is_valid is False
        assert any("must be non-empty" in e for e in errors)

    def test_validate_multiple_errors(self, tmp_path: Path) -> None:
        """Test validation collects multiple errors."""
        override = PDKOverride(
            host_path="/nonexistent/path",
            container_path="relative/path",
            pdk_version="  ",
        )

        is_valid, errors = override.validate()
        assert is_valid is False
        assert len(errors) >= 2  # At least host path and version errors

    def test_to_docker_mount(self, tmp_path: Path) -> None:
        """Test Docker mount string generation."""
        pdk_dir = tmp_path / "pdk"
        pdk_dir.mkdir()

        override = PDKOverride(
            host_path=str(pdk_dir),
            container_path="/opt/pdk",
            pdk_version="1.0.0",
        )

        mount_str = override.to_docker_mount()
        assert mount_str == f"{pdk_dir}:/opt/pdk:ro"
        assert mount_str.endswith(":ro")  # Read-only

    def test_to_dict(self, tmp_path: Path) -> None:
        """Test conversion to dictionary."""
        pdk_dir = tmp_path / "pdk"
        pdk_dir.mkdir()

        override = PDKOverride(
            host_path=str(pdk_dir),
            container_path="/opt/pdk",
            pdk_version="1.0.0",
            metadata={"key": "value"},
        )

        data = override.to_dict()
        assert data["host_path"] == str(pdk_dir)
        assert data["container_path"] == "/opt/pdk"
        assert data["pdk_version"] == "1.0.0"
        assert data["metadata"]["key"] == "value"

    def test_from_dict(self, tmp_path: Path) -> None:
        """Test creation from dictionary."""
        pdk_dir = tmp_path / "pdk"
        pdk_dir.mkdir()

        data = {
            "host_path": str(pdk_dir),
            "container_path": "/opt/pdk",
            "pdk_version": "1.0.0",
            "metadata": {"key": "value"},
        }

        override = PDKOverride.from_dict(data)
        assert override.host_path == str(pdk_dir)
        assert override.container_path == "/opt/pdk"
        assert override.pdk_version == "1.0.0"
        assert override.metadata["key"] == "value"

    def test_roundtrip_serialization(self, tmp_path: Path) -> None:
        """Test serialization roundtrip."""
        pdk_dir = tmp_path / "pdk"
        pdk_dir.mkdir()

        original = PDKOverride(
            host_path=str(pdk_dir),
            container_path="/opt/pdk",
            pdk_version="2.0.0",
            metadata={"env": "prod"},
        )

        data = original.to_dict()
        restored = PDKOverride.from_dict(data)

        assert restored.host_path == original.host_path
        assert restored.container_path == original.container_path
        assert restored.pdk_version == original.pdk_version
        assert restored.metadata == original.metadata


class TestCreatePDKOverride:
    """Tests for create_pdk_override convenience function."""

    def test_create_with_valid_config(self, tmp_path: Path) -> None:
        """Test creating PDK override with valid configuration."""
        pdk_dir = tmp_path / "pdk"
        pdk_dir.mkdir()

        override = create_pdk_override(
            host_path=str(pdk_dir),
            container_path="/opt/pdk",
            pdk_version="1.0.0",
            source="github",
            commit="abc123",
        )

        assert override.host_path == str(pdk_dir)
        assert override.pdk_version == "1.0.0"
        assert override.metadata["source"] == "github"
        assert override.metadata["commit"] == "abc123"

    def test_create_with_invalid_config(self) -> None:
        """Test creating PDK override with invalid config raises error."""
        with pytest.raises(ValueError, match="validation failed"):
            create_pdk_override(
                host_path="/nonexistent",
                container_path="/opt/pdk",
                pdk_version="1.0.0",
            )

    def test_create_validates_automatically(self, tmp_path: Path) -> None:
        """Test that create_pdk_override validates automatically."""
        pdk_dir = tmp_path / "pdk"
        pdk_dir.mkdir()

        # This should not raise
        override = create_pdk_override(
            host_path=str(pdk_dir),
            container_path="/opt/pdk",
            pdk_version="1.0.0",
        )

        # Validation should have passed
        is_valid, _ = override.validate()
        assert is_valid is True


class TestVerifyPDKAccessibility:
    """Tests for PDK accessibility verification."""

    def test_verify_pdk_exists(self, tmp_path: Path) -> None:
        """Test verification when PDK directory exists."""
        pdk_dir = tmp_path / "pdk"
        pdk_dir.mkdir()

        is_accessible, missing = verify_pdk_accessibility(str(pdk_dir))
        assert is_accessible is True
        assert len(missing) == 0

    def test_verify_pdk_not_exists(self, tmp_path: Path) -> None:
        """Test verification when PDK directory doesn't exist."""
        nonexistent = tmp_path / "nonexistent"

        is_accessible, missing = verify_pdk_accessibility(str(nonexistent))
        assert is_accessible is False
        assert "does not exist" in missing[0]

    def test_verify_pdk_not_directory(self, tmp_path: Path) -> None:
        """Test verification when PDK path is a file."""
        file_path = tmp_path / "pdk_file.txt"
        file_path.write_text("not a directory")

        is_accessible, missing = verify_pdk_accessibility(str(file_path))
        assert is_accessible is False
        assert "not a directory" in missing[0]

    def test_verify_with_expected_files(self, tmp_path: Path) -> None:
        """Test verification with expected files present."""
        pdk_dir = tmp_path / "pdk"
        pdk_dir.mkdir()
        (pdk_dir / "tech.lef").touch()
        (pdk_dir / "cells.lef").touch()

        is_accessible, missing = verify_pdk_accessibility(
            str(pdk_dir),
            expected_files=["tech.lef", "cells.lef"],
        )
        assert is_accessible is True
        assert len(missing) == 0

    def test_verify_with_missing_files(self, tmp_path: Path) -> None:
        """Test verification with some expected files missing."""
        pdk_dir = tmp_path / "pdk"
        pdk_dir.mkdir()
        (pdk_dir / "tech.lef").touch()
        # cells.lef is missing

        is_accessible, missing = verify_pdk_accessibility(
            str(pdk_dir),
            expected_files=["tech.lef", "cells.lef"],
        )
        assert is_accessible is False
        assert "cells.lef" in missing
        assert "tech.lef" not in missing


class TestDocumentPDKOverrideInProvenance:
    """Tests for PDK override provenance documentation."""

    def test_document_provenance(self, tmp_path: Path) -> None:
        """Test generating provenance record."""
        pdk_dir = tmp_path / "pdk"
        pdk_dir.mkdir()

        override = PDKOverride(
            host_path=str(pdk_dir),
            container_path="/opt/pdk",
            pdk_version="1.5.2",
            metadata={"variant": "hd"},
        )

        provenance = document_pdk_override_in_provenance(
            override=override,
            study_name="test_study",
        )

        assert provenance["pdk_override"]["enabled"] is True
        assert provenance["pdk_override"]["pdk_version"] == "1.5.2"
        assert provenance["pdk_override"]["container_path"] == "/opt/pdk"
        assert provenance["study_name"] == "test_study"
        assert provenance["override_type"] == "bind_mount"
        assert provenance["mount_mode"] == "read_only"

    def test_provenance_includes_metadata(self, tmp_path: Path) -> None:
        """Test provenance includes PDK metadata."""
        pdk_dir = tmp_path / "pdk"
        pdk_dir.mkdir()

        override = PDKOverride(
            host_path=str(pdk_dir),
            container_path="/opt/pdk",
            pdk_version="2.0.0",
            metadata={"source": "vendor", "license": "proprietary"},
        )

        provenance = document_pdk_override_in_provenance(
            override=override,
            study_name="prod_study",
        )

        assert provenance["pdk_override"]["metadata"]["source"] == "vendor"
        assert provenance["pdk_override"]["metadata"]["license"] == "proprietary"

    def test_provenance_hashes_host_path(self, tmp_path: Path) -> None:
        """Test provenance hashes host path for privacy."""
        pdk_dir = tmp_path / "pdk"
        pdk_dir.mkdir()

        override = PDKOverride(
            host_path=str(pdk_dir),
            container_path="/opt/pdk",
            pdk_version="1.0.0",
        )

        provenance = document_pdk_override_in_provenance(
            override=override,
            study_name="test",
        )

        # Should have hash, not full path
        assert "host_path_hash" in provenance["pdk_override"]
        assert "host_path" not in provenance["pdk_override"]
        assert isinstance(provenance["pdk_override"]["host_path_hash"], int)

    def test_provenance_serializable(self, tmp_path: Path) -> None:
        """Test provenance can be serialized to JSON."""
        pdk_dir = tmp_path / "pdk"
        pdk_dir.mkdir()

        override = PDKOverride(
            host_path=str(pdk_dir),
            container_path="/opt/pdk",
            pdk_version="1.0.0",
        )

        provenance = document_pdk_override_in_provenance(
            override=override,
            study_name="test",
        )

        # Should serialize without errors
        json_str = json.dumps(provenance)
        assert json_str is not None
        assert len(json_str) > 0


class TestStudyConfigIntegration:
    """Tests for PDK override integration with StudyConfig."""

    def test_study_config_accepts_pdk_override(self, tmp_path: Path) -> None:
        """Test StudyConfig accepts pdk_override field."""
        from src.controller.types import (
            ExecutionMode,
            SafetyDomain,
            StageConfig,
            StudyConfig,
        )

        pdk_dir = tmp_path / "pdk"
        pdk_dir.mkdir()

        override = PDKOverride(
            host_path=str(pdk_dir),
            container_path="/opt/pdk",
            pdk_version="1.0.0",
        )

        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        stage = StageConfig(
            name="stage1",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[],
        )

        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="CustomPDK",
            stages=[stage],
            snapshot_path=str(snapshot_dir),
            pdk_override=override,
        )

        assert config.pdk_override is not None
        assert config.pdk_override.pdk_version == "1.0.0"

    def test_study_config_without_pdk_override(self, tmp_path: Path) -> None:
        """Test StudyConfig works without pdk_override (default)."""
        from src.controller.types import (
            ExecutionMode,
            SafetyDomain,
            StageConfig,
            StudyConfig,
        )

        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        stage = StageConfig(
            name="stage1",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[],
        )

        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[stage],
            snapshot_path=str(snapshot_dir),
        )

        assert config.pdk_override is None


class TestEndToEndWorkflow:
    """End-to-end tests for PDK override workflow."""

    def test_complete_workflow(self, tmp_path: Path) -> None:
        """Test complete PDK override workflow."""
        # Step 1: Create versioned PDK directory on host
        pdk_dir = tmp_path / "custom_pdk_v1.5.0"
        pdk_dir.mkdir()
        (pdk_dir / "tech.lef").write_text("LAYER metal1")
        (pdk_dir / "cells.lef").write_text("MACRO INV")

        # Step 2: Declare bind mount in Study configuration
        override = create_pdk_override(
            host_path=str(pdk_dir),
            container_path="/opt/openroad/pdk",
            pdk_version="1.5.0",
            vendor="CustomSemiconductor",
            process="7nm",
        )

        # Step 3: Generate Docker mount string
        mount_str = override.to_docker_mount()
        assert ":ro" in mount_str  # Read-only mount

        # Step 4: Verify custom PDK is accessible (simulate container check)
        is_accessible, missing = verify_pdk_accessibility(
            str(pdk_dir),
            expected_files=["tech.lef", "cells.lef"],
        )
        assert is_accessible is True

        # Step 5: Document PDK override in Study provenance
        provenance = document_pdk_override_in_provenance(
            override=override,
            study_name="custom_pdk_study",
        )

        assert provenance["pdk_override"]["enabled"] is True
        assert provenance["pdk_override"]["pdk_version"] == "1.5.0"
        assert provenance["study_name"] == "custom_pdk_study"

        # Step 6: Verify provenance is serializable
        provenance_json = json.dumps(provenance, indent=2)
        assert "1.5.0" in provenance_json
        assert "custom_pdk_study" in provenance_json
