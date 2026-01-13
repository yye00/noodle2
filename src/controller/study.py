"""Study configuration loading and management."""

import yaml
from pathlib import Path
from typing import Any

from .types import (
    AbortRailConfig,
    ECOClass,
    ExecutionMode,
    RailsConfig,
    SafetyDomain,
    StageConfig,
    StageRailConfig,
    StudyConfig,
    StudyRailConfig,
)


def load_study_config(config_path: str | Path) -> StudyConfig:
    """
    Load Study configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        StudyConfig object

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If configuration is invalid
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Study configuration not found: {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    if not data:
        raise ValueError(f"Empty configuration file: {config_path}")

    return _parse_study_config(data)


def _parse_study_config(data: dict[str, Any]) -> StudyConfig:
    """Parse Study configuration from dictionary."""
    # Parse stages
    stages_data = data.get("stages", [])
    if not stages_data:
        raise ValueError("Study must define at least one stage")

    stages = []
    for stage_data in stages_data:
        stage = _parse_stage_config(stage_data)
        stages.append(stage)

    # Parse ECO filtering constraints
    eco_blacklist = data.get("eco_blacklist", [])
    eco_whitelist = data.get("eco_whitelist")  # None if not specified

    # Parse environment variables
    environment = data.get("environment", {})

    # Parse custom script mounts
    custom_script_mounts = data.get("custom_script_mounts", {})

    # Parse notification configuration
    notification_webhook_url = data.get("notification_webhook_url")
    notification_events = data.get("notification_events")

    # Parse rails configuration
    rails = _parse_rails_config(data.get("rails", {}))

    # Create StudyConfig
    config = StudyConfig(
        name=data["name"],
        safety_domain=SafetyDomain(data["safety_domain"]),
        base_case_name=data["base_case_name"],
        pdk=data["pdk"],
        stages=stages,
        snapshot_path=data["snapshot_path"],
        metadata=data.get("metadata", {}),
        eco_blacklist=eco_blacklist,
        eco_whitelist=eco_whitelist,
        environment=environment,
        custom_script_mounts=custom_script_mounts,
        notification_webhook_url=notification_webhook_url,
        notification_events=notification_events,
        rails=rails,
    )

    # Validate configuration
    config.validate()

    return config


def _parse_stage_config(data: dict[str, Any]) -> StageConfig:
    """Parse Stage configuration from dictionary."""
    allowed_eco_classes = [ECOClass(cls) for cls in data.get("allowed_eco_classes", [])]

    return StageConfig(
        name=data["name"],
        execution_mode=ExecutionMode(data["execution_mode"]),
        trial_budget=data["trial_budget"],
        survivor_count=data["survivor_count"],
        allowed_eco_classes=allowed_eco_classes,
        abort_threshold_wns_ps=data.get("abort_threshold_wns_ps"),
        visualization_enabled=data.get("visualization_enabled", False),
        timeout_seconds=data.get("timeout_seconds", 3600),
    )


def _parse_rails_config(data: dict[str, Any]) -> RailsConfig:
    """Parse Rails configuration from dictionary."""
    # Parse abort rail
    abort_data = data.get("abort", {})
    abort_rail = AbortRailConfig(
        wns_ps=abort_data.get("wns_ps"),
        timeout_seconds=abort_data.get("timeout_seconds"),
    )

    # Parse stage rail
    stage_data = data.get("stage", {})
    stage_rail = StageRailConfig(
        failure_rate=stage_data.get("failure_rate"),
    )

    # Parse study rail
    study_data = data.get("study", {})
    study_rail = StudyRailConfig(
        catastrophic_failures=study_data.get("catastrophic_failures"),
        max_runtime_hours=study_data.get("max_runtime_hours"),
    )

    return RailsConfig(
        abort=abort_rail,
        stage=stage_rail,
        study=study_rail,
    )


def create_study_config(
    name: str,
    pdk: str,
    base_case_name: str,
    snapshot_path: str,
    safety_domain: SafetyDomain = SafetyDomain.GUARDED,
    stages: list[StageConfig] | None = None,
) -> StudyConfig:
    """
    Create a Study configuration programmatically.

    Args:
        name: Study name
        pdk: PDK name (e.g., "Nangate45", "ASAP7", "Sky130")
        base_case_name: Base case identifier
        snapshot_path: Path to design snapshot
        safety_domain: Safety domain (default: GUARDED)
        stages: List of stage configurations (creates default if None)

    Returns:
        StudyConfig object
    """
    if stages is None:
        # Create a minimal single-stage configuration
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.PLACEMENT_LOCAL,
                ],
            )
        ]

    config = StudyConfig(
        name=name,
        safety_domain=safety_domain,
        base_case_name=base_case_name,
        pdk=pdk,
        stages=stages,
        snapshot_path=snapshot_path,
    )

    config.validate()
    return config
