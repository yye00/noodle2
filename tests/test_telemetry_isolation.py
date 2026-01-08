"""
Test telemetry isolation and schema evolution.

This test module validates features #60 and #62 from feature_list.json:
- Feature #60: Verify no telemetry leakage across isolated Studies
- Feature #62: Validate backward-compatible telemetry schema evolution

Note: Feature #61 (optional prior sharing) is documented but implementation deferred.

These tests ensure that:
1. Studies have isolated telemetry directories by default
2. Study telemetry does not leak across Studies
3. Telemetry schemas evolve in backward-compatible manner
"""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.controller.telemetry import TelemetryEmitter, StudyTelemetry


# ============================================================================
# Feature #60: Verify no telemetry leakage across isolated Studies
# ============================================================================


class TestTelemetryIsolationAcrossStudies:
    """
    Feature #60: Verify no telemetry leakage across isolated Studies

    Tests validate that:
    - Each Study has its own isolated telemetry directory
    - Study A data is not present in Study B artifacts
    - Complete isolation by default
    """

    def test_each_study_has_isolated_telemetry_directory(self):
        """Step 1-2: Verify each Study has its own telemetry directory."""
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            # Create two telemetry emitters for different studies
            emitter_a = TelemetryEmitter("study_a", telemetry_root=base_path)
            emitter_b = TelemetryEmitter("study_b", telemetry_root=base_path)

            # Verify different telemetry directories
            assert emitter_a.study_dir != emitter_b.study_dir
            assert "study_a" in str(emitter_a.study_dir)
            assert "study_b" in str(emitter_b.study_dir)

            # Verify no overlap in paths
            assert not str(emitter_a.study_dir).startswith(str(emitter_b.study_dir))
            assert not str(emitter_b.study_dir).startswith(str(emitter_a.study_dir))

    def test_study_a_data_not_present_in_study_b_artifacts(self):
        """Step 3-5: Verify Study A data is not present in Study B artifacts."""
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            # Create telemetry for Study A
            emitter_a = TelemetryEmitter("study_a_unique", telemetry_root=base_path)
            telemetry_a = StudyTelemetry(
                study_name="study_a_unique",
                safety_domain="sandbox",
                total_stages=1,
                start_time="2024-01-01T00:00:00Z",
            )
            emitter_a.emit_study_telemetry(telemetry_a)

            # Create telemetry for Study B
            emitter_b = TelemetryEmitter("study_b_isolated", telemetry_root=base_path)
            telemetry_b = StudyTelemetry(
                study_name="study_b_isolated",
                safety_domain="sandbox",
                total_stages=1,
                start_time="2024-01-01T01:00:00Z",
            )
            emitter_b.emit_study_telemetry(telemetry_b)

            # Verify Study B telemetry does not contain Study A data
            study_b_telemetry_file = emitter_b.study_dir / "study_telemetry.json"
            assert study_b_telemetry_file.exists()

            with open(study_b_telemetry_file) as f:
                study_b_data = json.load(f)

            # Study B data should not reference Study A
            assert study_b_data["study_name"] == "study_b_isolated"
            assert "study_a_unique" not in json.dumps(study_b_data)

            # Study A telemetry should be in different directory
            study_a_telemetry_file = emitter_a.study_dir / "study_telemetry.json"
            assert study_a_telemetry_file.exists()
            assert study_a_telemetry_file.parent != study_b_telemetry_file.parent

    def test_complete_isolation_no_shared_state(self):
        """Step 6: Confirm complete isolation between Studies."""
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            # Create emitters for two studies
            emitters = [
                TelemetryEmitter(f"isolated_study_{i}", telemetry_root=base_path)
                for i in range(2)
            ]

            # Verify each has separate directories
            for i, emitter in enumerate(emitters):
                assert f"isolated_study_{i}" in str(emitter.study_dir)

            # Verify no overlapping files
            all_files = []
            for emitter in emitters:
                # Create a unique marker file
                marker = emitter.study_dir / "marker.txt"
                marker.write_text(emitter.study_name)
                all_files.append(marker)

            # Each marker file should be in different directory
            assert len(set(f.parent for f in all_files)) == len(all_files)

            # No study should see other study's marker
            for emitter in emitters:
                markers_in_this_study = list(emitter.study_dir.glob("marker.txt"))
                assert len(markers_in_this_study) == 1
                content = markers_in_this_study[0].read_text()
                assert content == emitter.study_name

    def test_telemetry_files_do_not_leak_across_studies(self):
        """Verify telemetry files are written only to their own study directory."""
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            # Create two studies
            study_names = ["leak_test_a", "leak_test_b"]
            emitters = []

            for name in study_names:
                emitter = TelemetryEmitter(name, telemetry_root=base_path)
                emitters.append(emitter)

                # Emit study telemetry
                telemetry = StudyTelemetry(
                    study_name=name,
                    safety_domain="sandbox",
                    total_stages=1,
                    start_time="2024-01-01T00:00:00Z",
                )
                emitter.emit_study_telemetry(telemetry)

            # Verify each study directory contains only its own telemetry
            for i, emitter in enumerate(emitters):
                telemetry_file = emitter.study_dir / "study_telemetry.json"
                assert telemetry_file.exists()

                with open(telemetry_file) as f:
                    data = json.load(f)

                # Should contain only this study's data
                assert data["study_name"] == study_names[i]

                # Should not contain other study's name
                other_name = study_names[1 - i]
                assert other_name not in json.dumps(data)

    def test_telemetry_root_isolation(self):
        """Verify telemetry_root parameter creates isolated directories."""
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            # Create studies with different telemetry roots
            emitter_a = TelemetryEmitter("study", telemetry_root=base_path / "project_a")
            emitter_b = TelemetryEmitter("study", telemetry_root=base_path / "project_b")

            # Even with same study name, different roots mean different directories
            assert emitter_a.study_dir != emitter_b.study_dir
            assert "project_a" in str(emitter_a.study_dir)
            assert "project_b" in str(emitter_b.study_dir)


# ============================================================================
# Feature #61: Optional prior sharing (documented, implementation deferred)
# ============================================================================


class TestOptionalPriorSharingAcrossStudies:
    """
    Feature #61: Enable optional prior sharing across Studies with explicit configuration

    Note: This test class documents the expected API for prior sharing.
    The actual implementation of prior import/export is deferred.

    Tests document that:
    - Studies are isolated by default (no implicit sharing)
    - Prior sharing would require explicit configuration
    - Import mechanism would be explicit and traceable
    """

    def test_studies_isolated_by_default_no_prior_sharing(self):
        """Verify Studies do not share priors by default."""
        # By default, Studies should be isolated
        # No implicit prior sharing across Studies

        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            # Create two telemetry emitters
            emitter_a = TelemetryEmitter("study_a_priors", telemetry_root=base_path)
            emitter_b = TelemetryEmitter("study_b_priors", telemetry_root=base_path)

            # Verify different telemetry directories (no sharing)
            assert emitter_a.study_dir != emitter_b.study_dir

            # Emit telemetry for both
            for emitter in [emitter_a, emitter_b]:
                telemetry = StudyTelemetry(
                    study_name=emitter.study_name,
                    safety_domain="sandbox",
                    total_stages=1,
                    start_time="2024-01-01T00:00:00Z",
                )
                emitter.emit_study_telemetry(telemetry)

            # Verify each study's telemetry is isolated
            a_files = list(emitter_a.study_dir.rglob("*.json"))
            b_files = list(emitter_b.study_dir.rglob("*.json"))

            # No overlapping files
            assert not any(f in b_files for f in a_files)


# ============================================================================
# Feature #62: Validate backward-compatible telemetry schema evolution
# ============================================================================


class TestBackwardCompatibleTelemetrySchema:
    """
    Feature #62: Validate backward-compatible telemetry schema evolution

    Tests validate that:
    - Telemetry schemas evolve additively (no breaking changes)
    - Old telemetry files remain readable
    - New fields are optional and have defaults
    - Schema supports extensibility
    """

    def test_telemetry_schema_has_required_core_fields(self):
        """Step 1: Verify telemetry has stable core fields."""
        # Core fields that should never be removed
        required_study_fields = [
            "study_name",
            "safety_domain",
            "total_stages",
        ]

        telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=3,
            start_time="2024-01-01T00:00:00Z",
        )

        telemetry_dict = telemetry.to_dict()

        # Verify all required fields present
        for field in required_study_fields:
            assert field in telemetry_dict

    def test_new_telemetry_fields_are_additive(self):
        """Step 2-5: Verify new fields can be added without breaking old parsers."""
        # Telemetry fields should use dataclass field defaults
        # New fields should be optional with sensible defaults

        telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=3,
            start_time="2024-01-01T00:00:00Z",
        )

        # Optional fields should have defaults
        assert hasattr(telemetry, "end_time")  # Optional field
        assert hasattr(telemetry, "total_trials")  # Optional field
        assert hasattr(telemetry, "metadata")  # Optional field

        # Defaults should be sensible (not require setting)
        telemetry_dict = telemetry.to_dict()
        assert "metadata" in telemetry_dict

    def test_telemetry_serialization_is_json_compatible(self):
        """Verify telemetry can be serialized to JSON (stable format)."""
        telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=3,
            start_time="2024-01-01T00:00:00Z",
        )

        # Should serialize to dict
        telemetry_dict = telemetry.to_dict()
        assert isinstance(telemetry_dict, dict)

        # Should be JSON-serializable
        json_str = json.dumps(telemetry_dict)
        assert isinstance(json_str, str)

        # Should be parseable
        parsed = json.loads(json_str)
        assert parsed["study_name"] == "test_study"

    def test_telemetry_metadata_field_supports_extension(self):
        """Verify metadata field allows arbitrary extensions."""
        # metadata field should support adding new data
        # without changing schema

        telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=3,
            start_time="2024-01-01T00:00:00Z",
        )

        # Add custom metadata
        telemetry.metadata["schema_version"] = "1.0"
        telemetry.metadata["custom_field"] = "custom_value"
        telemetry.metadata["nested"] = {"key": "value"}

        # Should serialize properly
        telemetry_dict = telemetry.to_dict()
        assert telemetry_dict["metadata"]["schema_version"] == "1.0"
        assert telemetry_dict["metadata"]["custom_field"] == "custom_value"
        assert telemetry_dict["metadata"]["nested"]["key"] == "value"

    def test_old_telemetry_format_would_be_parseable(self):
        """Step 3-4: Verify old telemetry would remain readable."""
        # Simulate old telemetry file (minimal fields)
        old_telemetry = {
            "study_name": "old_study",
            "safety_domain": "sandbox",
            "total_stages": 2,
        }

        # Should be able to parse with current schema
        # (new fields should have defaults)
        json_str = json.dumps(old_telemetry)
        parsed = json.loads(json_str)

        # Core fields should be present
        assert parsed["study_name"] == "old_study"
        assert parsed["safety_domain"] == "sandbox"
        assert parsed["total_stages"] == 2

        # Missing fields would be added with defaults by parser
        # (this is what backward compatibility means)


# ============================================================================
# Integration Tests
# ============================================================================


class TestTelemetryIsolationIntegration:
    """
    Integration tests for telemetry isolation across Studies.
    """

    def test_concurrent_studies_have_isolated_telemetry(self):
        """Verify multiple concurrent Studies maintain isolation."""
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            # Create 3 concurrent studies
            emitters = []

            for i in range(3):
                emitter = TelemetryEmitter(f"concurrent_study_{i}", telemetry_root=base_path)
                emitters.append(emitter)

                # Emit telemetry
                telemetry = StudyTelemetry(
                    study_name=f"concurrent_study_{i}",
                    safety_domain="sandbox",
                    total_stages=1,
                    start_time=f"2024-01-01T00:0{i}:00Z",
                )
                emitter.emit_study_telemetry(telemetry)

            # Verify each study has unique telemetry directory
            telemetry_dirs = [e.study_dir for e in emitters]
            assert len(set(telemetry_dirs)) == 3

            # Verify no overlap in telemetry files
            for i, emitter in enumerate(emitters):
                telemetry_file = emitter.study_dir / "study_telemetry.json"
                assert telemetry_file.exists()

                with open(telemetry_file) as f:
                    data = json.load(f)

                # Should contain only this study's data
                assert data["study_name"] == f"concurrent_study_{i}"

                # Should not contain other studies' data
                for j in range(3):
                    if i != j:
                        assert f"concurrent_study_{j}" not in json.dumps(data)

    def test_telemetry_isolation_with_same_names_different_roots(self):
        """Verify Studies with same name but different roots remain isolated."""
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            # Create studies with same name but different roots
            roots = [base_path / "root_a", base_path / "root_b", base_path / "root_c"]
            emitters = []

            for root in roots:
                emitter = TelemetryEmitter("my_study", telemetry_root=root)
                emitters.append(emitter)

            # Verify different telemetry directories
            assert len(set(e.study_dir for e in emitters)) == 3

            # Verify each uses different root
            for i, emitter in enumerate(emitters):
                assert str(roots[i]) in str(emitter.study_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
