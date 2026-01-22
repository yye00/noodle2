"""YAML-based study configuration loader.

This module provides runtime configuration of Noodle 2 studies via YAML files,
eliminating the need to modify code for different study configurations.
"""

import yaml
from pathlib import Path
from typing import Any

from .types import (
    AbortRailConfig,
    DiagnosisConfig,
    ECOClass,
    ExecutionMode,
    ObjectiveConfig,
    ObjectiveMode,
    RailsConfig,
    SafetyDomain,
    StageConfig,
    StageRailConfig,
    StudyConfig,
    StudyRailConfig,
)


class YAMLConfigError(Exception):
    """Error in YAML configuration."""

    pass


def load_study_from_yaml(config_path: str | Path) -> StudyConfig:
    """
    Load a complete Study configuration from a YAML file.

    This is the main entry point for YAML-based study configuration.
    The YAML file can specify all aspects of a study including:
    - Study metadata (name, description, author)
    - Design configuration (PDK, snapshot path)
    - Safety domain
    - Execution settings (Ray, timeouts)
    - Viability criteria (early failure detection)
    - Prior learning configuration
    - Stage configuration (count, budgets, ECO classes)
    - ECO parameters and variants

    Args:
        config_path: Path to the YAML configuration file

    Returns:
        StudyConfig: Fully configured study ready for execution

    Raises:
        FileNotFoundError: If config file doesn't exist
        YAMLConfigError: If configuration is invalid
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Study configuration not found: {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    if not data:
        raise YAMLConfigError(f"Empty configuration file: {config_path}")

    return _parse_yaml_config(data, config_path)


def _parse_yaml_config(data: dict[str, Any], config_path: Path) -> StudyConfig:
    """Parse complete YAML configuration into StudyConfig."""
    # Extract top-level sections
    study_section = data.get("study", {})
    design_section = data.get("design", {})
    safety_section = data.get("safety", {})
    stages_section = data.get("stages", {})

    # Required fields
    name = study_section.get("name")
    if not name:
        raise YAMLConfigError("study.name is required")

    pdk = design_section.get("pdk")
    if not pdk:
        raise YAMLConfigError("design.pdk is required")

    base_case_name = design_section.get("base_case_name")
    if not base_case_name:
        raise YAMLConfigError("design.base_case_name is required")

    snapshot_path = design_section.get("snapshot_path")
    if not snapshot_path:
        raise YAMLConfigError("design.snapshot_path is required")

    # Parse safety domain
    safety_domain_str = safety_section.get("domain", "guarded")
    try:
        safety_domain = SafetyDomain(safety_domain_str)
    except ValueError:
        raise YAMLConfigError(
            f"Invalid safety domain: {safety_domain_str}. "
            f"Valid options: sandbox, guarded, locked"
        )

    # Generate stages
    stages = _generate_stages(stages_section)

    # Parse metadata
    metadata = _build_metadata(data, design_section, study_section)

    # Parse rails configuration
    rails = _parse_rails(data.get("viability", {}), data.get("execution", {}))

    # Parse diagnosis configuration
    diagnosis = _parse_diagnosis(data.get("diagnosis", {}))

    # Parse objective configuration
    objective = _parse_objective(data.get("objective", {}))

    # Create StudyConfig
    config = StudyConfig(
        name=name,
        safety_domain=safety_domain,
        base_case_name=base_case_name,
        pdk=pdk,
        stages=stages,
        snapshot_path=snapshot_path,
        metadata=metadata,
        author=study_section.get("author"),
        description=study_section.get("description"),
        tags=study_section.get("tags", []),
        rails=rails,
        diagnosis=diagnosis,
        objective=objective,
    )

    # Validate
    config.validate()

    return config


def _generate_stages(stages_section: dict[str, Any]) -> list[StageConfig]:
    """Generate stage configurations from YAML stages section."""
    num_stages = stages_section.get("count", 10)
    defaults = stages_section.get("defaults", {})
    overrides = stages_section.get("overrides", [])
    survivor_progression = stages_section.get("survivor_progression", {})

    # Default values
    default_trial_budget = defaults.get("trial_budget", 25)
    default_survivor_count = defaults.get("survivor_count", 8)
    default_timeout = defaults.get("timeout_seconds", 1800)
    default_viz_enabled = defaults.get("visualization_enabled", True)
    default_abort_threshold = defaults.get("abort_threshold_wns_ps")
    default_execution_mode = defaults.get("execution_mode", "sta_congestion")

    # Parse survivor progression
    survivors_list = _calculate_survivor_progression(
        survivor_progression, num_stages, default_survivor_count
    )

    # Build override lookup
    override_map = _build_override_map(overrides, num_stages)

    stages = []
    for i in range(num_stages):
        # Get override for this stage if exists
        override = override_map.get(i, {})

        # Determine ECO classes
        eco_classes_raw = override.get(
            "allowed_eco_classes",
            ["topology_neutral", "placement_local"] if i < 2 else [
                "topology_neutral", "placement_local",
                "routing_affecting", "global_disruptive"
            ]
        )
        eco_classes = [ECOClass(cls) for cls in eco_classes_raw]

        # Determine execution mode
        exec_mode_str = override.get("execution_mode", default_execution_mode)
        execution_mode = ExecutionMode(exec_mode_str)

        # Create stage config
        stage = StageConfig(
            name=f"stage_{i}",
            execution_mode=execution_mode,
            trial_budget=override.get("trial_budget", default_trial_budget),
            survivor_count=survivors_list[i],
            allowed_eco_classes=eco_classes,
            abort_threshold_wns_ps=override.get("abort_threshold_wns_ps", default_abort_threshold),
            visualization_enabled=override.get("visualization_enabled", default_viz_enabled),
            timeout_seconds=override.get("timeout_seconds", default_timeout),
        )
        stages.append(stage)

    return stages


def _calculate_survivor_progression(
    progression: dict[str, Any],
    num_stages: int,
    default_count: int
) -> list[int]:
    """Calculate survivor counts for each stage based on progression type."""
    prog_type = progression.get("type", "fixed")

    if prog_type == "fixed":
        return [default_count] * num_stages

    elif prog_type == "funnel":
        start = progression.get("start", 8)
        end = progression.get("end", 2)
        # Linear interpolation with integer rounding
        survivors = []
        for i in range(num_stages):
            if num_stages == 1:
                count = start
            else:
                ratio = i / (num_stages - 1)
                count = int(start + ratio * (end - start))
            survivors.append(max(end, count))
        return survivors

    elif prog_type == "custom":
        custom_list = progression.get("survivors", [])
        if len(custom_list) < num_stages:
            # Pad with last value
            last_val = custom_list[-1] if custom_list else default_count
            custom_list.extend([last_val] * (num_stages - len(custom_list)))
        return custom_list[:num_stages]

    else:
        raise YAMLConfigError(
            f"Invalid survivor_progression type: {prog_type}. "
            f"Valid options: fixed, funnel, custom"
        )


def _build_override_map(
    overrides: list[dict[str, Any]],
    num_stages: int
) -> dict[int, dict[str, Any]]:
    """Build a mapping from stage index to override configuration."""
    override_map: dict[int, dict[str, Any]] = {}

    for override in overrides:
        stages_spec = override.get("stages", [])

        # Parse stages specification
        stage_indices: list[int] = []
        if isinstance(stages_spec, list):
            stage_indices = stages_spec
        elif isinstance(stages_spec, str):
            # Handle "N+" format (e.g., "2+" means stages 2 and above)
            if stages_spec.endswith("+"):
                start_idx = int(stages_spec[:-1])
                stage_indices = list(range(start_idx, num_stages))
            else:
                # Try single stage number
                stage_indices = [int(stages_spec)]
        elif isinstance(stages_spec, int):
            stage_indices = [stages_spec]

        # Apply override to each specified stage
        for idx in stage_indices:
            if 0 <= idx < num_stages:
                override_map[idx] = {
                    k: v for k, v in override.items()
                    if k != "stages"
                }

    return override_map


def _build_metadata(
    data: dict[str, Any],
    design_section: dict[str, Any],
    study_section: dict[str, Any]
) -> dict[str, Any]:
    """Build metadata dictionary from various YAML sections."""
    metadata: dict[str, Any] = {}

    # Include initial metrics if provided
    if "initial_metrics" in design_section:
        metadata["initial_state"] = design_section["initial_metrics"]

    # Include targets if provided
    if "targets" in data:
        metadata["target_improvements"] = data["targets"]

    # Include version
    if "version" in study_section:
        metadata["version"] = study_section["version"]

    # Include prior learning config
    if "prior_learning" in data:
        metadata["prior_learning"] = data["prior_learning"]

    # Include viability config
    if "viability" in data:
        metadata["viability"] = data["viability"]

    # Include ECO configuration summary
    if "ecos" in data:
        eco_config = data["ecos"]
        metadata["eco_config"] = {
            "base_ecos": list(eco_config.get("base", {}).keys()),
            "aggressive_ecos": list(eco_config.get("aggressive", {}).keys()),
        }

    # Include execution config
    if "execution" in data:
        metadata["execution"] = data["execution"]

    # Include output config
    if "output" in data:
        metadata["output"] = data["output"]

    return metadata


def _parse_rails(
    viability: dict[str, Any],
    execution: dict[str, Any]
) -> RailsConfig:
    """Parse rails configuration from viability and execution sections."""
    # Abort rail
    abort = AbortRailConfig(
        wns_ps=viability.get("max_wns_degradation_ps"),
        timeout_seconds=execution.get("trial_timeout_seconds"),
    )

    # Stage rail - abort on stage failure
    stage = StageRailConfig(
        failure_rate=1.0 if viability.get("abort_on_stage_failure") else None,
    )

    # Study rail
    study = StudyRailConfig(
        max_runtime_hours=None,  # Can be added to YAML if needed
    )

    return RailsConfig(abort=abort, stage=stage, study=study)


def _parse_diagnosis(diagnosis_data: dict[str, Any]) -> DiagnosisConfig:
    """Parse diagnosis configuration."""
    return DiagnosisConfig(
        enabled=diagnosis_data.get("enabled", True),
        timing_paths=diagnosis_data.get("timing_paths", 20),
        hotspot_threshold=diagnosis_data.get("hotspot_threshold", 0.7),
        wire_delay_threshold=diagnosis_data.get("wire_delay_threshold", 0.65),
    )


def _parse_objective(objective_data: dict[str, Any]) -> ObjectiveConfig:
    """Parse objective configuration."""
    mode_str = objective_data.get("mode", "weighted_sum")
    try:
        mode = ObjectiveMode(mode_str)
    except ValueError:
        mode = ObjectiveMode.WEIGHTED_SUM

    return ObjectiveConfig(
        mode=mode,
        primary=objective_data.get("primary", "wns_ps"),
        secondary=objective_data.get("secondary"),
        weights=objective_data.get("weights"),
    )


def get_eco_config_from_yaml(config_path: str | Path) -> dict[str, Any]:
    """
    Extract ECO configuration from YAML file.

    This returns the raw ECO configuration for use by the executor
    to determine which ECOs to run and with what parameters.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Dictionary with 'base' and 'aggressive' ECO configurations
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration not found: {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    return data.get("ecos", {})


def get_prior_learning_config(config_path: str | Path) -> dict[str, Any]:
    """
    Extract prior learning configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Dictionary with prior learning settings
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration not found: {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    return data.get("prior_learning", {
        "enabled": False,
        "filter_from_stage": 3,
        "min_data_points": 3,
        "trusted_threshold": 0.8,
        "suspicious_threshold": 0.7,
        "cross_project_db": None,
        # Enhanced learning options
        "use_wns_weighted_selection": True,  # Prioritize ECOs by WNS improvement magnitude
        "within_study_learning": True,  # Use current study's successes to influence later stages
        "cross_study_learning": False,  # Load priors from other studies/PDKs
        "cross_study_weight": 0.5,  # Weight for cross-study priors (0.0-1.0)
        "check_anti_patterns": True,  # Skip ECOs with known anti-patterns for current context
        "exploration_rate": 0.2,  # Fraction of trials for exploration (try less-proven ECOs)
    })


def get_viability_config(config_path: str | Path) -> dict[str, Any]:
    """
    Extract viability/early failure detection configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Dictionary with viability settings
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration not found: {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    return data.get("viability", {
        "abort_on_base_case_failure": True,
        "min_improvement_threshold": 0.0,
        "max_wns_degradation_ps": None,
        "abort_on_stage_failure": True,
        # Rollback configuration
        "enable_rollback": False,
        "rollback_threshold_ps": 50,
        # Recovery configuration - try successful ECOs before rollback
        "enable_recovery": False,
        "recovery_trials": 5,  # Number of recovery trials to attempt
        "recovery_strategy": "top_performers",  # top_performers, conservative, recent_successful
    })


def get_execution_config(config_path: str | Path) -> dict[str, Any]:
    """
    Extract execution configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Dictionary with execution settings (Ray, timeouts, etc.)
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration not found: {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    return data.get("execution", {
        "use_ray": True,
        "ray_dashboard": True,
        "ray_dashboard_port": 8265,
        "max_concurrent_trials": 0,
        "trial_timeout_seconds": 1800,
    })


def get_output_config(config_path: str | Path) -> dict[str, Any]:
    """
    Extract output configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Dictionary with output settings including:
        - dir: Base output directory
        - visualizations: Generate before/after/comparison visualizations
        - heatmaps: Generate heatmap PNGs
        - lineage_graph: Generate case lineage DOT file
        - eco_leaderboard: Generate ECO effectiveness rankings
        - keep_trial_artifacts: Keep raw trial data in trials/ subdirectory
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration not found: {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    output_config = data.get("output", {})

    # Handle both old format (artifacts_dir + demo_output_dir) and new format (dir)
    if "dir" in output_config:
        # New unified format
        return {
            "dir": output_config.get("dir", "output"),
            "visualizations": output_config.get("visualizations", True),
            "heatmaps": output_config.get("heatmaps", True),
            "lineage_graph": output_config.get("lineage_graph", True),
            "eco_leaderboard": output_config.get("eco_leaderboard", True),
            "keep_trial_artifacts": output_config.get("keep_trial_artifacts", True),
        }
    else:
        # Legacy format - convert to new format
        return {
            "dir": output_config.get("artifacts_dir", "output"),
            "visualizations": output_config.get("visualizations", True),
            "heatmaps": output_config.get("heatmaps", True),
            "lineage_graph": output_config.get("lineage_graph", True),
            "eco_leaderboard": output_config.get("eco_leaderboard", True),
            "keep_trial_artifacts": True,
        }


def list_available_configs(studies_dir: str | Path = "studies") -> list[Path]:
    """
    List available YAML configuration files in the studies directory.

    Args:
        studies_dir: Directory containing study configuration files

    Returns:
        List of paths to YAML configuration files
    """
    studies_path = Path(studies_dir)
    if not studies_path.exists():
        return []

    return sorted(studies_path.glob("*.yaml"))


def validate_yaml_config(config_path: str | Path) -> tuple[bool, str | None]:
    """
    Validate a YAML configuration file without loading it as a StudyConfig.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Tuple of (valid: bool, error_message: str | None)
    """
    try:
        load_study_from_yaml(config_path)
        return True, None
    except Exception as e:
        return False, str(e)
