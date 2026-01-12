#!/usr/bin/env python3
"""Create ASAP7 design snapshot by running ORFS flow.

This script creates a real ASAP7 GCD design snapshot with ASAP7-specific
workarounds for Feature #279.
"""

from pathlib import Path

from src.infrastructure.orfs_flow import (
    create_design_snapshot,
    verify_snapshot_loadable,
)


def main():
    """Create ASAP7 GCD snapshot."""
    print("=" * 60)
    print("Creating ASAP7 GCD Design Snapshot")
    print("=" * 60)
    print()

    platform = "asap7"
    design = "gcd"
    snapshot_dir = Path("studies/asap7_base")
    orfs_path = Path("orfs")

    print(f"Platform: {platform}")
    print(f"Design: {design}")
    print(f"Snapshot directory: {snapshot_dir}")
    print(f"ORFS path: {orfs_path}")
    print()

    print("Running ORFS flow (synth -> floorplan -> place)...")
    print("This may take several minutes...")
    print()

    result = create_design_snapshot(platform, design, snapshot_dir, orfs_path)

    if not result.success:
        print(f"❌ Failed to create snapshot: {result.error}")
        return 1

    print("✅ Snapshot created successfully!")
    print()
    print(f"Snapshot path: {result.snapshot_path}")
    print(f"ODB file: {result.odb_file}")
    print()

    # Verify snapshot is loadable
    print("Verifying snapshot is loadable by OpenROAD...")
    if verify_snapshot_loadable(result.odb_file):
        print("✅ Snapshot is loadable!")
    else:
        print("❌ Warning: Snapshot may not be loadable")
        return 1

    print()
    print("ASAP7 snapshot created successfully at:")
    print(f"  {result.odb_file}")
    print()

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
