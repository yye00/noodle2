#!/usr/bin/env python3
"""
Command-line interface for feature tracking and progress reporting.

Usage:
    python -m src.tracking.cli [--detailed]
"""

import sys
import argparse
from pathlib import Path

from .feature_loader import load_feature_list, validate_feature_list
from .progress_report import generate_progress_report


def main() -> int:
    """Main entry point for progress report CLI."""
    parser = argparse.ArgumentParser(
        description="Generate feature implementation progress report"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed breakdown by category",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate feature list structure and requirements",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of human-readable format",
    )
    parser.add_argument(
        "--feature-list",
        type=Path,
        help="Path to feature_list.json (defaults to project root)",
    )

    args = parser.parse_args()

    try:
        # Load feature list
        features = load_feature_list(args.feature_list)

        # Validate if requested
        if args.validate:
            print("Validating feature list structure...\n")
            result = validate_feature_list(features)

            if result["errors"]:
                print("❌ Validation FAILED\n")
                print("Errors:")
                for error in result["errors"]:
                    print(f"  • {error}")
                print()
            else:
                print("✅ Validation PASSED\n")

            if result["warnings"]:
                print("Warnings:")
                for warning in result["warnings"]:
                    print(f"  • {warning}")
                print()

            print("Statistics:")
            for key, value in result["stats"].items():
                formatted_key = key.replace("_", " ").title()
                if isinstance(value, float):
                    print(f"  {formatted_key}: {value:.2f}")
                else:
                    print(f"  {formatted_key}: {value}")

            return 0 if result["valid"] else 1

        # Generate progress report
        report = generate_progress_report(features)

        if args.json:
            import json
            print(json.dumps(report.to_dict(), indent=2))
        else:
            report.print_report(detailed=args.detailed)

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
