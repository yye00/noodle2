"""
Schema validation and dry-run support for Study configurations.

This module provides:
- JSON schema validation for Study configurations
- Dry-run mode for validating configurations without executing trials
- Comprehensive error reporting for invalid configurations
"""

from pathlib import Path
from typing import Any

from .types import (
    ECOClass,
    ExecutionMode,
    SafetyDomain,
    StudyConfig,
)


class ValidationError(Exception):
    """Raised when configuration validation fails."""

    def __init__(self, message: str, field: str | None = None):
        """
        Initialize validation error.

        Args:
            message: Error message
            field: Name of the field that failed validation (if applicable)
        """
        self.field = field
        super().__init__(message)


def validate_study_schema(data: dict[str, Any]) -> list[str]:
    """
    Validate Study configuration against schema.

    This performs comprehensive validation beyond basic type checking,
    including semantic validation of field values and relationships.

    Args:
        data: Study configuration dictionary

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Required fields
    required_fields = ["name", "safety_domain", "base_case_name", "pdk", "stages", "snapshot_path"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if errors:
        # Don't continue if required fields are missing
        return errors

    # Validate name
    if not isinstance(data["name"], str) or not data["name"].strip():
        errors.append("Field 'name' must be a non-empty string")

    # Validate safety_domain
    try:
        SafetyDomain(data["safety_domain"])
    except (ValueError, KeyError):
        valid_domains = [d.value for d in SafetyDomain]
        errors.append(
            f"Invalid safety_domain '{data.get('safety_domain')}'. "
            f"Must be one of: {valid_domains}"
        )

    # Validate base_case_name
    if not isinstance(data["base_case_name"], str) or not data["base_case_name"].strip():
        errors.append("Field 'base_case_name' must be a non-empty string")

    # Validate pdk
    if not isinstance(data["pdk"], str) or not data["pdk"].strip():
        errors.append("Field 'pdk' must be a non-empty string")

    # Validate snapshot_path
    if not isinstance(data["snapshot_path"], str) or not data["snapshot_path"].strip():
        errors.append("Field 'snapshot_path' must be a non-empty string")

    # Validate stages
    if not isinstance(data["stages"], list):
        errors.append("Field 'stages' must be a list")
    elif len(data["stages"]) == 0:
        errors.append("Study must define at least one stage")
    else:
        for idx, stage in enumerate(data["stages"]):
            stage_errors = _validate_stage_schema(stage, idx)
            errors.extend(stage_errors)

    # Validate optional metadata
    if "metadata" in data:
        if not isinstance(data["metadata"], dict):
            errors.append("Field 'metadata' must be a dictionary")

    # Validate optional author
    if "author" in data:
        if not isinstance(data["author"], str):
            errors.append("Field 'author' must be a string")

    # Validate optional creation_date
    if "creation_date" in data:
        if not isinstance(data["creation_date"], str):
            errors.append("Field 'creation_date' must be a string (ISO 8601 format)")

    # Validate optional description
    if "description" in data:
        if not isinstance(data["description"], str):
            errors.append("Field 'description' must be a string")

    return errors


def _validate_stage_schema(stage: dict[str, Any], stage_idx: int) -> list[str]:
    """
    Validate a single Stage configuration.

    Args:
        stage: Stage configuration dictionary
        stage_idx: Index of the stage in the stages list

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    stage_prefix = f"Stage {stage_idx}"

    # Required fields
    required_fields = ["name", "execution_mode", "trial_budget", "survivor_count"]
    for field in required_fields:
        if field not in stage:
            errors.append(f"{stage_prefix}: Missing required field '{field}'")

    if errors:
        return errors

    # Validate name
    if not isinstance(stage["name"], str) or not stage["name"].strip():
        errors.append(f"{stage_prefix}: Field 'name' must be a non-empty string")

    # Validate execution_mode
    try:
        ExecutionMode(stage["execution_mode"])
    except (ValueError, KeyError):
        valid_modes = [m.value for m in ExecutionMode]
        errors.append(
            f"{stage_prefix}: Invalid execution_mode '{stage.get('execution_mode')}'. "
            f"Must be one of: {valid_modes}"
        )

    # Validate trial_budget
    if not isinstance(stage["trial_budget"], int) or stage["trial_budget"] <= 0:
        errors.append(f"{stage_prefix}: Field 'trial_budget' must be a positive integer")

    # Validate survivor_count
    if not isinstance(stage["survivor_count"], int) or stage["survivor_count"] <= 0:
        errors.append(f"{stage_prefix}: Field 'survivor_count' must be a positive integer")

    # Validate survivor_count <= trial_budget
    if (
        isinstance(stage.get("trial_budget"), int)
        and isinstance(stage.get("survivor_count"), int)
        and stage["survivor_count"] > stage["trial_budget"]
    ):
        errors.append(
            f"{stage_prefix}: survivor_count ({stage['survivor_count']}) "
            f"cannot exceed trial_budget ({stage['trial_budget']})"
        )

    # Validate allowed_eco_classes (optional)
    if "allowed_eco_classes" in stage:
        if not isinstance(stage["allowed_eco_classes"], list):
            errors.append(f"{stage_prefix}: Field 'allowed_eco_classes' must be a list")
        else:
            for eco_cls in stage["allowed_eco_classes"]:
                try:
                    ECOClass(eco_cls)
                except ValueError:
                    valid_classes = [c.value for c in ECOClass]
                    errors.append(
                        f"{stage_prefix}: Invalid ECO class '{eco_cls}'. "
                        f"Must be one of: {valid_classes}"
                    )

    # Validate abort_threshold_wns_ps (optional)
    if "abort_threshold_wns_ps" in stage:
        value = stage["abort_threshold_wns_ps"]
        if value is not None and not isinstance(value, int):
            errors.append(f"{stage_prefix}: Field 'abort_threshold_wns_ps' must be an integer or null")

    # Validate visualization_enabled (optional)
    if "visualization_enabled" in stage:
        if not isinstance(stage["visualization_enabled"], bool):
            errors.append(f"{stage_prefix}: Field 'visualization_enabled' must be a boolean")

    # Validate timeout_seconds (optional)
    if "timeout_seconds" in stage:
        value = stage["timeout_seconds"]
        if not isinstance(value, int) or value <= 0:
            errors.append(f"{stage_prefix}: Field 'timeout_seconds' must be a positive integer")

    return errors


def validate_study_config(config: StudyConfig) -> list[str]:
    """
    Validate a parsed StudyConfig object.

    This validates the configuration after it has been parsed into
    a StudyConfig object, checking semantic constraints.

    Args:
        config: StudyConfig object to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    try:
        config.validate()
    except ValueError as e:
        errors.append(str(e))

    return errors


def generate_run_legality_report(config: StudyConfig) -> dict[str, Any]:
    """
    Generate a run legality report for a Study configuration.

    This is a thin wrapper around safety.generate_legality_report that
    returns a dictionary for easy integration with dry-run validation.

    Args:
        config: Study configuration

    Returns:
        Dictionary containing legality report
    """
    from .safety import generate_legality_report

    report = generate_legality_report(config)
    return report.to_dict()


def dry_run_validation(config_path: str | Path) -> dict[str, Any]:
    """
    Perform dry-run validation of a Study configuration.

    This loads and validates the configuration without executing any trials.
    It produces a comprehensive validation report including:
    - Configuration validity
    - Schema validation results
    - Run legality assessment (safety domain compatibility)
    - Warnings and recommendations

    Args:
        config_path: Path to Study configuration file

    Returns:
        Dictionary containing validation results with keys:
        - valid: bool indicating if configuration is valid
        - errors: list of error messages
        - warnings: list of warning messages
        - config_summary: dict with key configuration parameters
        - legality_assessment: dict with safety domain assessment

    Raises:
        FileNotFoundError: If config file doesn't exist
    """
    from .study import load_study_config

    config_path = Path(config_path)
    if not config_path.exists():
        return {
            "valid": False,
            "errors": [f"Configuration file not found: {config_path}"],
            "warnings": [],
            "config_summary": {},
            "legality_assessment": {},
        }

    errors = []
    warnings = []
    config_summary = {}
    legality_assessment = {}

    try:
        # Load configuration
        config = load_study_config(config_path)

        # Validate configuration
        validation_errors = validate_study_config(config)
        errors.extend(validation_errors)

        # Generate configuration summary
        config_summary = {
            "name": config.name,
            "safety_domain": config.safety_domain.value,
            "pdk": config.pdk,
            "base_case_name": config.base_case_name,
            "stage_count": len(config.stages),
            "total_trial_budget": sum(stage.trial_budget for stage in config.stages),
        }

        # Generate legality assessment
        try:
            legality_report = generate_run_legality_report(config)
            legality_assessment = {
                "safety_domain": legality_report.get("safety_domain"),
                "allowed_eco_classes": legality_report.get("allowed_eco_classes", []),
                "legal": legality_report.get("is_legal", True),
                "violations": legality_report.get("violations", []),
                "warnings": legality_report.get("warnings", []),
            }

            # Add warnings from legality report
            if not legality_report.get("is_legal", True):
                warnings.append(
                    "Configuration violates safety domain constraints. "
                    "See legality_assessment for details."
                )

        except Exception as e:
            warnings.append(f"Could not generate legality assessment: {e}")

        # Additional warnings
        if config.safety_domain == SafetyDomain.SANDBOX:
            warnings.append(
                "Safety domain is 'sandbox' - permissive mode suitable for exploration only"
            )

        for idx, stage in enumerate(config.stages):
            if stage.trial_budget > 100:
                warnings.append(
                    f"Stage {idx} has high trial_budget ({stage.trial_budget}). "
                    "Consider reducing for initial testing."
                )

            if stage.visualization_enabled:
                warnings.append(
                    f"Stage {idx} has visualization enabled. "
                    "Ensure GUI/Xvfb environment is configured."
                )

    except Exception as e:
        errors.append(f"Failed to load configuration: {e}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "config_summary": config_summary,
        "legality_assessment": legality_assessment,
    }
