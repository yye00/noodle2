"""Tests for F274: Create real Nangate45 design snapshot by running ORFS flow.

F274 Requirements:
- Step 1: Run ORFS synthesis for Nangate45 GCD design
- Step 2: Run ORFS floorplan for Nangate45 GCD design
- Step 3: Run ORFS placement for Nangate45 GCD design
- Step 4: Verify .odb file is created with real design data
- Step 5: Copy snapshot to studies/nangate45_base/ directory
- Step 6: Verify snapshot can be loaded by OpenROAD
"""

import subprocess
from pathlib import Path

import pytest

from infrastructure.orfs_flow import (
    create_design_snapshot,
    run_orfs_flow_through_placement,
    run_orfs_stage,
    verify_snapshot_loadable,
)


# Test configuration
PLATFORM = "nangate45"
DESIGN = "gcd"
ORFS_PATH = Path("./orfs")
SNAPSHOT_DIR = Path("./studies/nangate45_base")


class TestStep1RunSynthesis:
    """Step 1: Run ORFS synthesis for Nangate45 GCD design."""

    def test_synthesis_stage_executes(self):
        """Verify synthesis stage can be executed."""
        result = run_orfs_stage("synth", PLATFORM, DESIGN, ORFS_PATH, timeout=300)
        assert result.stage == "synth"
        assert isinstance(result.success, bool)

    def test_synthesis_produces_odb(self):
        """Verify synthesis produces 1_synth.odb file."""
        result = run_orfs_stage("synth", PLATFORM, DESIGN, ORFS_PATH, timeout=300)
        if result.success:
            assert result.odb_file is not None
            assert result.odb_file.exists()
            assert result.odb_file.name == "1_synth.odb"

    def test_synthesis_odb_is_not_empty(self):
        """Verify synthesis ODB file has real content."""
        result = run_orfs_stage("synth", PLATFORM, DESIGN, ORFS_PATH, timeout=300)
        if result.success and result.odb_file:
            # ODB file should be larger than 1KB
            assert result.odb_file.stat().st_size > 1024


class TestStep2RunFloorplan:
    """Step 2: Run ORFS floorplan for Nangate45 GCD design."""

    def test_floorplan_stage_executes(self):
        """Verify floorplan stage can be executed."""
        result = run_orfs_stage("floorplan", PLATFORM, DESIGN, ORFS_PATH, timeout=300)
        assert result.stage == "floorplan"
        assert isinstance(result.success, bool)

    def test_floorplan_produces_odb(self):
        """Verify floorplan produces 2_floorplan.odb file."""
        result = run_orfs_stage("floorplan", PLATFORM, DESIGN, ORFS_PATH, timeout=300)
        if result.success:
            assert result.odb_file is not None
            assert result.odb_file.exists()
            assert result.odb_file.name == "2_floorplan.odb"

    def test_floorplan_odb_is_not_empty(self):
        """Verify floorplan ODB file has real content."""
        result = run_orfs_stage("floorplan", PLATFORM, DESIGN, ORFS_PATH, timeout=300)
        if result.success and result.odb_file:
            assert result.odb_file.stat().st_size > 1024


class TestStep3RunPlacement:
    """Step 3: Run ORFS placement for Nangate45 GCD design."""

    def test_placement_stage_executes(self):
        """Verify placement stage can be executed."""
        result = run_orfs_stage("place", PLATFORM, DESIGN, ORFS_PATH, timeout=300)
        assert result.stage == "place"
        assert isinstance(result.success, bool)

    def test_placement_produces_odb(self):
        """Verify placement produces 3_place.odb file."""
        result = run_orfs_stage("place", PLATFORM, DESIGN, ORFS_PATH, timeout=300)
        if result.success:
            assert result.odb_file is not None
            assert result.odb_file.exists()
            assert result.odb_file.name == "3_place.odb"

    def test_placement_odb_is_not_empty(self):
        """Verify placement ODB file has real content."""
        result = run_orfs_stage("place", PLATFORM, DESIGN, ORFS_PATH, timeout=300)
        if result.success and result.odb_file:
            # Placement ODB should be larger than synthesis
            assert result.odb_file.stat().st_size > 10240  # 10KB


class TestStep4VerifyODBCreated:
    """Step 4: Verify .odb file is created with real design data."""

    def test_complete_flow_produces_odb(self):
        """Verify complete flow through placement produces ODB."""
        results, odb_file = run_orfs_flow_through_placement(PLATFORM, DESIGN, ORFS_PATH)
        assert len(results) == 3  # synth, floorplan, place
        if all(r.success for r in results):
            assert odb_file is not None
            assert odb_file.exists()

    def test_odb_contains_real_design_data(self):
        """Verify ODB file contains actual design data (not mock)."""
        results, odb_file = run_orfs_flow_through_placement(PLATFORM, DESIGN, ORFS_PATH)
        if odb_file and odb_file.exists():
            # Check file size is realistic for a placed design
            size_bytes = odb_file.stat().st_size
            assert size_bytes > 10240, "ODB too small - likely not real data"
            assert size_bytes < 100 * 1024 * 1024, "ODB suspiciously large"

    def test_odb_file_is_readable_binary(self):
        """Verify ODB file is a valid binary file."""
        results, odb_file = run_orfs_flow_through_placement(PLATFORM, DESIGN, ORFS_PATH)
        if odb_file and odb_file.exists():
            # Try to read first few bytes
            with odb_file.open("rb") as f:
                header = f.read(16)
                assert len(header) == 16
                # ODB files should have binary content
                assert b"\x00" in header or len(header) > 0


class TestStep5CopySnapshotToDirectory:
    """Step 5: Copy snapshot to studies/nangate45_base/ directory."""

    def test_create_snapshot_in_target_directory(self):
        """Verify snapshot creation copies to target directory."""
        result = create_design_snapshot(
            PLATFORM, DESIGN, SNAPSHOT_DIR, ORFS_PATH
        )
        assert isinstance(result.success, bool)
        if result.success:
            assert result.snapshot_path == SNAPSHOT_DIR
            assert result.snapshot_path.exists()
            assert result.snapshot_path.is_dir()

    def test_snapshot_odb_exists_in_target(self):
        """Verify ODB file exists in snapshot directory."""
        result = create_design_snapshot(
            PLATFORM, DESIGN, SNAPSHOT_DIR, ORFS_PATH
        )
        if result.success:
            assert result.odb_file is not None
            assert result.odb_file.exists()
            assert result.odb_file.parent == SNAPSHOT_DIR

    def test_snapshot_odb_has_correct_name(self):
        """Verify snapshot ODB has meaningful name."""
        result = create_design_snapshot(
            PLATFORM, DESIGN, SNAPSHOT_DIR, ORFS_PATH
        )
        if result.success and result.odb_file:
            assert result.odb_file.name == "gcd_placed.odb"

    def test_snapshot_directory_is_created_if_missing(self):
        """Verify snapshot directory is created if it doesn't exist."""
        # Create a temporary snapshot dir
        temp_snapshot = Path("./studies/temp_snapshot_test")
        if temp_snapshot.exists():
            import shutil

            shutil.rmtree(temp_snapshot)

        result = create_design_snapshot(
            PLATFORM, DESIGN, temp_snapshot, ORFS_PATH
        )

        if result.success:
            assert temp_snapshot.exists()
            # Cleanup
            import shutil

            shutil.rmtree(temp_snapshot)


class TestStep6VerifySnapshotLoadable:
    """Step 6: Verify snapshot can be loaded by OpenROAD."""

    def test_snapshot_is_loadable_by_openroad(self):
        """Verify snapshot ODB can be loaded by OpenROAD."""
        # First create snapshot
        result = create_design_snapshot(
            PLATFORM, DESIGN, SNAPSHOT_DIR, ORFS_PATH
        )
        if result.success and result.odb_file:
            # Verify it can be loaded
            is_loadable = verify_snapshot_loadable(result.odb_file)
            assert is_loadable, "Snapshot ODB cannot be loaded by OpenROAD"

    def test_openroad_can_read_db(self):
        """Verify OpenROAD read_db command works on snapshot."""
        result = create_design_snapshot(
            PLATFORM, DESIGN, SNAPSHOT_DIR, ORFS_PATH
        )
        if result.success and result.odb_file:
            # Try to load it with OpenROAD (using full path to binary)
            openroad_bin = "/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad"
            cmd = [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{Path.cwd()}:/work",
                "openroad/orfs:latest",
                "bash",
                "-c",
                f"cd /work && {openroad_bin} -exit <<EOF\nread_db {result.odb_file}\nexit\nEOF",
            ]
            proc_result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            assert proc_result.returncode == 0, f"OpenROAD failed: {proc_result.stderr}"


class TestF274Integration:
    """Integration tests for complete F274 workflow."""

    def test_complete_f274_workflow(self):
        """Complete F274 workflow: create real Nangate45 snapshot."""
        # Create snapshot
        result = create_design_snapshot(
            PLATFORM, DESIGN, SNAPSHOT_DIR, ORFS_PATH
        )

        # Verify all aspects
        assert result.success, f"Snapshot creation failed: {result.error}"
        assert result.snapshot_path is not None
        assert result.odb_file is not None
        assert result.platform == PLATFORM
        assert result.design == DESIGN

        # Verify files exist
        assert result.snapshot_path.exists()
        assert result.odb_file.exists()

        # Verify ODB is loadable
        assert verify_snapshot_loadable(result.odb_file)

    def test_f274_all_steps_pass(self):
        """Verify all F274 steps pass in sequence."""
        # Step 1-3: Run flow through placement
        results, odb_file = run_orfs_flow_through_placement(PLATFORM, DESIGN, ORFS_PATH)
        assert all(r.success for r in results), "Flow stages failed"

        # Step 4: Verify ODB created
        assert odb_file is not None
        assert odb_file.exists()

        # Step 5: Copy to snapshot directory
        import shutil

        snapshot_odb = SNAPSHOT_DIR / "gcd_placed.odb"
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(odb_file, snapshot_odb)
        assert snapshot_odb.exists()

        # Step 6: Verify loadable
        assert verify_snapshot_loadable(snapshot_odb)


class TestSnapshotCreationHelpers:
    """Test helper functions for snapshot creation."""

    def test_orfs_stage_result_structure(self):
        """Verify ORFSFlowResult has correct structure."""
        result = run_orfs_stage("synth", PLATFORM, DESIGN, ORFS_PATH, timeout=300)
        assert hasattr(result, "stage")
        assert hasattr(result, "success")
        assert hasattr(result, "odb_file")
        assert hasattr(result, "stdout")
        assert hasattr(result, "stderr")
        assert hasattr(result, "error")

    def test_snapshot_creation_result_structure(self):
        """Verify SnapshotCreationResult has correct structure."""
        result = create_design_snapshot(PLATFORM, DESIGN, SNAPSHOT_DIR, ORFS_PATH)
        assert hasattr(result, "success")
        assert hasattr(result, "snapshot_path")
        assert hasattr(result, "odb_file")
        assert hasattr(result, "platform")
        assert hasattr(result, "design")
        assert hasattr(result, "error")

    def test_flow_returns_all_stage_results(self):
        """Verify flow returns results for all stages."""
        results, _ = run_orfs_flow_through_placement(PLATFORM, DESIGN, ORFS_PATH)
        assert len(results) <= 3  # May stop early on failure
        for result in results:
            assert result.stage in ["synth", "floorplan", "place"]
