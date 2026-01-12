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

    return parser


def cmd_run(args: argparse.Namespace) -> int:
    """Execute run command."""
    print(f"🚀 Running Study: {args.study}")
    print(f"   Ray address: {args.ray_address}")
    if args.checkpoint_dir:
        print(f"   Checkpoints: {args.checkpoint_dir}")
    if args.dry_run:
        print("   Dry run: validation only")
    print()
    print("Error: Study execution not yet implemented.")
    print("This is a placeholder for the full Study runner.")
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
        "validate": cmd_validate,
        "list-studies": cmd_list_studies,
        "ls": cmd_list_studies,
        "show": cmd_show,
        "export": cmd_export,
        "progress": cmd_progress,
        "init": cmd_init,
        "replay": cmd_replay,
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
