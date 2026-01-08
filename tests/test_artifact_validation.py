"""Tests for trial artifact validation."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.controller.artifact_validation import (
    ArtifactChecklist,
    ArtifactRequirement,
    ArtifactType,
    ArtifactValidator,
    get_sta_congestion_checklist,
    get_sta_only_checklist,
    get_visualization_checklist,
)


class TestArtifactRequirement:
    """Tests for ArtifactRequirement."""

    def test_validate_file_exists(self) -> None:
        """Test validating that a file exists."""
        with TemporaryDirectory() as tmpdir:
            artifact_path = Path(tmpdir) / "test.txt"
            artifact_path.write_text("test content")

            requirement = ArtifactRequirement(
                artifact_type=ArtifactType.LOG_FILE,
                path_pattern="test.txt",
            )

            is_valid, error = requirement.validate_file(artifact_path)
            assert is_valid
            assert error is None

    def test_validate_file_not_exists(self) -> None:
        """Test validation fails when file doesn't exist."""
        requirement = ArtifactRequirement(
            artifact_type=ArtifactType.LOG_FILE,
            path_pattern="test.txt",
        )

        is_valid, error = requirement.validate_file(Path("/nonexistent/test.txt"))
        assert not is_valid
        assert "not found" in error.lower()

    def test_validate_file_size(self) -> None:
        """Test file size validation."""
        with TemporaryDirectory() as tmpdir:
            artifact_path = Path(tmpdir) / "test.txt"
            artifact_path.write_text("abc")  # 3 bytes

            requirement = ArtifactRequirement(
                artifact_type=ArtifactType.LOG_FILE,
                path_pattern="test.txt",
                min_size_bytes=10,
            )

            is_valid, error = requirement.validate_file(artifact_path)
            assert not is_valid
            assert "too small" in error.lower()

    def test_validate_json_parseable(self) -> None:
        """Test JSON parseability validation."""
        with TemporaryDirectory() as tmpdir:
            # Valid JSON
            artifact_path = Path(tmpdir) / "metrics.json"
            artifact_path.write_text('{"wns_ps": -50}')

            requirement = ArtifactRequirement(
                artifact_type=ArtifactType.METRICS_JSON,
                path_pattern="metrics.json",
                validate_parseable=True,
            )

            is_valid, error = requirement.validate_file(artifact_path)
            assert is_valid
            assert error is None

    def test_validate_json_invalid(self) -> None:
        """Test JSON validation fails on invalid JSON."""
        with TemporaryDirectory() as tmpdir:
            artifact_path = Path(tmpdir) / "metrics.json"
            artifact_path.write_text("not valid json {")

            requirement = ArtifactRequirement(
                artifact_type=ArtifactType.METRICS_JSON,
                path_pattern="metrics.json",
                validate_parseable=True,
            )

            is_valid, error = requirement.validate_file(artifact_path)
            assert not is_valid
            assert "json" in error.lower()

    def test_validate_csv_parseable(self) -> None:
        """Test CSV parseability validation."""
        with TemporaryDirectory() as tmpdir:
            artifact_path = Path(tmpdir) / "data.csv"
            artifact_path.write_text("x,y,value\n0,0,1.5\n1,0,2.3\n")

            requirement = ArtifactRequirement(
                artifact_type=ArtifactType.HEATMAP_CSV,
                path_pattern="data.csv",
                validate_parseable=True,
            )

            is_valid, error = requirement.validate_file(artifact_path)
            assert is_valid
            assert error is None

    def test_validate_csv_invalid(self) -> None:
        """Test CSV validation fails when no commas present."""
        with TemporaryDirectory() as tmpdir:
            artifact_path = Path(tmpdir) / "data.csv"
            artifact_path.write_text("not a csv file")

            requirement = ArtifactRequirement(
                artifact_type=ArtifactType.HEATMAP_CSV,
                path_pattern="data.csv",
                validate_parseable=True,
            )

            is_valid, error = requirement.validate_file(artifact_path)
            assert not is_valid
            assert "comma" in error.lower()


class TestArtifactChecklist:
    """Tests for ArtifactChecklist."""

    def test_create_empty_checklist(self) -> None:
        """Test creating an empty checklist."""
        checklist = ArtifactChecklist(trial_type="test_type")

        assert checklist.trial_type == "test_type"
        assert len(checklist.requirements) == 0

    def test_add_requirement(self) -> None:
        """Test adding requirements to checklist."""
        checklist = ArtifactChecklist(trial_type="test_type")

        requirement = ArtifactRequirement(
            artifact_type=ArtifactType.LOG_FILE,
            path_pattern="test.log",
        )

        checklist.add_requirement(requirement)

        assert len(checklist.requirements) == 1
        assert checklist.requirements[0] == requirement

    def test_get_required_artifacts(self) -> None:
        """Test filtering required artifacts."""
        checklist = ArtifactChecklist(trial_type="test_type")

        checklist.add_requirement(
            ArtifactRequirement(
                artifact_type=ArtifactType.LOG_FILE,
                path_pattern="required.log",
                required=True,
            )
        )

        checklist.add_requirement(
            ArtifactRequirement(
                artifact_type=ArtifactType.HEATMAP_CSV,
                path_pattern="optional.csv",
                required=False,
            )
        )

        required = checklist.get_required_artifacts()
        assert len(required) == 1
        assert required[0].path_pattern == "required.log"

    def test_get_optional_artifacts(self) -> None:
        """Test filtering optional artifacts."""
        checklist = ArtifactChecklist(trial_type="test_type")

        checklist.add_requirement(
            ArtifactRequirement(
                artifact_type=ArtifactType.LOG_FILE,
                path_pattern="required.log",
                required=True,
            )
        )

        checklist.add_requirement(
            ArtifactRequirement(
                artifact_type=ArtifactType.HEATMAP_CSV,
                path_pattern="optional.csv",
                required=False,
            )
        )

        optional = checklist.get_optional_artifacts()
        assert len(optional) == 1
        assert optional[0].path_pattern == "optional.csv"


class TestArtifactValidator:
    """Tests for ArtifactValidator."""

    def test_validate_complete_artifacts(self) -> None:
        """Test validation passes when all required artifacts are present."""
        with TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)

            # Create required artifacts
            (artifact_dir / "timing_report.txt").write_text("timing report content")
            (artifact_dir / "metrics.json").write_text('{"wns_ps": -50}')

            # Create checklist
            checklist = ArtifactChecklist(trial_type="test_type")
            checklist.add_requirement(
                ArtifactRequirement(
                    artifact_type=ArtifactType.TIMING_REPORT,
                    path_pattern="timing_report.txt",
                    required=True,
                )
            )
            checklist.add_requirement(
                ArtifactRequirement(
                    artifact_type=ArtifactType.METRICS_JSON,
                    path_pattern="metrics.json",
                    required=True,
                    validate_parseable=True,
                )
            )

            # Validate
            validator = ArtifactValidator(checklist)
            result = validator.validate(artifact_dir)

            assert result.is_complete
            assert len(result.missing_required) == 0
            assert len(result.invalid_artifacts) == 0
            assert len(result.present_artifacts) == 2

    def test_validate_missing_required_artifact(self) -> None:
        """Test validation fails when required artifact is missing."""
        with TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)

            # Create checklist with required artifact
            checklist = ArtifactChecklist(trial_type="test_type")
            checklist.add_requirement(
                ArtifactRequirement(
                    artifact_type=ArtifactType.TIMING_REPORT,
                    path_pattern="timing_report.txt",
                    required=True,
                )
            )

            # Validate (file doesn't exist)
            validator = ArtifactValidator(checklist)
            result = validator.validate(artifact_dir)

            assert not result.is_complete
            assert "timing_report.txt" in result.missing_required
            assert "Missing" in result.validation_summary

    def test_validate_invalid_json(self) -> None:
        """Test validation fails when JSON artifact is invalid."""
        with TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)

            # Create invalid JSON
            (artifact_dir / "metrics.json").write_text("not valid json")

            # Create checklist
            checklist = ArtifactChecklist(trial_type="test_type")
            checklist.add_requirement(
                ArtifactRequirement(
                    artifact_type=ArtifactType.METRICS_JSON,
                    path_pattern="metrics.json",
                    required=True,
                    validate_parseable=True,
                )
            )

            # Validate
            validator = ArtifactValidator(checklist)
            result = validator.validate(artifact_dir)

            assert not result.is_complete
            assert len(result.invalid_artifacts) > 0
            assert "invalid" in result.validation_summary.lower()

    def test_validate_optional_artifacts(self) -> None:
        """Test validation passes even when optional artifacts are missing."""
        with TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)

            # Create only required artifact
            (artifact_dir / "timing_report.txt").write_text("timing report")

            # Create checklist with required and optional artifacts
            checklist = ArtifactChecklist(trial_type="test_type")
            checklist.add_requirement(
                ArtifactRequirement(
                    artifact_type=ArtifactType.TIMING_REPORT,
                    path_pattern="timing_report.txt",
                    required=True,
                )
            )
            checklist.add_requirement(
                ArtifactRequirement(
                    artifact_type=ArtifactType.HEATMAP_CSV,
                    path_pattern="heatmap.csv",
                    required=False,
                )
            )

            # Validate
            validator = ArtifactValidator(checklist)
            result = validator.validate(artifact_dir)

            assert result.is_complete
            assert len(result.missing_optional) == 1
            assert "heatmap.csv" in result.missing_optional


class TestStandardChecklists:
    """Tests for standard checklist factory functions."""

    def test_sta_only_checklist(self) -> None:
        """Test STA-only checklist."""
        checklist = get_sta_only_checklist()

        assert checklist.trial_type == "sta_only"
        assert len(checklist.requirements) >= 3

        # Check for timing report
        assert any(
            req.artifact_type == ArtifactType.TIMING_REPORT
            for req in checklist.requirements
        )

        # Check for metrics JSON
        assert any(
            req.artifact_type == ArtifactType.METRICS_JSON
            for req in checklist.requirements
        )

    def test_sta_congestion_checklist(self) -> None:
        """Test STA+congestion checklist."""
        checklist = get_sta_congestion_checklist()

        assert checklist.trial_type == "sta_congestion"

        # Should include congestion report
        assert any(
            req.artifact_type == ArtifactType.CONGESTION_REPORT
            for req in checklist.requirements
        )

    def test_visualization_checklist(self) -> None:
        """Test visualization checklist."""
        checklist = get_visualization_checklist()

        assert checklist.trial_type == "visualization"

        # Should include heatmap CSVs (optional)
        heatmap_reqs = [
            req
            for req in checklist.requirements
            if req.artifact_type == ArtifactType.HEATMAP_CSV
        ]

        assert len(heatmap_reqs) >= 3
        # Heatmaps should be optional
        assert all(not req.required for req in heatmap_reqs)


class TestArtifactValidationEndToEnd:
    """End-to-end tests for artifact validation."""

    def test_validate_trial_artifact_completeness(self) -> None:
        """
        Feature: Validate trial artifact completeness before marking trial as successful.

        Steps:
            1. Define artifact completeness checklist for trial type
            2. Execute trial (simulated)
            3. Check all required artifacts are present
            4. Verify artifact files are non-empty and parseable
            5. Mark trial as successful only if all artifacts pass validation
            6. Classify as early failure if artifacts are incomplete
        """
        with TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)

            # Step 1: Define checklist for STA-only trial
            checklist = get_sta_only_checklist()
            validator = ArtifactValidator(checklist)

            # Step 2: Simulate trial execution - create artifacts

            # Step 3 & 4: Validate artifacts - initially missing
            result = validator.validate(artifact_dir)
            assert not result.is_complete
            assert len(result.missing_required) > 0

            # Step 6: Should classify as early failure
            assert "Missing" in result.validation_summary

            # Now create valid artifacts
            (artifact_dir / "timing_report.txt").write_text(
                "WNS: -50ps\nTNS: -1000ps"
            )
            (artifact_dir / "metrics.json").write_text('{"wns_ps": -50, "tns_ps": -1000}')
            (artifact_dir / "trial.log").write_text("Trial execution log")
            (artifact_dir / "trial.tcl").write_text("# TCL script\nreport_checks")

            # Step 5: Re-validate - should pass now
            result = validator.validate(artifact_dir)
            assert result.is_complete
            assert len(result.missing_required) == 0
            assert len(result.invalid_artifacts) == 0
            assert len(result.present_artifacts) >= 4

    def test_validate_with_invalid_json(self) -> None:
        """Test validation fails gracefully with invalid JSON."""
        with TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)

            # Create artifacts, but metrics.json is invalid
            (artifact_dir / "timing_report.txt").write_text("timing report")
            (artifact_dir / "metrics.json").write_text("{invalid json}")
            (artifact_dir / "trial.log").write_text("log")
            (artifact_dir / "trial.tcl").write_text("tcl")

            checklist = get_sta_only_checklist()
            validator = ArtifactValidator(checklist)
            result = validator.validate(artifact_dir)

            # Should fail because metrics.json is unparseable
            assert not result.is_complete
            assert len(result.invalid_artifacts) > 0

            # Check the invalid artifact is identified
            invalid_paths = [str(p) for p in result.invalid_artifacts.keys()]
            assert any("metrics.json" in p for p in invalid_paths)

    def test_validate_sta_congestion_trial(self) -> None:
        """Test validation for STA+congestion trial."""
        with TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)

            # Create all required artifacts for STA+congestion (with sufficient content)
            (artifact_dir / "timing_report.txt").write_text("timing report content")
            (artifact_dir / "metrics.json").write_text('{"wns_ps": -50}')
            (artifact_dir / "trial.log").write_text("trial log content")
            (artifact_dir / "trial.tcl").write_text("tcl script content")
            (artifact_dir / "congestion_report.rpt").write_text("congestion data")

            checklist = get_sta_congestion_checklist()
            validator = ArtifactValidator(checklist)
            result = validator.validate(artifact_dir)

            assert result.is_complete
            assert len(result.present_artifacts) >= 5

    def test_result_to_dict(self) -> None:
        """Test converting validation result to dict."""
        with TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir)

            checklist = ArtifactChecklist(trial_type="test")
            checklist.add_requirement(
                ArtifactRequirement(
                    artifact_type=ArtifactType.LOG_FILE,
                    path_pattern="test.log",
                    required=True,
                )
            )

            validator = ArtifactValidator(checklist)
            result = validator.validate(artifact_dir)

            # Convert to dict
            result_dict = result.to_dict()

            assert isinstance(result_dict, dict)
            assert "is_complete" in result_dict
            assert "missing_required" in result_dict
            assert "validation_summary" in result_dict

            # Should be serializable to JSON
            json_str = json.dumps(result_dict)
            assert json_str is not None
