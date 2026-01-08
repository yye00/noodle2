"""Reproducible demo Study configuration for Nangate45.

This module provides a fixed, deterministic demo Study configuration
that can be used for testing, demonstrations, and reproducibility verification.
The demo Study is designed to:
- Run consistently across different machines
- Provide clear, observable results
- Serve as a template for new users
- Enable regression testing
"""

from pathlib import Path

from .types import (
    ECOClass,
    ExecutionMode,
    SafetyDomain,
    StageConfig,
    StudyConfig,
)


def create_nangate45_demo_study(
    snapshot_path: str | None = None,
    safety_domain: SafetyDomain = SafetyDomain.GUARDED,
) -> StudyConfig:
    """Create a reproducible demo Study for Nangate45.

    This creates a fixed 3-stage Study configuration designed for:
    - Reproducibility testing across machines
    - New user onboarding and tutorials
    - Integration testing
    - Regression baselines

    Args:
        snapshot_path: Path to Nangate45 design snapshot.
                      If None, uses default 'studies/nangate45_base'
        safety_domain: Safety domain for the Study (default: GUARDED)

    Returns:
        StudyConfig: Fully configured demo Study

    Example:
        >>> demo = create_nangate45_demo_study()
        >>> demo.validate()  # Ensure configuration is valid
        >>> # Execute with StudyExecutor
    """
    if snapshot_path is None:
        # Default to studies/nangate45_base relative to project root
        snapshot_path = str(Path("studies") / "nangate45_base")

    # Stage 0: Exploration - Wide search with conservative ECOs
    stage_0 = StageConfig(
        name="exploration",
        execution_mode=ExecutionMode.STA_ONLY,
        trial_budget=10,
        survivor_count=3,
        allowed_eco_classes=[
            ECOClass.TOPOLOGY_NEUTRAL,
        ],
        abort_threshold_wns_ps=-50000,  # -50ns - very permissive
        visualization_enabled=True,
        timeout_seconds=300,  # 5 minutes per trial
    )

    # Stage 1: Refinement - Medium search with moderate ECOs
    stage_1 = StageConfig(
        name="refinement",
        execution_mode=ExecutionMode.STA_ONLY,
        trial_budget=6,
        survivor_count=2,
        allowed_eco_classes=[
            ECOClass.TOPOLOGY_NEUTRAL,
            ECOClass.PLACEMENT_LOCAL,
        ],
        abort_threshold_wns_ps=-100000,  # -100ns - moderate
        visualization_enabled=True,
        timeout_seconds=600,  # 10 minutes per trial
    )

    # Stage 2: Closure - Focused search with all ECOs
    stage_2 = StageConfig(
        name="closure",
        execution_mode=ExecutionMode.STA_ONLY,
        trial_budget=4,
        survivor_count=2,
        allowed_eco_classes=[
            ECOClass.TOPOLOGY_NEUTRAL,
            ECOClass.PLACEMENT_LOCAL,
            ECOClass.ROUTING_AFFECTING,
        ],
        abort_threshold_wns_ps=None,  # No abort threshold in final stage
        visualization_enabled=True,
        timeout_seconds=900,  # 15 minutes per trial
    )

    # Create the complete Study configuration
    study = StudyConfig(
        name="nangate45_demo",
        safety_domain=safety_domain,
        base_case_name="nangate45_base",
        pdk="Nangate45",
        stages=[stage_0, stage_1, stage_2],
        snapshot_path=snapshot_path,
        metadata={
            "purpose": "Reproducible demo Study for Nangate45 PDK",
            "design": "counter (4-bit counter)",
            "expected_behavior": "Deterministic results across machines",
            "version": "1.0.0",
        },
        author="Noodle2 Team",
        description=(
            "Reproducible 3-stage demo Study on Nangate45 open PDK. "
            "This Study demonstrates multi-stage ECO exploration with "
            "progressively aggressive ECO classes. Designed for testing, "
            "tutorials, and reproducibility verification."
        ),
        tags=["demo", "nangate45", "reproducible", "tutorial"],
    )

    # Validate configuration before returning
    study.validate()

    return study


def create_minimal_demo_study(
    snapshot_path: str | None = None,
) -> StudyConfig:
    """Create a minimal single-stage demo Study for quick testing.

    This is a simplified version of the demo Study with just one stage,
    useful for:
    - Quick integration tests
    - CI/CD pipelines
    - Debugging and development

    Args:
        snapshot_path: Path to Nangate45 design snapshot.
                      If None, uses default 'studies/nangate45_base'

    Returns:
        StudyConfig: Minimal demo Study configuration
    """
    if snapshot_path is None:
        snapshot_path = str(Path("studies") / "nangate45_base")

    # Single stage with minimal trial budget
    stage = StageConfig(
        name="quick_test",
        execution_mode=ExecutionMode.STA_ONLY,
        trial_budget=3,
        survivor_count=1,
        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
        abort_threshold_wns_ps=-50000,
        visualization_enabled=False,
        timeout_seconds=180,  # 3 minutes
    )

    study = StudyConfig(
        name="nangate45_minimal_demo",
        safety_domain=SafetyDomain.SANDBOX,
        base_case_name="nangate45_base",
        pdk="Nangate45",
        stages=[stage],
        snapshot_path=snapshot_path,
        metadata={
            "purpose": "Minimal demo for quick testing",
            "version": "1.0.0",
        },
        author="Noodle2 Team",
        description="Minimal single-stage demo Study for quick testing",
        tags=["demo", "minimal", "quick"],
    )

    study.validate()

    return study


def get_demo_study_expected_metrics() -> dict[str, int]:
    """Get expected metrics ranges for demo Study validation.

    Returns a dictionary of expected metric ranges that can be used
    to verify reproducibility across different machines.

    Returns:
        Dictionary with expected metric ranges:
        - base_case_wns_ps: Expected WNS for base case (in picoseconds)
        - min_trial_count: Minimum expected trial count
        - max_trial_count: Maximum expected trial count
        - expected_stages: Number of stages
    """
    return {
        "base_case_wns_ps": 2500,  # 2.5ns from run_sta.tcl
        "min_trial_count": 20,  # 10 + 6 + 4 = 20 total trials
        "max_trial_count": 20,
        "expected_stages": 3,
        "stage_0_trial_budget": 10,
        "stage_1_trial_budget": 6,
        "stage_2_trial_budget": 4,
    }


def save_demo_study_config(output_path: Path) -> None:
    """Save demo Study configuration to JSON file.

    This creates a standalone JSON configuration file that can be
    shared and loaded independently.

    Args:
        output_path: Path where to save the JSON configuration
    """
    import json
    from dataclasses import asdict

    demo = create_nangate45_demo_study()

    # Convert to dict (handle enums)
    def convert_value(obj: object) -> object:
        """Convert dataclass/enum values to JSON-serializable types."""
        if hasattr(obj, "value"):  # Enum
            return obj.value
        elif isinstance(obj, list):
            return [convert_value(item) for item in obj]
        elif hasattr(obj, "__dict__"):  # dataclass
            return {k: convert_value(v) for k, v in asdict(obj).items()}
        else:
            return obj

    config_dict = convert_value(demo)

    # Write to file with pretty formatting
    with output_path.open("w") as f:
        json.dump(config_dict, f, indent=2, sort_keys=True)
