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


def create_asap7_demo_study(
    snapshot_path: str | None = None,
    safety_domain: SafetyDomain = SafetyDomain.GUARDED,
) -> StudyConfig:
    """Create a reproducible demo Study for ASAP7 with STA-first staging.

    ASAP7 requires STA-first staging for stable results. This creates a
    3-stage Study that:
    - Stage 1: STA-only timing baseline (most stable)
    - Stage 2+: Optionally enable congestion analysis after timing is stable
    - Uses lower utilization (0.55) to prevent routing explosion
    - Includes all ASAP7-specific workarounds

    This configuration follows ASAP7 best practices:
    - STA-first (not congestion-first) for stability
    - Low utilization (0.50-0.55) for routing headroom
    - Explicit routing layer constraints
    - Proper site and pin placement constraints

    Args:
        snapshot_path: Path to ASAP7 design snapshot.
                      If None, uses default 'studies/asap7_base'
        safety_domain: Safety domain for the Study (default: GUARDED)

    Returns:
        StudyConfig: ASAP7 demo Study with STA-first staging

    Example:
        >>> demo = create_asap7_demo_study()
        >>> demo.validate()  # Ensure configuration is valid
        >>> # Stage 1 is STA-only (most stable for ASAP7)
        >>> assert demo.stages[0].execution_mode == ExecutionMode.STA_ONLY
    """
    if snapshot_path is None:
        # Default to studies/asap7_base relative to project root
        snapshot_path = str(Path("studies") / "asap7_base")

    # Stage 0: STA-only baseline (REQUIRED for ASAP7 stability)
    # This is the most stable execution mode for ASAP7 and should always be first
    stage_0 = StageConfig(
        name="sta_baseline",
        execution_mode=ExecutionMode.STA_ONLY,  # STA-first for ASAP7
        trial_budget=8,
        survivor_count=3,
        allowed_eco_classes=[
            ECOClass.TOPOLOGY_NEUTRAL,
        ],
        abort_threshold_wns_ps=-100000,  # -100ns - permissive for exploration
        visualization_enabled=True,
        timeout_seconds=600,  # 10 minutes per trial
    )

    # Stage 1: STA-only refinement (continue with stable mode)
    stage_1 = StageConfig(
        name="sta_refinement",
        execution_mode=ExecutionMode.STA_ONLY,  # Keep STA-only for stability
        trial_budget=5,
        survivor_count=2,
        allowed_eco_classes=[
            ECOClass.TOPOLOGY_NEUTRAL,
            ECOClass.PLACEMENT_LOCAL,
        ],
        abort_threshold_wns_ps=-150000,  # -150ns
        visualization_enabled=True,
        timeout_seconds=900,  # 15 minutes per trial
    )

    # Stage 2: Optional congestion analysis (only after timing is stable)
    # For ASAP7, defer congestion analysis until later stages
    stage_2 = StageConfig(
        name="congestion_closure",
        execution_mode=ExecutionMode.STA_CONGESTION,  # Add congestion in final stage
        trial_budget=3,
        survivor_count=2,
        allowed_eco_classes=[
            ECOClass.TOPOLOGY_NEUTRAL,
            ECOClass.PLACEMENT_LOCAL,
        ],
        abort_threshold_wns_ps=None,  # No abort in final stage
        visualization_enabled=True,
        timeout_seconds=1200,  # 20 minutes per trial
    )

    # Create the complete Study configuration
    study = StudyConfig(
        name="asap7_demo",
        safety_domain=safety_domain,
        base_case_name="asap7_base",
        pdk="ASAP7",  # Will trigger ASAP7-specific workarounds
        stages=[stage_0, stage_1, stage_2],
        snapshot_path=snapshot_path,
        metadata={
            "purpose": "Reproducible demo Study for ASAP7 PDK with STA-first staging",
            "design": "Counter or other ASAP7-compatible design",
            "expected_behavior": "Stable timing-first approach for ASAP7",
            "version": "1.0.0",
            "asap7_workarounds": [
                "routing_layer_constraints",
                "site_specification",
                "pin_placement_constraints",
                "low_utilization_0.55",
            ],
        },
        author="Noodle2 Team",
        description=(
            "Reproducible 3-stage demo Study for ASAP7 PDK following STA-first "
            "best practices. Stage 1-2 use STA-only mode for stability, while "
            "Stage 3 optionally adds congestion analysis after timing is stable. "
            "Uses low utilization (0.55) and ASAP7-specific workarounds to prevent "
            "routing explosion and ensure reproducible results."
        ),
        tags=["demo", "asap7", "sta-first", "reproducible"],
    )

    # Validate configuration before returning
    study.validate()

    return study


def create_nangate45_extreme_demo_study(
    snapshot_path: str | None = None,
    safety_domain: SafetyDomain = SafetyDomain.GUARDED,
) -> StudyConfig:
    """Create an 'extreme' broken design demo Study for Nangate45.

    This creates a demo Study designed to showcase Noodle 2's ability to
    fix extremely broken designs with:
    - Starting WNS ~ -2000ps (very negative slack)
    - Starting hot_ratio > 0.3 (severe congestion)
    - Auto-diagnosis to identify bottlenecks
    - Multi-stage ECO application to systematically fix the design
    - Complete visualization suite showing before/after comparison

    The demo generates complete artifacts including:
    - before/ directory with initial metrics and visualizations
    - after/ directory with final improved metrics
    - comparison/ directory with differential heatmaps
    - stage-by-stage progression tracking
    - Pareto frontier evolution

    Args:
        snapshot_path: Path to Nangate45 extreme design snapshot.
                      If None, uses default 'studies/nangate45_extreme'
        safety_domain: Safety domain for the Study (default: GUARDED)

    Returns:
        StudyConfig: Extreme demo Study configuration

    Example:
        >>> demo = create_nangate45_extreme_demo_study()
        >>> demo.validate()
        >>> # Execute to demonstrate fixing extremely broken design
    """
    if snapshot_path is None:
        # Default to studies/nangate45_extreme relative to project root
        # (uses extreme snapshot with timing violations and high congestion)
        snapshot_path = str(Path("studies") / "nangate45_extreme")

    # Stage 0: Aggressive exploration to find any improvements
    # Start with topology-neutral ECOs which are safest
    stage_0 = StageConfig(
        name="aggressive_exploration",
        execution_mode=ExecutionMode.STA_CONGESTION,  # Need both metrics
        trial_budget=15,  # More trials needed for extreme case
        survivor_count=4,  # Keep more survivors initially
        allowed_eco_classes=[
            ECOClass.TOPOLOGY_NEUTRAL,
        ],
        abort_threshold_wns_ps=-150000,  # -150ns - very permissive
        visualization_enabled=True,
        timeout_seconds=600,  # 10 minutes per trial
    )

    # Stage 1: Refinement with placement-affecting ECOs
    stage_1 = StageConfig(
        name="placement_refinement",
        execution_mode=ExecutionMode.STA_CONGESTION,
        trial_budget=10,
        survivor_count=3,
        allowed_eco_classes=[
            ECOClass.TOPOLOGY_NEUTRAL,
            ECOClass.PLACEMENT_LOCAL,
        ],
        abort_threshold_wns_ps=-200000,  # -200ns
        visualization_enabled=True,
        timeout_seconds=900,  # 15 minutes per trial
    )

    # Stage 2: Final closure with all available ECOs
    stage_2 = StageConfig(
        name="aggressive_closure",
        execution_mode=ExecutionMode.STA_CONGESTION,
        trial_budget=8,
        survivor_count=2,
        allowed_eco_classes=[
            ECOClass.TOPOLOGY_NEUTRAL,
            ECOClass.PLACEMENT_LOCAL,
            ECOClass.ROUTING_AFFECTING,
        ],
        abort_threshold_wns_ps=None,  # No abort in final stage
        visualization_enabled=True,
        timeout_seconds=1200,  # 20 minutes per trial
    )

    # Create the complete Study configuration
    study = StudyConfig(
        name="nangate45_extreme_demo",
        safety_domain=safety_domain,
        base_case_name="nangate45_extreme",
        pdk="Nangate45",
        stages=[stage_0, stage_1, stage_2],
        snapshot_path=snapshot_path,
        metadata={
            "purpose": "Demonstrate fixing extremely broken Nangate45 design",
            "design": "AES or similar complex design with severe timing/congestion issues",
            "expected_behavior": "Improve WNS by >50%, reduce hot_ratio from >0.3 to <0.12",
            "version": "1.0.0",
            "initial_state": {
                "wns_ps_range": [-3000, -2000],
                "hot_ratio_range": [0.30, 0.45],
            },
            "target_improvements": {
                "wns_improvement_percent": 50,
                "hot_ratio_target": 0.12,
            },
        },
        author="Noodle2 Team",
        description=(
            "Extreme broken design demo Study for Nangate45. Showcases Noodle 2's "
            "ability to systematically fix a design with severe timing violations "
            "(WNS ~ -2000ps) and congestion issues (hot_ratio > 0.3) through "
            "multi-stage ECO application, auto-diagnosis, and comprehensive "
            "before/after visualizations."
        ),
        tags=["demo", "nangate45", "extreme", "before-after", "visualization"],
    )

    # Validate configuration before returning
    study.validate()

    return study


def create_asap7_extreme_demo_study(
    snapshot_path: str | None = None,
    safety_domain: SafetyDomain = SafetyDomain.GUARDED,
) -> StudyConfig:
    """Create an 'extreme' broken design demo Study for ASAP7.

    This creates a demo Study designed to showcase Noodle 2's ability to
    fix extremely broken ASAP7 designs with:
    - Starting WNS ~ -3000ps (very negative slack, worse than Nangate45)
    - Starting hot_ratio > 0.4 (severe congestion due to advanced node)
    - ASAP7-specific workarounds automatically applied
    - STA-first staging for stability
    - Auto-diagnosis to identify bottlenecks
    - Multi-stage ECO application to systematically fix the design

    ASAP7-Specific Considerations:
    - Uses STA-first staging (stages start with STA_ONLY or STA_CONGESTION)
    - Lower utilization (0.55) to prevent routing explosion
    - All ASAP7 workarounds automatically applied by tcl_generator
    - Higher initial trial budget due to advanced node complexity

    Args:
        snapshot_path: Path to ASAP7 extreme design snapshot.
                      If None, uses default 'studies/asap7_extreme'
        safety_domain: Safety domain for the Study (default: GUARDED)

    Returns:
        StudyConfig: ASAP7 extreme demo Study configuration

    Example:
        >>> demo = create_asap7_extreme_demo_study()
        >>> demo.validate()
        >>> # STA-first staging is used for ASAP7
        >>> assert demo.stages[0].execution_mode in [ExecutionMode.STA_ONLY, ExecutionMode.STA_CONGESTION]
    """
    if snapshot_path is None:
        # Default to studies/asap7_extreme relative to project root
        # (uses extreme snapshot with timing violations for 7nm)
        snapshot_path = str(Path("studies") / "asap7_extreme")

    # Stage 0: STA-first exploration (ASAP7 best practice)
    # Use STA_CONGESTION instead of pure STA_ONLY to track both metrics
    # but rely on STA-first staging philosophy
    stage_0 = StageConfig(
        name="sta_exploration",
        execution_mode=ExecutionMode.STA_CONGESTION,  # Track both, STA-priority
        trial_budget=12,  # More trials for ASAP7 complexity
        survivor_count=4,
        allowed_eco_classes=[
            ECOClass.TOPOLOGY_NEUTRAL,
        ],
        abort_threshold_wns_ps=-200000,  # -200ns - very permissive for extreme case
        visualization_enabled=True,
        timeout_seconds=900,  # 15 minutes per trial (ASAP7 is slower)
    )

    # Stage 1: Timing-focused refinement
    stage_1 = StageConfig(
        name="timing_refinement",
        execution_mode=ExecutionMode.STA_CONGESTION,
        trial_budget=8,
        survivor_count=3,
        allowed_eco_classes=[
            ECOClass.TOPOLOGY_NEUTRAL,
            ECOClass.PLACEMENT_LOCAL,
        ],
        abort_threshold_wns_ps=-250000,  # -250ns
        visualization_enabled=True,
        timeout_seconds=1200,  # 20 minutes per trial
    )

    # Stage 2: Final closure with careful routing consideration
    stage_2 = StageConfig(
        name="careful_closure",
        execution_mode=ExecutionMode.STA_CONGESTION,
        trial_budget=6,
        survivor_count=2,
        allowed_eco_classes=[
            ECOClass.TOPOLOGY_NEUTRAL,
            ECOClass.PLACEMENT_LOCAL,
            ECOClass.ROUTING_AFFECTING,
        ],
        abort_threshold_wns_ps=None,  # No abort in final stage
        visualization_enabled=True,
        timeout_seconds=1800,  # 30 minutes per trial (ASAP7 routing is complex)
    )

    # Create the complete Study configuration
    study = StudyConfig(
        name="asap7_extreme_demo",
        safety_domain=safety_domain,
        base_case_name="asap7_extreme",
        pdk="ASAP7",  # Triggers ASAP7-specific workarounds
        stages=[stage_0, stage_1, stage_2],
        snapshot_path=snapshot_path,
        metadata={
            "purpose": "Demonstrate fixing extremely broken ASAP7 design with STA-first staging",
            "design": "AES or similar complex design with severe advanced-node issues",
            "expected_behavior": "Improve WNS by >40%, reduce hot_ratio from >0.4 to <0.15",
            "version": "1.0.0",
            "asap7_workarounds": [
                "routing_layer_constraints",
                "site_specification",
                "pin_placement_constraints",
                "low_utilization_0.55",
            ],
            "staging_strategy": "STA-first for ASAP7 stability",
            "initial_state": {
                "wns_ps_range": [-3500, -2500],
                "hot_ratio_range": [0.40, 0.55],
            },
            "target_improvements": {
                "wns_improvement_percent": 40,
                "hot_ratio_target": 0.15,
            },
        },
        author="Noodle2 Team",
        description=(
            "Extreme broken design demo Study for ASAP7 PDK. Showcases Noodle 2's "
            "ability to systematically fix an advanced-node design with severe timing "
            "violations (WNS ~ -3000ps) and congestion issues (hot_ratio > 0.4) through "
            "STA-first staging, ASAP7-specific workarounds, and multi-stage ECO "
            "application. Demonstrates ASAP7 best practices: low utilization (0.55), "
            "timing-priority staging, and explicit routing/pin constraints."
        ),
        tags=["demo", "asap7", "extreme", "sta-first", "advanced-node"],
    )

    # Validate configuration before returning
    study.validate()

    return study


def create_sky130_extreme_demo_study(
    snapshot_path: str | None = None,
    safety_domain: SafetyDomain = SafetyDomain.GUARDED,
) -> StudyConfig:
    """Create an 'extreme' broken design demo Study for Sky130.

    This creates a demo Study designed to showcase Noodle 2's ability to
    fix extremely broken Sky130 designs with:
    - Production-realistic Ibex RISC-V core design
    - Starting WNS ~ -2200ps (severe timing violation)
    - Starting hot_ratio > 0.32 (severe congestion)
    - Complete audit trail for manufacturing
    - Publication-quality visualizations
    - Approval gate simulation
    - Multi-stage ECO application to systematically fix the design

    Sky130-Specific Considerations:
    - Uses production-realistic Ibex design (not synthetic)
    - Provides complete audit trail for manufacturing approval
    - Generates publication-quality differential visualizations
    - Simulates approval gate workflow
    - Uses open-source Sky130 PDK (sky130_fd_sc_hd)

    Args:
        snapshot_path: Path to Sky130 extreme design snapshot.
                      If None, uses default 'studies/sky130_extreme'
        safety_domain: Safety domain for the Study (default: GUARDED)

    Returns:
        StudyConfig: Sky130 extreme demo Study configuration

    Example:
        >>> demo = create_sky130_extreme_demo_study()
        >>> demo.validate()
        >>> # Production-realistic Ibex design
        >>> assert demo.metadata["design"] == "Ibex RISC-V Core"
    """
    if snapshot_path is None:
        # Default to studies/sky130_extreme relative to project root
        # (uses extreme snapshot with timing violations for 130nm)
        snapshot_path = str(Path("studies") / "sky130_extreme")

    # Stage 0: Aggressive exploration
    stage_0 = StageConfig(
        name="aggressive_exploration",
        execution_mode=ExecutionMode.STA_CONGESTION,
        trial_budget=14,  # Moderate trial budget for production design
        survivor_count=4,
        allowed_eco_classes=[
            ECOClass.TOPOLOGY_NEUTRAL,
        ],
        abort_threshold_wns_ps=-150000,  # -150ns - permissive for extreme case
        visualization_enabled=True,
        timeout_seconds=800,  # ~13 minutes per trial
    )

    # Stage 1: Placement refinement
    stage_1 = StageConfig(
        name="placement_refinement",
        execution_mode=ExecutionMode.STA_CONGESTION,
        trial_budget=10,
        survivor_count=3,
        allowed_eco_classes=[
            ECOClass.TOPOLOGY_NEUTRAL,
            ECOClass.PLACEMENT_LOCAL,
        ],
        abort_threshold_wns_ps=-200000,  # -200ns
        visualization_enabled=True,
        timeout_seconds=1000,  # ~17 minutes per trial
    )

    # Stage 2: Final closure
    stage_2 = StageConfig(
        name="final_closure",
        execution_mode=ExecutionMode.STA_CONGESTION,
        trial_budget=7,
        survivor_count=2,
        allowed_eco_classes=[
            ECOClass.TOPOLOGY_NEUTRAL,
            ECOClass.PLACEMENT_LOCAL,
            ECOClass.ROUTING_AFFECTING,
        ],
        abort_threshold_wns_ps=None,  # No abort in final stage
        visualization_enabled=True,
        timeout_seconds=1500,  # 25 minutes per trial
    )

    # Create the complete Study configuration
    study = StudyConfig(
        name="sky130_extreme_demo",
        safety_domain=safety_domain,
        base_case_name="sky130_extreme",
        pdk="Sky130",
        stages=[stage_0, stage_1, stage_2],
        snapshot_path=snapshot_path,
        metadata={
            "purpose": "Demonstrate fixing extremely broken Sky130 design with production-realistic workflow",
            "design": "Ibex RISC-V Core",
            "design_type": "production_realistic",
            "expected_behavior": "Improve WNS by >50%, reduce hot_ratio from >0.32 to <0.13",
            "version": "1.0.0",
            "sky130_features": [
                "pdk_variant: sky130A",
                "std_cell_library: sky130_fd_sc_hd",
                "open_source_pdk: true",
                "production_realistic_ibex_design",
                "complete_audit_trail",
                "approval_gate_simulation",
                "publication_quality_visualizations",
            ],
            "success_criteria": {
                "wns_improvement_percent": 50,
                "hot_ratio_reduction_percent": 60,
                "audit_trail_complete": True,
                "approval_gate_passed": True,
            },
        },
        author="Noodle2 Team",
        description=(
            "Extreme broken design demo Study for Sky130 PDK with production-realistic "
            "Ibex RISC-V core. Showcases Noodle 2's ability to systematically fix a "
            "design with severe timing violations (WNS ~ -2200ps) and congestion issues "
            "(hot_ratio > 0.32) through multi-stage ECO application. Demonstrates "
            "production-realistic features: complete audit trail, approval gate simulation, "
            "and publication-quality visualizations. Uses open-source Sky130 PDK "
            "(sky130_fd_sc_hd) suitable for manufacturing."
        ),
        tags=["demo", "sky130", "extreme", "production-realistic", "ibex", "audit-trail"],
    )

    # Validate configuration before returning
    study.validate()

    return study


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
