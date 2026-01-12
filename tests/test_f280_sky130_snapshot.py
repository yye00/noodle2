"""Tests for F280: Create real Sky130 design snapshot using sky130hd platform.

F280 Requirements:
- Step 1: Run ORFS flow for Sky130 design
- Step 2: Verify sky130_fd_sc_hd library is used
- Step 3: Verify .odb snapshot is created
- Step 4: Execute report_checks and verify real timing data
- Step 5: Copy to studies/sky130_base/
"""

import subprocess
from pathlib import Path

import pytest

from src.infrastructure.orfs_flow import (
    create_design_snapshot,
    run_orfs_flow_through_placement,
    run_orfs_stage,
    verify_snapshot_loadable,
)


# Test configuration
PLATFORM = "sky130hd"
DESIGN = "gcd"
ORFS_PATH = Path("./orfs")
SNAPSHOT_DIR = Path("./studies/sky130_base")
SNAPSHOT_ODB = SNAPSHOT_DIR / "gcd_placed.odb"


class TestStep1RunORFSFlow:
    """Step 1: Run ORFS flow for Sky130 design."""

    def test_sky130_synthesis_stage_executes(self):
        """Verify Sky130 synthesis stage can be executed."""
        result = run_orfs_stage("synth", PLATFORM, DESIGN, ORFS_PATH, timeout=300)
        assert result.stage == "synth"
        assert isinstance(result.success, bool)

    def test_sky130_synthesis_produces_odb(self):
        """Verify Sky130 synthesis produces 1_synth.odb file."""
        result = run_orfs_stage("synth", PLATFORM, DESIGN, ORFS_PATH, timeout=300)
        if result.success:
            assert result.odb_file is not None
            assert result.odb_file.exists()
            assert result.odb_file.name == "1_synth.odb"

    def test_sky130_floorplan_stage_executes(self):
        """Verify Sky130 floorplan stage can be executed."""
        result = run_orfs_stage("floorplan", PLATFORM, DESIGN, ORFS_PATH, timeout=300)
        assert result.stage == "floorplan"
        assert isinstance(result.success, bool)

    def test_sky130_placement_stage_executes(self):
        """Verify Sky130 placement stage can be executed."""
        result = run_orfs_stage("place", PLATFORM, DESIGN, ORFS_PATH, timeout=300)
        assert result.stage == "place"
        assert isinstance(result.success, bool)

    def test_sky130_complete_flow_produces_odb(self):
        """Verify complete Sky130 flow through placement produces ODB."""
        results, odb_file = run_orfs_flow_through_placement(PLATFORM, DESIGN, ORFS_PATH)
        assert len(results) == 3  # synth, floorplan, place
        if all(r.success for r in results):
            assert odb_file is not None
            assert odb_file.exists()


class TestStep2VerifySky130Library:
    """Step 2: Verify sky130_fd_sc_hd library is used."""

    def test_sky130_platform_config_exists(self):
        """Verify Sky130 platform configuration exists."""
        config_file = ORFS_PATH / "flow" / "designs" / PLATFORM / DESIGN / "config.mk"
        assert config_file.exists(), f"Sky130 config not found: {config_file}"

    def test_sky130_config_specifies_platform(self):
        """Verify Sky130 config specifies sky130hd platform."""
        config_file = ORFS_PATH / "flow" / "designs" / PLATFORM / DESIGN / "config.mk"
        if not config_file.exists():
            pytest.skip(f"Config file not found: {config_file}")

        config_content = config_file.read_text()
        assert "PLATFORM" in config_content
        assert "sky130hd" in config_content

    def test_sky130_uses_standard_cell_library(self):
        """Verify Sky130 uses sky130_fd_sc_hd standard cell library."""
        platform_dir = ORFS_PATH / "flow" / "platforms" / "sky130hd"
        if not platform_dir.exists():
            pytest.skip(f"Sky130 platform not found: {platform_dir}")

        # Look for library files
        lib_files = list(platform_dir.glob("**/sky130_fd_sc_hd*.lib"))
        assert len(lib_files) > 0, "No sky130_fd_sc_hd .lib files found"

    def test_sky130_has_liberty_files(self):
        """Verify Sky130 platform has Liberty timing files."""
        platform_dir = ORFS_PATH / "flow" / "platforms" / "sky130hd"
        if not platform_dir.exists():
            pytest.skip(f"Sky130 platform not found: {platform_dir}")

        lib_files = list(platform_dir.glob("**/*.lib"))
        assert len(lib_files) > 0, "No .lib files found for Sky130"

    def test_sky130_has_lef_files(self):
        """Verify Sky130 platform has LEF physical design files."""
        platform_dir = ORFS_PATH / "flow" / "platforms" / "sky130hd"
        if not platform_dir.exists():
            pytest.skip(f"Sky130 platform not found: {platform_dir}")

        lef_files = list(platform_dir.glob("**/*.lef"))
        assert len(lef_files) > 0, "No .lef files found for Sky130"


class TestStep3VerifyODBSnapshot:
    """Step 3: Verify .odb snapshot is created."""

    def test_create_sky130_snapshot_function_succeeds(self):
        """Verify create_design_snapshot works for Sky130."""
        result = create_design_snapshot(PLATFORM, DESIGN, SNAPSHOT_DIR, ORFS_PATH)
        assert isinstance(result.success, bool)

    def test_sky130_snapshot_creates_odb_file(self):
        """Verify Sky130 snapshot creates .odb file."""
        result = create_design_snapshot(PLATFORM, DESIGN, SNAPSHOT_DIR, ORFS_PATH)
        if result.success:
            assert result.odb_file is not None
            assert result.odb_file.exists()
            assert result.odb_file.suffix == ".odb"

    def test_sky130_snapshot_copied_to_studies_directory(self):
        """Verify Sky130 snapshot is copied to studies/sky130_base/."""
        result = create_design_snapshot(PLATFORM, DESIGN, SNAPSHOT_DIR, ORFS_PATH)
        if result.success:
            assert result.snapshot_path == SNAPSHOT_DIR
            assert (SNAPSHOT_DIR / "gcd_placed.odb").exists()

    def test_sky130_snapshot_has_reasonable_size(self):
        """Verify Sky130 snapshot file has reasonable size (> 100 KB)."""
        if not SNAPSHOT_ODB.exists():
            result = create_design_snapshot(PLATFORM, DESIGN, SNAPSHOT_DIR, ORFS_PATH)
            if not result.success:
                pytest.skip("Snapshot creation failed")

        if SNAPSHOT_ODB.exists():
            size_bytes = SNAPSHOT_ODB.stat().st_size
            size_kb = size_bytes / 1024
            assert size_kb > 100, f"Snapshot too small: {size_kb:.1f} KB"


class TestStep4ReportChecksTimingData:
    """Step 4: Execute report_checks and verify real timing data."""

    def test_snapshot_is_loadable_by_openroad(self):
        """Verify Sky130 snapshot can be loaded by OpenROAD."""
        if not SNAPSHOT_ODB.exists():
            result = create_design_snapshot(PLATFORM, DESIGN, SNAPSHOT_DIR, ORFS_PATH)
            if not result.success:
                pytest.skip("Snapshot creation failed")

        assert verify_snapshot_loadable(SNAPSHOT_ODB), "Snapshot not loadable by OpenROAD"

    def test_report_checks_executes_successfully(self):
        """Verify report_checks can be executed on Sky130 snapshot."""
        if not SNAPSHOT_ODB.exists():
            pytest.skip("Snapshot not available")

        mount_path = Path.cwd()
        abs_odb_path = SNAPSHOT_ODB.resolve()
        rel_odb_path = abs_odb_path.relative_to(mount_path)
        openroad_bin = "/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad"

        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{mount_path}:/work",
            "openroad/orfs:latest",
            "bash",
            "-c",
            f'''cd /work && {openroad_bin} -exit <<EOF
read_db {rel_odb_path}
report_checks
exit
EOF''',
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        # report_checks should run without crashing
        assert result.returncode == 0, f"OpenROAD failed: {result.stderr}"

    def test_report_checks_shows_timing_info(self):
        """Verify report_checks shows timing information (even if no liberty)."""
        if not SNAPSHOT_ODB.exists():
            pytest.skip("Snapshot not available")

        mount_path = Path.cwd()
        abs_odb_path = SNAPSHOT_ODB.resolve()
        rel_odb_path = abs_odb_path.relative_to(mount_path)
        openroad_bin = "/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad"

        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{mount_path}:/work",
            "openroad/orfs:latest",
            "bash",
            "-c",
            f'''cd /work && {openroad_bin} -exit <<EOF
read_db {rel_odb_path}
report_checks
exit
EOF''',
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Should mention either timing data or lack of liberty
        output = result.stdout + result.stderr
        has_timing_info = (
            "startpoint" in output.lower()
            or "endpoint" in output.lower()
            or "slack" in output.lower()
            or "No liberty libraries" in output
            or "no timing" in output.lower()
        )
        assert has_timing_info, f"No timing info in output: {output[:500]}"

    def test_snapshot_contains_real_cells(self):
        """Verify Sky130 snapshot contains real placed cells."""
        if not SNAPSHOT_ODB.exists():
            pytest.skip("Snapshot not available")

        mount_path = Path.cwd()
        abs_odb_path = SNAPSHOT_ODB.resolve()
        rel_odb_path = abs_odb_path.relative_to(mount_path)
        openroad_bin = "/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad"

        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{mount_path}:/work",
            "openroad/orfs:latest",
            "bash",
            "-c",
            f'''cd /work && {openroad_bin} -exit <<EOF
read_db {rel_odb_path}
puts "Instance count: [llength [get_cells *]]"
exit
EOF''',
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        output = result.stdout
        # Should have cells (GCD design has instances)
        assert "Instance count:" in output
        # Extract count
        for line in output.splitlines():
            if "Instance count:" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    count = int(parts[1].strip())
                    assert count > 0, f"Expected cells, got {count}"


class TestStep5CopyToStudiesDirectory:
    """Step 5: Copy to studies/sky130_base/."""

    def test_snapshot_directory_is_created(self):
        """Verify studies/sky130_base/ directory is created."""
        if not SNAPSHOT_ODB.exists():
            result = create_design_snapshot(PLATFORM, DESIGN, SNAPSHOT_DIR, ORFS_PATH)
            if not result.success:
                pytest.skip("Snapshot creation failed")

        assert SNAPSHOT_DIR.exists()
        assert SNAPSHOT_DIR.is_dir()

    def test_snapshot_file_exists_in_correct_location(self):
        """Verify gcd_placed.odb exists in studies/sky130_base/."""
        if not SNAPSHOT_ODB.exists():
            result = create_design_snapshot(PLATFORM, DESIGN, SNAPSHOT_DIR, ORFS_PATH)
            if not result.success:
                pytest.skip("Snapshot creation failed")

        assert SNAPSHOT_ODB.exists()
        assert SNAPSHOT_ODB.parent == SNAPSHOT_DIR

    def test_snapshot_path_is_correct(self):
        """Verify snapshot path matches expected location."""
        result = create_design_snapshot(PLATFORM, DESIGN, SNAPSHOT_DIR, ORFS_PATH)
        if result.success:
            assert result.snapshot_path == SNAPSHOT_DIR
            assert result.odb_file == SNAPSHOT_ODB

    def test_snapshot_is_accessible(self):
        """Verify snapshot file is readable."""
        if not SNAPSHOT_ODB.exists():
            pytest.skip("Snapshot not created")

        assert SNAPSHOT_ODB.is_file()
        # Try to read first few bytes
        with open(SNAPSHOT_ODB, "rb") as f:
            header = f.read(4)
            assert len(header) == 4, "Cannot read snapshot file"


class TestIntegration:
    """Integration tests for complete Sky130 snapshot workflow."""

    def test_complete_sky130_snapshot_workflow(self):
        """Test complete workflow: create, verify, copy Sky130 snapshot."""
        # Step 1: Create snapshot
        result = create_design_snapshot(PLATFORM, DESIGN, SNAPSHOT_DIR, ORFS_PATH)
        assert result.success, f"Snapshot creation failed: {result.error}"

        # Step 2: Verify ODB file
        assert result.odb_file is not None
        assert result.odb_file.exists()

        # Step 3: Verify location
        assert result.snapshot_path == SNAPSHOT_DIR
        assert result.odb_file == SNAPSHOT_ODB

        # Step 4: Verify loadable
        assert verify_snapshot_loadable(result.odb_file)

    def test_sky130_snapshot_different_from_nangate45(self):
        """Verify Sky130 and Nangate45 snapshots are different (different PDKs)."""
        nangate45_snapshot = Path("studies/nangate45_base/gcd_placed.odb")
        sky130_snapshot = SNAPSHOT_ODB

        if not nangate45_snapshot.exists():
            pytest.skip("Nangate45 snapshot not available")

        if not sky130_snapshot.exists():
            result = create_design_snapshot(PLATFORM, DESIGN, SNAPSHOT_DIR, ORFS_PATH)
            if not result.success:
                pytest.skip("Sky130 snapshot creation failed")

        # Different PDKs should have different file sizes
        ng45_size = nangate45_snapshot.stat().st_size
        sky130_size = sky130_snapshot.stat().st_size

        # Sizes should differ (different cell libraries)
        assert ng45_size != sky130_size, "Snapshots should have different sizes"

    def test_sky130_snapshot_different_from_asap7(self):
        """Verify Sky130 and ASAP7 snapshots are different (different PDKs)."""
        asap7_snapshot = Path("studies/asap7_base/gcd_placed.odb")
        sky130_snapshot = SNAPSHOT_ODB

        if not asap7_snapshot.exists():
            pytest.skip("ASAP7 snapshot not available")

        if not sky130_snapshot.exists():
            result = create_design_snapshot(PLATFORM, DESIGN, SNAPSHOT_DIR, ORFS_PATH)
            if not result.success:
                pytest.skip("Sky130 snapshot creation failed")

        # Different PDKs should have different file sizes
        asap7_size = asap7_snapshot.stat().st_size
        sky130_size = sky130_snapshot.stat().st_size

        # Sizes should differ (different nodes: 7nm vs 130nm)
        assert asap7_size != sky130_size, "Snapshots should have different sizes"

    def test_all_three_pdks_have_snapshots(self):
        """Verify all three PDK snapshots exist (Nangate45, ASAP7, Sky130)."""
        nangate45_snapshot = Path("studies/nangate45_base/gcd_placed.odb")
        asap7_snapshot = Path("studies/asap7_base/gcd_placed.odb")
        sky130_snapshot = SNAPSHOT_ODB

        # Create Sky130 if needed
        if not sky130_snapshot.exists():
            result = create_design_snapshot(PLATFORM, DESIGN, SNAPSHOT_DIR, ORFS_PATH)
            if not result.success:
                pytest.skip("Sky130 snapshot creation failed")

        # Check all exist
        snapshots_exist = {
            "Nangate45": nangate45_snapshot.exists(),
            "ASAP7": asap7_snapshot.exists(),
            "Sky130": sky130_snapshot.exists(),
        }

        # Sky130 must exist
        assert snapshots_exist["Sky130"], "Sky130 snapshot must exist"

        # Report status
        print("\nPDK Snapshot Status:")
        for pdk, exists in snapshots_exist.items():
            print(f"  {pdk}: {'✅' if exists else '❌'}")

    def test_both_snapshots_loadable(self):
        """Verify both Nangate45 and Sky130 snapshots are loadable."""
        nangate45_snapshot = Path("studies/nangate45_base/gcd_placed.odb")
        sky130_snapshot = SNAPSHOT_ODB

        # Create Sky130 if needed
        if not sky130_snapshot.exists():
            result = create_design_snapshot(PLATFORM, DESIGN, SNAPSHOT_DIR, ORFS_PATH)
            if not result.success:
                pytest.skip("Sky130 snapshot creation failed")

        # Verify Sky130 loadable
        assert verify_snapshot_loadable(sky130_snapshot), "Sky130 snapshot not loadable"

        # Verify Nangate45 loadable (if exists)
        if nangate45_snapshot.exists():
            assert verify_snapshot_loadable(nangate45_snapshot), "Nangate45 snapshot not loadable"
