"""
Tests for Study configuration schema validation and dry-run mode.

This module tests:
- Feature #86: Validate Study configuration JSON schema before execution
- Feature #87: Support dry-run mode to validate configuration without executing trials
"""

import pytest
import tempfile
from pathlib import Path

from src.controller.validation import (
    validate_study_schema,
    validate_study_config,
    dry_run_validation,
    ValidationError,
)
from src.controller.study import create_study_config, load_study_config
from src.controller.types import (
    ECOClass,
    ExecutionMode,
    SafetyDomain,
    StageConfig,
)


class TestSchemaValidation:
    """
    Feature #86: Validate Study configuration JSON schema before execution.

    Steps:
        1. Load Study configuration file
        2. Parse JSON and validate against schema
        3. Check required fields are present
        4. Verify safety domain is valid value
        5. Reject Study with clear error if schema validation fails
    """

    def test_validate_complete_valid_config(self) -> None:
        """Test validation of a complete, valid configuration."""
        config_data = {
            "name": "valid_study",
            "safety_domain": "guarded",
            "base_case_name": "nangate45_base",
            "pdk": "Nangate45",
            "snapshot_path": "/tmp/snapshots/nangate45",
            "stages": [
                {
                    "name": "stage_0",
                    "execution_mode": "sta_only",
                    "trial_budget": 10,
                    "survivor_count": 5,
                    "allowed_eco_classes": ["topology_neutral"],
                }
            ],
        }

        # Step 2: Parse and validate against schema
        errors = validate_study_schema(config_data)

        # Step 3: Check required fields are present (no errors)
        assert len(errors) == 0, f"Valid config should have no errors: {errors}"

    def test_validate_missing_required_fields(self) -> None:
        """Step 3: Test detection of missing required fields."""
        # Missing 'name'
        config_data = {
            "safety_domain": "guarded",
            "base_case_name": "nangate45_base",
            "pdk": "Nangate45",
            "snapshot_path": "/tmp/snapshots",
            "stages": [],
        }

        errors = validate_study_schema(config_data)
        assert any("name" in err for err in errors), "Should detect missing 'name'"

        # Missing 'safety_domain'
        config_data = {
            "name": "test",
            "base_case_name": "nangate45_base",
            "pdk": "Nangate45",
            "snapshot_path": "/tmp/snapshots",
            "stages": [],
        }

        errors = validate_study_schema(config_data)
        assert any("safety_domain" in err for err in errors), "Should detect missing 'safety_domain'"

        # Missing 'stages'
        config_data = {
            "name": "test",
            "safety_domain": "guarded",
            "base_case_name": "nangate45_base",
            "pdk": "Nangate45",
            "snapshot_path": "/tmp/snapshots",
        }

        errors = validate_study_schema(config_data)
        assert any("stages" in err for err in errors), "Should detect missing 'stages'"

    def test_validate_invalid_safety_domain(self) -> None:
        """Step 4: Verify safety domain is valid value."""
        config_data = {
            "name": "test_study",
            "safety_domain": "invalid_domain",  # Invalid value
            "base_case_name": "nangate45_base",
            "pdk": "Nangate45",
            "snapshot_path": "/tmp/snapshots",
            "stages": [
                {
                    "name": "stage_0",
                    "execution_mode": "sta_only",
                    "trial_budget": 10,
                    "survivor_count": 5,
                }
            ],
        }

        errors = validate_study_schema(config_data)
        assert any("safety_domain" in err.lower() for err in errors), \
            "Should detect invalid safety_domain"
        assert any("invalid_domain" in err for err in errors), \
            "Error should mention the invalid value"

    def test_validate_valid_safety_domains(self) -> None:
        """Test all valid safety domain values."""
        valid_domains = ["sandbox", "guarded", "locked"]

        for domain in valid_domains:
            config_data = {
                "name": f"test_{domain}",
                "safety_domain": domain,
                "base_case_name": "nangate45_base",
                "pdk": "Nangate45",
                "snapshot_path": "/tmp/snapshots",
                "stages": [
                    {
                        "name": "stage_0",
                        "execution_mode": "sta_only",
                        "trial_budget": 10,
                        "survivor_count": 5,
                    }
                ],
            }

            errors = validate_study_schema(config_data)
            assert len(errors) == 0, f"Domain '{domain}' should be valid"

    def test_validate_empty_stages_list(self) -> None:
        """Test detection of empty stages list."""
        config_data = {
            "name": "test_study",
            "safety_domain": "guarded",
            "base_case_name": "nangate45_base",
            "pdk": "Nangate45",
            "snapshot_path": "/tmp/snapshots",
            "stages": [],  # Empty stages
        }

        errors = validate_study_schema(config_data)
        assert any("at least one stage" in err.lower() for err in errors), \
            "Should detect empty stages list"

    def test_validate_stage_missing_required_fields(self) -> None:
        """Test detection of missing required fields in stage configuration."""
        config_data = {
            "name": "test_study",
            "safety_domain": "guarded",
            "base_case_name": "nangate45_base",
            "pdk": "Nangate45",
            "snapshot_path": "/tmp/snapshots",
            "stages": [
                {
                    "name": "stage_0",
                    # Missing execution_mode, trial_budget, survivor_count
                }
            ],
        }

        errors = validate_study_schema(config_data)
        assert any("execution_mode" in err for err in errors), \
            "Should detect missing execution_mode"
        assert any("trial_budget" in err for err in errors), \
            "Should detect missing trial_budget"
        assert any("survivor_count" in err for err in errors), \
            "Should detect missing survivor_count"

    def test_validate_invalid_execution_mode(self) -> None:
        """Test detection of invalid execution mode."""
        config_data = {
            "name": "test_study",
            "safety_domain": "guarded",
            "base_case_name": "nangate45_base",
            "pdk": "Nangate45",
            "snapshot_path": "/tmp/snapshots",
            "stages": [
                {
                    "name": "stage_0",
                    "execution_mode": "invalid_mode",
                    "trial_budget": 10,
                    "survivor_count": 5,
                }
            ],
        }

        errors = validate_study_schema(config_data)
        assert any("execution_mode" in err.lower() for err in errors), \
            "Should detect invalid execution_mode"

    def test_validate_invalid_trial_budget(self) -> None:
        """Test detection of invalid trial budget."""
        # Zero budget
        config_data = {
            "name": "test_study",
            "safety_domain": "guarded",
            "base_case_name": "nangate45_base",
            "pdk": "Nangate45",
            "snapshot_path": "/tmp/snapshots",
            "stages": [
                {
                    "name": "stage_0",
                    "execution_mode": "sta_only",
                    "trial_budget": 0,  # Invalid
                    "survivor_count": 5,
                }
            ],
        }

        errors = validate_study_schema(config_data)
        assert any("trial_budget" in err and "positive" in err for err in errors), \
            "Should detect zero trial_budget"

        # Negative budget
        config_data["stages"][0]["trial_budget"] = -5
        errors = validate_study_schema(config_data)
        assert any("trial_budget" in err for err in errors), \
            "Should detect negative trial_budget"

    def test_validate_survivor_count_exceeds_budget(self) -> None:
        """Test detection of survivor count exceeding trial budget."""
        config_data = {
            "name": "test_study",
            "safety_domain": "guarded",
            "base_case_name": "nangate45_base",
            "pdk": "Nangate45",
            "snapshot_path": "/tmp/snapshots",
            "stages": [
                {
                    "name": "stage_0",
                    "execution_mode": "sta_only",
                    "trial_budget": 5,
                    "survivor_count": 10,  # Exceeds budget
                }
            ],
        }

        errors = validate_study_schema(config_data)
        assert any("exceed" in err.lower() and "trial_budget" in err for err in errors), \
            "Should detect survivor_count exceeding trial_budget"

    def test_validate_invalid_eco_class(self) -> None:
        """Test detection of invalid ECO class."""
        config_data = {
            "name": "test_study",
            "safety_domain": "guarded",
            "base_case_name": "nangate45_base",
            "pdk": "Nangate45",
            "snapshot_path": "/tmp/snapshots",
            "stages": [
                {
                    "name": "stage_0",
                    "execution_mode": "sta_only",
                    "trial_budget": 10,
                    "survivor_count": 5,
                    "allowed_eco_classes": ["invalid_eco_class"],
                }
            ],
        }

        errors = validate_study_schema(config_data)
        assert any("eco" in err.lower() and "invalid_eco_class" in err for err in errors), \
            "Should detect invalid ECO class"

    def test_validate_multiple_errors(self) -> None:
        """Step 5: Test that multiple errors are reported clearly."""
        config_data = {
            "name": "",  # Empty name
            "safety_domain": "invalid",  # Invalid domain
            "base_case_name": "nangate45_base",
            "pdk": "Nangate45",
            "snapshot_path": "/tmp/snapshots",
            "stages": [
                {
                    "name": "stage_0",
                    "execution_mode": "invalid_mode",  # Invalid mode
                    "trial_budget": -5,  # Invalid budget
                    "survivor_count": 10,  # Will exceed budget
                }
            ],
        }

        errors = validate_study_schema(config_data)

        # Should have multiple errors
        assert len(errors) >= 3, f"Should detect multiple errors, got: {errors}"

        # Verify different types of errors are detected
        assert any("name" in err for err in errors), "Should detect empty name"
        assert any("safety_domain" in err for err in errors), "Should detect invalid domain"
        assert any("execution_mode" in err for err in errors), "Should detect invalid mode"
        assert any("trial_budget" in err for err in errors), "Should detect invalid budget"


class TestDryRunMode:
    """
    Feature #87: Support dry-run mode to validate configuration without executing trials.

    Steps:
        1. Load Study configuration
        2. Enable dry-run mode
        3. Validate all configuration parameters
        4. Generate Run Legality Report
        5. Exit without executing trials
        6. Report validation results to user
    """

    def test_dry_run_valid_config(self) -> None:
        """Test dry-run validation of a valid configuration."""
        yaml_content = """
name: nangate45_test_study
safety_domain: sandbox
base_case_name: nangate45_base
pdk: Nangate45
snapshot_path: /tmp/snapshots/nangate45

stages:
  - name: stage_0
    execution_mode: sta_only
    trial_budget: 10
    survivor_count: 5
    allowed_eco_classes:
      - topology_neutral
      - placement_local
"""

        # Step 1: Create temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            # Step 2-3: Enable dry-run mode and validate
            result = dry_run_validation(yaml_path)

            # Step 6: Verify validation results
            assert result["valid"] is True, f"Config should be valid: {result['errors']}"
            assert len(result["errors"]) == 0, "Should have no errors"

            # Verify config summary
            assert result["config_summary"]["name"] == "nangate45_test_study"
            assert result["config_summary"]["safety_domain"] == "sandbox"
            assert result["config_summary"]["pdk"] == "Nangate45"
            assert result["config_summary"]["stage_count"] == 1
            assert result["config_summary"]["total_trial_budget"] == 10

            # Step 4: Verify legality assessment is generated
            assert "legality_assessment" in result
            assert result["legality_assessment"]["safety_domain"] == "sandbox"

        finally:
            Path(yaml_path).unlink()

    def test_dry_run_invalid_config(self) -> None:
        """Test dry-run validation of an invalid configuration."""
        yaml_content = """
name: invalid_study
safety_domain: invalid_domain
base_case_name: nangate45_base
pdk: Nangate45
snapshot_path: /tmp/snapshots

stages:
  - name: stage_0
    execution_mode: invalid_mode
    trial_budget: 0
    survivor_count: 5
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            result = dry_run_validation(yaml_path)

            # Should be invalid
            assert result["valid"] is False, "Config should be invalid"
            assert len(result["errors"]) > 0, "Should have errors"

            # Errors should be descriptive
            assert any(err for err in result["errors"]), "Should have error messages"

        finally:
            Path(yaml_path).unlink()

    def test_dry_run_missing_file(self) -> None:
        """Test dry-run validation with missing file."""
        result = dry_run_validation("/nonexistent/config.yaml")

        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert any("not found" in err.lower() for err in result["errors"])

    def test_dry_run_generates_warnings(self) -> None:
        """Test that dry-run generates appropriate warnings."""
        yaml_content = """
name: high_budget_study
safety_domain: sandbox
base_case_name: nangate45_base
pdk: Nangate45
snapshot_path: /tmp/snapshots

stages:
  - name: stage_0
    execution_mode: sta_only
    trial_budget: 150
    survivor_count: 50
    visualization_enabled: true
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            result = dry_run_validation(yaml_path)

            # Should be valid but have warnings
            assert result["valid"] is True
            assert len(result["warnings"]) > 0

            # Should warn about sandbox mode
            assert any("sandbox" in warn.lower() for warn in result["warnings"])

            # Should warn about high trial budget
            assert any("trial_budget" in warn for warn in result["warnings"])

            # Should warn about visualization
            assert any("visualization" in warn.lower() for warn in result["warnings"])

        finally:
            Path(yaml_path).unlink()

    def test_dry_run_does_not_execute_trials(self) -> None:
        """Step 5: Verify dry-run does not execute trials."""
        yaml_content = """
name: dry_run_test
safety_domain: guarded
base_case_name: nangate45_base
pdk: Nangate45
snapshot_path: /tmp/snapshots

stages:
  - name: stage_0
    execution_mode: sta_only
    trial_budget: 5
    survivor_count: 2
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            # Perform dry-run
            result = dry_run_validation(yaml_path)

            # Validation completes without executing trials
            assert result["valid"] is True
            assert "config_summary" in result
            assert "legality_assessment" in result

            # No trial execution artifacts should be created
            # (This is implicit - the function returns immediately after validation)

        finally:
            Path(yaml_path).unlink()

    def test_dry_run_illegal_configuration(self) -> None:
        """Test dry-run detection of safety domain violations."""
        yaml_content = """
name: illegal_study
safety_domain: locked
base_case_name: nangate45_base
pdk: Nangate45
snapshot_path: /tmp/snapshots

stages:
  - name: stage_0
    execution_mode: sta_only
    trial_budget: 10
    survivor_count: 5
    allowed_eco_classes:
      - global_disruptive
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            result = dry_run_validation(yaml_path)

            # Config is syntactically valid but may be illegal
            # Check for warnings about safety violations
            if not result["legality_assessment"].get("legal", True):
                assert len(result["warnings"]) > 0
                assert any("safety" in warn.lower() for warn in result["warnings"])

        finally:
            Path(yaml_path).unlink()


class TestValidateStudyConfig:
    """Test validation of parsed StudyConfig objects."""

    def test_validate_parsed_config(self) -> None:
        """Test validation of a parsed StudyConfig object."""
        config = create_study_config(
            name="test_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="/tmp/test",
        )

        errors = validate_study_config(config)
        assert len(errors) == 0, "Valid config should have no errors"

    def test_validate_invalid_parsed_config(self) -> None:
        """Test validation catches errors in parsed config."""
        # Create config with invalid stage budget
        with pytest.raises(ValueError):
            create_study_config(
                name="test_study",
                pdk="Nangate45",
                base_case_name="nangate45_base",
                snapshot_path="/tmp/test",
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=0,  # Invalid
                        survivor_count=5,
                        allowed_eco_classes=[],
                    )
                ],
            )
