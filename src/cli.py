#!/usr/bin/env python3
"""
Noodle 2 — Safety-aware, policy-driven orchestration for OpenROAD experiments.

Main command-line interface for managing Studies, executing trials, and
analyzing results.
"""

import sys
import argparse
from pathlib import Path
from typing import Optional

# Version info
__version__ = "0.1.0"


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser with helpful usage messages."""
    parser = argparse.ArgumentParser(
        prog="noodle2",
        description="""
╔═══════════════════════════════════════════════════════════════════╗
║                        Noodle 2 v{version}                        ║
║   Safety-aware, policy-driven orchestration for OpenROAD         ║
╚═══════════════════════════════════════════════════════════════════╝

Noodle 2 manages uncertainty, failure, and limited compute budgets
while exploring Engineering Change Orders (ECOs) across complex,
multi-stage physical design workflows.

What Noodle 2 Does:
  • Orchestrates OpenROAD/OpenSTA trials with safety constraints
  • Manages Studies with multiple stages and Cases
  • Enforces safety domains and ECO class policies
  • Tracks telemetry, lineage, and provenance
  • Integrates with Ray for distributed execution
  • Provides rich visualizations and reports
        """.format(version=__version__),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run a Study from configuration file
  noodle2 run --study studies/nangate45_baseline.yaml

  # Validate Study configuration
  noodle2 validate --study studies/asap7_exploration.yaml

  # List all Studies
  noodle2 list-studies

  # Show Study results
  noodle2 show --study nangate45_baseline

  # Export Study results to CSV/JSON
  noodle2 export --study nangate45_baseline --format csv

  # Check progress on feature implementation
  noodle2 progress --detailed

For more help on a specific command:
  noodle2 <command> --help
        """,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"noodle2 {__version__}",
    )

    # Create subcommands
    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands",
        metavar="<command>",
    )

    # === RUN command ===
    run_parser = subparsers.add_parser(
        "run",
        help="Execute a Study",
        description="""
Execute a complete Study from configuration file.

This will:
  1. Load Study configuration and validate safety domain
  2. Verify base case is structurally runnable
  3. Execute trials across all stages with Ray
  4. Apply safety gates and survivor selection
  5. Generate telemetry, artifacts, and reports
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    run_parser.add_argument(
        "--study",
        type=Path,
        required=True,
        help="Path to Study configuration YAML file",
    )
    run_parser.add_argument(
        "--ray-address",
        type=str,
        default="auto",
        help="Ray cluster address (default: auto, starts local)",
    )
    run_parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        help="Directory for checkpoint files (enables resume)",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without executing trials",
    )

    # === RESUME command ===
    resume_parser = subparsers.add_parser(
        "resume",
        help="Resume a Study from checkpoint",
        description="""
Resume execution of an interrupted Study from a checkpoint.

This will:
  1. Locate checkpoint file (latest or specified path)
  2. Validate checkpoint integrity and resumption safety
  3. Skip already-completed stages
  4. Resume execution from next incomplete stage
  5. Preserve all previous results and telemetry

By default, resumes from the latest checkpoint. Use --checkpoint
to resume from a specific checkpoint file (useful for re-running
from an earlier stage with different parameters).
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    resume_parser.add_argument(
        "--study",
        type=str,
        required=True,
        help="Study name or path to Study artifact directory",
    )
    resume_parser.add_argument(
        "--checkpoint",
        type=Path,
        help="Specific checkpoint file to resume from (default: latest)",
    )
    resume_parser.add_argument(
        "--ray-address",
        type=str,
        default="auto",
        help="Ray cluster address (default: auto, starts local)",
    )

    # === VALIDATE command ===
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate Study configuration",
        description="""
Validate Study configuration and produce Run Legality Report.

Checks:
  • Safety domain and ECO class compatibility
  • Stage configuration and budget constraints
  • Base case snapshot availability
  • PDK references and tool paths
  • Policy and rail configuration

Exits with code 0 if valid, non-zero if errors found.
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    validate_parser.add_argument(
        "--study",
        type=Path,
        required=True,
        help="Path to Study configuration YAML file",
    )
    validate_parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )

    # === LIST-STUDIES command ===
    list_parser = subparsers.add_parser(
        "list-studies",
        aliases=["ls"],
        help="List all Studies",
        description="""
Display catalog of all Studies with status and metadata.

Shows:
  • Study name and description
  • Safety domain
  • Creation date
  • Status (running, completed, failed, blocked)
  • Completion percentage
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    list_parser.add_argument(
        "--status",
        choices=["all", "running", "completed", "failed", "blocked"],
        default="all",
        help="Filter by Study status",
    )
    list_parser.add_argument(
        "--domain",
        choices=["all", "sandbox", "guarded", "locked"],
        default="all",
        help="Filter by safety domain",
    )

    # === SHOW command ===
    show_parser = subparsers.add_parser(
        "show",
        help="Show Study details and results",
        description="""
Display detailed information about a Study.

Includes:
  • Study configuration and metadata
  • Stage summaries with pass rates
  • Case lineage DAG
  • Top ECOs by effectiveness
  • Winner Case metrics
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    show_parser.add_argument(
        "--study",
        type=str,
        required=True,
        help="Study name or path to Study directory",
    )
    show_parser.add_argument(
        "--stage",
        type=int,
        help="Show specific stage details (default: all)",
    )
    show_parser.add_argument(
        "--case",
        type=str,
        help="Show specific Case details",
    )

    # === EXPORT command ===
    export_parser = subparsers.add_parser(
        "export",
        help="Export Study results",
        description="""
Export Study results for external analysis.

Formats:
  • JSON: Full structured data with nested objects
  • CSV: Flattened tabular format for spreadsheets
  • Both: Generate both JSON and CSV

Output includes:
  • Study configuration
  • All Case metrics and rankings
  • Case lineage DAG
  • Stage summaries
  • Export metadata
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    export_parser.add_argument(
        "--study",
        type=str,
        required=True,
        help="Study name or path",
    )
    export_parser.add_argument(
        "--format",
        choices=["json", "csv", "both"],
        default="both",
        help="Export format (default: both)",
    )
    export_parser.add_argument(
        "--output",
        type=Path,
        help="Output directory (default: Study artifacts)",
    )

    # === PROGRESS command ===
    progress_parser = subparsers.add_parser(
        "progress",
        help="Show feature implementation progress",
        description="""
Display progress report on Noodle 2 feature implementation.

Shows:
  • Overall completion percentage
  • Breakdown by category (functional, style, integration)
  • Recently completed features
  • Remaining work
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    progress_parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed per-feature breakdown",
    )
    progress_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    # === INIT command ===
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a new Study",
        description="""
Create a new Study configuration from template.

Generates:
  • Study configuration YAML
  • Artifact directory structure
  • README with navigation guide
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    init_parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="Study name (used for directory and artifacts)",
    )
    init_parser.add_argument(
        "--pdk",
        choices=["nangate45", "asap7", "sky130"],
        required=True,
        help="Target PDK/technology",
    )
    init_parser.add_argument(
        "--domain",
        choices=["sandbox", "guarded", "locked"],
        default="sandbox",
        help="Safety domain (default: sandbox)",
    )
    init_parser.add_argument(
        "--output",
        type=Path,
        help="Output directory (default: studies/<name>)",
    )

    # === REPLAY command ===
    replay_parser = subparsers.add_parser(
        "replay",
        help="Replay a specific trial with verbose output",
        description="""
Re-execute a specific trial from a completed Study.

This command:
  • Loads trial configuration from telemetry
  • Re-executes the trial with same parameters
  • Shows verbose execution details
  • Does not modify Study state
  • Useful for debugging and verification

The trial is executed in isolation and does not affect
the original Study's state or telemetry.
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    replay_parser.add_argument(
        "--case",
        type=str,
        required=True,
        help="Case name to replay (e.g., nangate45_1_5)",
    )
    replay_parser.add_argument(
        "--trial",
        type=int,
        help="Specific trial index to replay (default: first trial)",
    )
    replay_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed execution steps and logging",
    )
    replay_parser.add_argument(
        "--output",
        type=Path,
        help="Output directory for replay artifacts (default: replay_output)",
    )
    replay_parser.add_argument(
        "--eco",
        type=str,
        help="ECO class to apply (overrides original)",
    )
    replay_parser.add_argument(
        "--param",
        type=str,
        action="append",
        dest="params",
        metavar="KEY=VALUE",
        help="ECO parameter override (can be used multiple times, e.g., --param size=1.8)",
    )

    # === DEBUG command ===
    debug_parser = subparsers.add_parser(
        "debug",
        help="Generate detailed debug report for specific trial",
        description="""
Generate comprehensive debug report for a specific trial.

This command creates a detailed debug report including:
  • execution_trace.json - Step-by-step execution log
  • tcl_commands.log - Exact TCL commands sent to OpenROAD
  • openroad_stdout.log - OpenROAD stdout capture
  • openroad_stderr.log - OpenROAD stderr capture
  • metrics_before.json - Metrics before ECO application
  • metrics_after.json - Metrics after ECO application
  • diagnosis_at_execution.json - Diagnosis results
  • eco_parameters_used.json - Detailed ECO parameters
  • all_heatmaps/ - Full visualization set

This is useful for:
  • Debugging trial failures
  • Understanding ECO behavior
  • Analyzing timing and congestion issues
  • Generating reports for documentation
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    debug_parser.add_argument(
        "--case",
        type=str,
        required=True,
        help="Case name to debug (e.g., nangate45_1_5)",
    )
    debug_parser.add_argument(
        "--trial",
        type=int,
        help="Specific trial index to debug (default: first trial)",
    )
    debug_parser.add_argument(
        "--output",
        type=Path,
        help="Output directory for debug report (default: debug_report/)",
    )
    debug_parser.add_argument(
        "--no-heatmaps",
        action="store_true",
        help="Skip heatmap generation to reduce output size",
    )

    # === COMPARE command ===
    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare two studies and generate comparison report",
        description="""
Compare two completed Studies and generate comparison report.

This command:
  • Loads final metrics from both Studies
  • Compares key metrics (WNS, TNS, hot_ratio, power)
  • Calculates deltas and percent changes
  • Shows direction indicators (▲ for improvement, ▼ for regression)
  • Determines overall improvement/regression

The comparison helps evaluate:
  • Impact of ECO strategy changes
  • Effect of parameter tuning
  • Progress between iterations
  • A/B testing of different approaches
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    compare_parser.add_argument(
        "--study1",
        type=str,
        required=True,
        help="First Study name for comparison",
    )
    compare_parser.add_argument(
        "--study2",
        type=str,
        required=True,
        help="Second Study name for comparison",
    )
    compare_parser.add_argument(
        "--output",
        type=Path,
        help="Output file for comparison report (default: stdout)",
    )
    compare_parser.add_argument(
        "--format",
        choices=["text", "json", "both"],
        default="text",
        help="Output format (default: text)",
    )

    # === SHOW-PRIORS command ===
    show_priors_parser = subparsers.add_parser(
        "show-priors",
        help="Inspect warm-start priors before study execution",
        description="""
Inspect ECO priors that will be loaded for warm-start execution.

This command displays:
  • Source study provenance (where priors came from)
  • ECO effectiveness data for each ECO
  • Weights and confidence scores
  • Total applications and success rates
  • WNS improvement statistics

This allows operators to review the priors before committing
to a study execution, ensuring they understand what historical
data will be used to guide ECO selection.
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    show_priors_parser.add_argument(
        "--study",
        type=str,
        required=True,
        help="Study name or path to Study configuration",
    )
    show_priors_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    show_priors_parser.add_argument(
        "--eco",
        type=str,
        help="Show details for a specific ECO only",
    )

    return parser


def cmd_run(args: argparse.Namespace) -> int:
    """Execute run command."""
    from src.controller.study import load_study_config
    from src.controller.executor import StudyExecutor

    study_path = Path(args.study)

    # If study is just a name, look for it in studies/ directory
    if not study_path.exists() and not str(study_path).endswith(('.yaml', '.yml')):
        study_path = Path('studies') / f"{args.study}.yaml"

    if not study_path.exists():
        print(f"❌ Error: Study configuration not found: {study_path}")
        return 1

    print(f"🚀 Running Study: {study_path}")
    print(f"   Ray address: {args.ray_address}")
    if args.checkpoint_dir:
        print(f"   Checkpoints: {args.checkpoint_dir}")
    if args.dry_run:
        print("   Dry run: validation only")
    print()

    try:
        # Load configuration
        print("📋 Loading configuration...")
        config = load_study_config(study_path)
        print(f"   Study name: {config.name}")
        print(f"   PDK: {config.pdk}")
        print(f"   Safety domain: {config.safety_domain}")
        print(f"   Stages: {len(config.stages)}")
        print()

        if args.dry_run:
            print("✅ Configuration is valid (dry run)")
            return 0

        # Initialize executor
        print("⚙️  Initializing executor...")
        executor = StudyExecutor(
            config=config,
            artifacts_root="artifacts",
            telemetry_root="telemetry",
            use_ray=False,  # For now, use sequential execution
        )

        # Execute study
        print("🏃 Executing study...")
        print()
        result = executor.execute()

        # Print results
        print()
        print("=" * 70)
        print("✅ Study execution complete!")
        print(f"   Total stages: {result.total_stages}")
        print(f"   Stages completed: {result.stages_completed}")
        print(f"   Total runtime: {result.total_runtime_seconds:.2f}s")
        print(f"   Final survivors: {len(result.final_survivors)}")
        if result.aborted:
            print(f"   ⚠️  Aborted: {result.abort_reason}")
        print("=" * 70)

        return 0 if not result.aborted else 1

    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return 1
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        return 1
    except Exception as e:
        print(f"❌ Execution failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_resume(args: argparse.Namespace) -> int:
    """Execute resume command to continue interrupted Study from checkpoint."""
    from src.controller.study_resumption import load_checkpoint, find_checkpoint, validate_resumption
    from src.controller.study import load_study_config
    from src.controller.executor import StudyExecutor

    print("🔄 Resuming Study from checkpoint")
    print(f"   Study: {args.study}")
    print()

    try:
        # Resolve study path
        study_path = Path(args.study)

        # Check if it's an artifact directory or a study name
        if study_path.is_dir():
            artifact_dir = study_path
        elif (Path("artifacts") / args.study).is_dir():
            artifact_dir = Path("artifacts") / args.study
        else:
            print(f"❌ Error: Study artifact directory not found: {args.study}")
            print()
            print("Tip: Provide either:")
            print("  • Study name (e.g., 'nangate45_baseline')")
            print("  • Path to Study artifact directory (e.g., 'artifacts/nangate45_baseline')")
            return 1

        # Find checkpoint file
        if args.checkpoint:
            checkpoint_path = args.checkpoint
            if not checkpoint_path.exists():
                print(f"❌ Error: Checkpoint file not found: {checkpoint_path}")
                return 1
            print(f"   Checkpoint: {checkpoint_path}")
        else:
            checkpoint_path = find_checkpoint(artifact_dir)
            if checkpoint_path is None:
                print(f"❌ Error: No checkpoint found in {artifact_dir}")
                print()
                print("Tip: Create checkpoint during study execution with --checkpoint-dir")
                return 1
            print(f"   Checkpoint: {checkpoint_path} (latest)")

        print()

        # Load checkpoint
        print("📋 Loading checkpoint...")
        checkpoint = load_checkpoint(checkpoint_path)
        print(f"   Study name: {checkpoint.study_name}")
        print(f"   Last completed stage: {checkpoint.last_completed_stage_index}")
        print(f"   Completed stages: {len(checkpoint.completed_stages)}")
        print(f"   Next stage: {checkpoint.get_next_stage_index()}")
        print()

        # Load study configuration
        # Try to find study config YAML in the artifact directory or studies/
        study_config_path = None
        possible_paths = [
            artifact_dir / f"{checkpoint.study_name}.yaml",
            artifact_dir.parent / f"{checkpoint.study_name}.yaml",
            Path("studies") / f"{checkpoint.study_name}.yaml",
        ]

        for path in possible_paths:
            if path.exists():
                study_config_path = path
                break

        if study_config_path is None:
            print(f"❌ Error: Study configuration not found for {checkpoint.study_name}")
            print()
            print("Searched locations:")
            for path in possible_paths:
                print(f"  • {path}")
            return 1

        print("📋 Loading study configuration...")
        config = load_study_config(study_config_path)
        print(f"   PDK: {config.pdk}")
        print(f"   Safety domain: {config.safety_domain}")
        print(f"   Total stages: {len(config.stages)}")
        print()

        # Validate resumption is safe
        print("🔍 Validating resumption...")
        is_valid, issues = validate_resumption(checkpoint, len(config.stages))

        if not is_valid:
            print("❌ Resumption validation failed:")
            for issue in issues:
                print(f"   • {issue}")
            return 1

        print("   ✅ Resumption is safe")
        print()

        # Initialize executor with checkpoint
        print("⚙️  Initializing executor...")
        executor = StudyExecutor(
            config=config,
            artifacts_root="artifacts",
            telemetry_root="telemetry",
            use_ray=False,
            checkpoint=checkpoint,  # Pass checkpoint to executor
        )

        # Resume execution
        print("🏃 Resuming study execution...")
        print(f"   Skipping stages 0-{checkpoint.last_completed_stage_index}")
        print(f"   Starting from stage {checkpoint.get_next_stage_index()}")
        print()

        result = executor.execute()

        # Print results
        print()
        print("=" * 70)
        print("✅ Study resumption complete!")
        print(f"   Total stages: {result.total_stages}")
        print(f"   Stages completed: {result.stages_completed}")
        print(f"   Total runtime: {result.total_runtime_seconds:.2f}s")
        print(f"   Final survivors: {len(result.final_survivors)}")
        if result.aborted:
            print(f"   ⚠️  Aborted: {result.abort_reason}")
        print("=" * 70)

        return 0 if not result.aborted else 1

    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return 1
    except ValueError as e:
        print(f"❌ Validation error: {e}")
        return 1
    except Exception as e:
        print(f"❌ Resumption failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_validate(args: argparse.Namespace) -> int:
    """Execute validate command."""
    print(f"✓ Validating Study: {args.study}")
    if args.strict:
        print("  Using strict mode (warnings = errors)")
    print()
    print("Error: Study validation not yet implemented.")
    print("This is a placeholder for configuration validation.")
    return 1


def cmd_list_studies(args: argparse.Namespace) -> int:
    """Execute list-studies command."""
    from src.controller.study_list import discover_studies, filter_studies, format_study_table

    print("📋 Study Catalog")
    print()

    # Discover all Studies
    all_studies = discover_studies()

    if not all_studies:
        print("No Studies found in telemetry directory.")
        print()
        print("Tip: Run 'noodle2 init --name <name> --pdk <pdk>' to create a new Study.")
        return 0

    # Apply filters
    filtered = filter_studies(all_studies, status=args.status, domain=args.domain)

    if not filtered:
        print(f"No Studies match filters (status={args.status}, domain={args.domain})")
        return 0

    # Display filters if active
    if args.status != "all" or args.domain != "all":
        print(f"Filters: status={args.status}, domain={args.domain}")
        print()

    # Format and display table
    table = format_study_table(filtered)
    print(table)

    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Execute show command."""
    print(f"📊 Study Details: {args.study}")
    if args.stage is not None:
        print(f"   Showing stage: {args.stage}")
    if args.case:
        print(f"   Showing case: {args.case}")
    print()
    print("Error: Study show not yet implemented.")
    print("This is a placeholder for Study details display.")
    return 1


def cmd_export(args: argparse.Namespace) -> int:
    """Execute export command."""
    print(f"📤 Exporting Study: {args.study}")
    print(f"   Format: {args.format}")
    if args.output:
        print(f"   Output: {args.output}")
    print()
    print("Error: Study export not yet implemented.")
    print("This is a placeholder. Use src.telemetry.study_export module directly.")
    return 1


def cmd_progress(args: argparse.Namespace) -> int:
    """Execute progress command."""
    from .tracking.cli import main as tracking_main
    # Delegate to existing tracking CLI
    sys.argv = ["tracking"]
    if args.detailed:
        sys.argv.append("--detailed")
    if args.json:
        sys.argv.append("--json")
    return tracking_main()


def cmd_init(args: argparse.Namespace) -> int:
    """Execute init command."""
    print(f"🔧 Initializing Study: {args.name}")
    print(f"   PDK: {args.pdk}")
    print(f"   Domain: {args.domain}")
    if args.output:
        print(f"   Output: {args.output}")
    print()
    print("Error: Study initialization not yet implemented.")
    print("This is a placeholder for Study template generation.")
    return 1


def cmd_replay(args: argparse.Namespace) -> int:
    """Execute replay command."""
    from src.replay.trial_replay import replay_trial, ReplayConfig

    print(f"🔄 Replaying Trial from Case: {args.case}")
    if args.trial is not None:
        print(f"   Trial index: {args.trial}")
    if args.verbose:
        print(f"   Verbose: enabled")
    if args.output:
        print(f"   Output: {args.output}")
    if args.eco:
        print(f"   ECO override: {args.eco}")
    if args.params:
        print(f"   Parameter overrides: {args.params}")
    print()

    # Parse parameter overrides
    param_overrides = {}
    if args.params:
        for param in args.params:
            if "=" not in param:
                print(f"❌ Invalid parameter format: {param}")
                print("   Expected format: KEY=VALUE")
                return 1
            key, value = param.split("=", 1)
            # Try to convert to number if possible
            try:
                value = float(value)
            except ValueError:
                pass  # Keep as string
            param_overrides[key] = value

    # Create replay configuration
    config = ReplayConfig(
        case_name=args.case,
        trial_index=args.trial,
        verbose=args.verbose,
        output_dir=args.output or Path("replay_output"),
        eco_override=args.eco,
        param_overrides=param_overrides,
    )

    try:
        result = replay_trial(config)
        if result.success:
            print()
            print("✅ Replay completed successfully")
            print(f"   Runtime: {result.runtime_seconds:.2f}s")
            print(f"   Output: {result.output_dir}")
            if result.param_changes:
                print(f"   Parameter changes applied:")
                for key, (old, new) in result.param_changes.items():
                    print(f"     {key}: {old} → {new}")
            return 0
        else:
            print()
            print("❌ Replay failed")
            print(f"   Return code: {result.return_code}")
            if result.error_message:
                print(f"   Error: {result.error_message}")
            return 1
    except Exception as e:
        print(f"❌ Error during replay: {e}")
        import traceback
        if args.verbose:
            traceback.print_exc()
        return 1


def cmd_debug(args: argparse.Namespace) -> int:
    """Execute debug command."""
    from src.replay.debug_report import generate_debug_report, DebugReportConfig

    print(f"🔍 Generating Debug Report for Case: {args.case}")
    if args.trial is not None:
        print(f"   Trial index: {args.trial}")
    if args.output:
        print(f"   Output: {args.output}")
    if args.no_heatmaps:
        print(f"   Heatmaps: disabled")
    print()

    # Create debug report configuration
    config = DebugReportConfig(
        case_name=args.case,
        trial_index=args.trial,
        output_dir=args.output or Path("debug_report"),
        include_heatmaps=not args.no_heatmaps,
    )

    try:
        result = generate_debug_report(config)
        if result.success:
            print()
            print("✅ Debug report generated successfully")
            print(f"   Output directory: {result.output_dir}")
            print(f"   Files generated: {len(result.files_generated)}")
            print()
            print("   Generated files:")
            for file_path in result.files_generated:
                print(f"     • {file_path}")
            print()
            print("Tip: Review the execution_trace.json for step-by-step execution details")
            return 0
        else:
            print()
            print("❌ Debug report generation failed")
            if result.error_message:
                print(f"   Error: {result.error_message}")
            return 1
    except Exception as e:
        print(f"❌ Error during debug report generation: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_compare(args: argparse.Namespace) -> int:
    """Execute compare command."""
    from src.controller.study_comparison import (
        compare_studies,
        format_comparison_report,
        write_comparison_report,
    )

    print(f"📊 Comparing Studies: {args.study1} vs {args.study2}")
    print()

    try:
        # Generate comparison report
        report = compare_studies(args.study1, args.study2)

        # Format and display/save report
        if args.format in ["text", "both"]:
            formatted_report = format_comparison_report(report)

            if args.output and args.format == "text":
                # Write to file
                text_output = args.output
                with open(text_output, "w") as f:
                    f.write(formatted_report)
                print(f"✅ Comparison report written to: {text_output}")
                print()
            else:
                # Print to stdout
                print(formatted_report)
                print()

        if args.format in ["json", "both"]:
            # Write JSON report
            if args.output:
                json_output = (
                    args.output.with_suffix(".json")
                    if args.format == "both"
                    else args.output
                )
            else:
                json_output = Path(f"comparison_{args.study1}_vs_{args.study2}.json")

            write_comparison_report(report, json_output)
            print(f"✅ JSON comparison report written to: {json_output}")
            print()

        # Print summary
        if report.overall_improvement is not None:
            if report.overall_improvement:
                print("✅ Study 2 shows overall improvement over Study 1")
            else:
                print("⚠️  Study 2 shows regression from Study 1")
        else:
            print("ℹ️  Insufficient data for overall assessment")

        return 0

    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print()
        print("Tip: Ensure both Studies have completed and have telemetry data")
        return 1
    except Exception as e:
        print(f"❌ Error during comparison: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_show_priors(args: argparse.Namespace) -> int:
    """Execute show-priors command."""
    import json

    from src.controller.prior_sharing import PriorRepository
    from src.controller.warm_start import WarmStartConfig, WarmStartLoader

    # Only print header for text format
    if args.format != "json":
        print(f"🔍 Inspecting Warm-Start Priors: {args.study}")
        print()

    try:
        # Load study configuration to get warm-start settings
        # For now, we'll accept a direct path to a prior repository file
        # or a warm-start configuration file
        study_path = Path(args.study)

        if not study_path.exists():
            print(f"❌ Error: Study path does not exist: {study_path}")
            return 1

        # Check if it's a prior repository file (JSON)
        if study_path.suffix == ".json":
            # Load prior repository directly
            with open(study_path) as f:
                data = json.load(f)

            repository = PriorRepository.from_dict(data)

            # Display in requested format
            if args.format == "json":
                print(json.dumps(repository.to_dict(), indent=2))
                return 0

            # Text format
            print("=" * 70)
            print("PRIOR REPOSITORY")
            print("=" * 70)
            print()

            # Provenance
            if repository.provenance:
                print("Source Study Provenance:")
                print(f"  • Study ID: {repository.provenance.source_study_id}")
                print(f"  • Export Time: {repository.provenance.export_timestamp}")
                if repository.provenance.source_study_snapshot_hash:
                    print(f"  • Snapshot Hash: {repository.provenance.source_study_snapshot_hash}")
                print()

            # Summary statistics
            eco_count = len(repository.eco_priors)
            print(f"Total ECOs: {eco_count}")
            print()

            # Filter to specific ECO if requested
            if args.eco:
                if args.eco not in repository.eco_priors:
                    print(f"❌ Error: ECO '{args.eco}' not found in repository")
                    print(f"Available ECOs: {', '.join(sorted(repository.eco_priors.keys()))}")
                    return 1
                eco_list = [(args.eco, repository.eco_priors[args.eco])]
            else:
                eco_list = sorted(repository.eco_priors.items())

            # Display ECO details
            print("=" * 70)
            print("ECO EFFECTIVENESS DATA")
            print("=" * 70)
            print()

            for eco_name, effectiveness in eco_list:
                print(f"ECO: {eco_name}")
                print(f"  Prior: {effectiveness.prior.value}")
                print(f"  Total Applications: {effectiveness.total_applications}")
                print(f"  Successful: {effectiveness.successful_applications}")
                print(f"  Failed: {effectiveness.failed_applications}")

                if effectiveness.total_applications > 0:
                    success_rate = (
                        effectiveness.successful_applications
                        / effectiveness.total_applications
                        * 100
                    )
                    print(f"  Success Rate: {success_rate:.1f}%")

                print(f"  Average WNS Improvement: {effectiveness.average_wns_improvement_ps:.2f} ps")
                print(f"  Best Improvement: {effectiveness.best_wns_improvement_ps:.2f} ps")
                print(f"  Worst Degradation: {effectiveness.worst_wns_degradation_ps:.2f} ps")
                print()

            return 0

        else:
            print(f"❌ Error: Expected JSON file, got: {study_path}")
            print()
            print("Tip: Provide path to a prior repository JSON file")
            print("Example: noodle2 show-priors --study priors/nangate45_baseline.json")
            return 1

    except FileNotFoundError as e:
        print(f"❌ Error: File not found: {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON format: {e}")
        return 1
    except Exception as e:
        print(f"❌ Error during prior inspection: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main() -> int:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Handle no command (show help)
    if not args.command:
        parser.print_help()
        return 0

    # Dispatch to command handlers
    command_map = {
        "run": cmd_run,
        "resume": cmd_resume,
        "validate": cmd_validate,
        "list-studies": cmd_list_studies,
        "ls": cmd_list_studies,
        "show": cmd_show,
        "export": cmd_export,
        "progress": cmd_progress,
        "init": cmd_init,
        "replay": cmd_replay,
        "debug": cmd_debug,
        "compare": cmd_compare,
        "show-priors": cmd_show_priors,
    }

    handler = command_map.get(args.command)
    if handler:
        try:
            return handler(args)
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user", file=sys.stderr)
            return 130
        except Exception as e:
            print(f"\n❌ Error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
