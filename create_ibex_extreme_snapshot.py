#!/usr/bin/env python3
"""
Create an extreme snapshot for ibex design on Nangate45 PDK.

This script:
1. Runs OpenROAD-flow-scripts to synthesize and place ibex
2. Extracts the placed ODB file
3. Creates an STA script with extremely aggressive clock constraints
4. Runs STA to verify WNS < -1500ps
5. Packages everything into a snapshot directory

The ibex design is much larger than GCD and has longer critical paths,
making it possible to achieve WNS < -1500ps violations.
"""

import json
import shutil
import subprocess
from pathlib import Path

# Paths
NOODLE2_ROOT = Path(__file__).parent
ORFS_ROOT = NOODLE2_ROOT / "orfs"
ORFS_FLOW = ORFS_ROOT / "flow"
DESIGN_CONFIG = "designs/nangate45/ibex/config.mk"
SNAPSHOT_DIR = NOODLE2_ROOT / "studies" / "nangate45_extreme_ibex"

def run_command(cmd: list[str], cwd: Path, description: str) -> tuple[bool, str]:
    """Run a command and return success status and output."""
    print(f"\n=== {description} ===")
    print(f"Command: {' '.join(cmd)}")
    print(f"Working directory: {cwd}")

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout
        )

        if result.returncode == 0:
            print(f"✓ {description} completed successfully")
            return True, result.stdout
        else:
            print(f"✗ {description} failed")
            print(f"STDOUT:\n{result.stdout}")
            print(f"STDERR:\n{result.stderr}")
            return False, result.stderr

    except subprocess.TimeoutExpired:
        print(f"✗ {description} timed out after 30 minutes")
        return False, "Timeout"
    except Exception as e:
        print(f"✗ {description} failed with exception: {e}")
        return False, str(e)

def main():
    """Main execution flow."""
    print("=== Creating Ibex Extreme Snapshot ===")
    print(f"ORFS root: {ORFS_ROOT}")
    print(f"Snapshot output: {SNAPSHOT_DIR}")

    # Step 1: Run ORFS to synthesize and place ibex
    print("\n### Step 1: Running ORFS synthesis and placement ###")

    # Clean previous build
    success, _ = run_command(
        ["make", "clean", f"DESIGN_CONFIG={DESIGN_CONFIG}"],
        ORFS_FLOW,
        "Clean previous ORFS build"
    )

    # Run synthesis
    success, _ = run_command(
        ["make", f"DESIGN_CONFIG={DESIGN_CONFIG}", "synth"],
        ORFS_FLOW,
        "ORFS synthesis"
    )
    if not success:
        print("✗ Synthesis failed, aborting")
        return False

    # Run floorplan
    success, _ = run_command(
        ["make", f"DESIGN_CONFIG={DESIGN_CONFIG}", "floorplan"],
        ORFS_FLOW,
        "ORFS floorplan"
    )
    if not success:
        print("✗ Floorplan failed, aborting")
        return False

    # Run placement
    success, _ = run_command(
        ["make", f"DESIGN_CONFIG={DESIGN_CONFIG}", "place"],
        ORFS_FLOW,
        "ORFS placement"
    )
    if not success:
        print("✗ Placement failed, aborting")
        return False

    # Step 2: Find and copy the placed ODB
    print("\n### Step 2: Extracting placed ODB ###")

    results_dir = ORFS_FLOW / "results" / "nangate45" / "ibex" / "base"
    odb_file = results_dir / "3_place.odb"

    if not odb_file.exists():
        print(f"✗ Placed ODB not found at {odb_file}")
        return False

    print(f"✓ Found placed ODB: {odb_file}")
    print(f"  Size: {odb_file.stat().st_size / 1024 / 1024:.1f} MB")

    # Step 3: Create snapshot directory
    print("\n### Step 3: Creating snapshot directory ###")

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # Copy ODB file
    dest_odb = SNAPSHOT_DIR / "ibex_placed.odb"
    shutil.copy2(odb_file, dest_odb)
    print(f"✓ Copied ODB to {dest_odb}")

    # Copy constraint file for reference
    constraint_src = ORFS_ROOT / "flow" / DESIGN_CONFIG.replace("config.mk", "constraint.sdc")
    constraint_dest = SNAPSHOT_DIR / "ibex_base.sdc"
    shutil.copy2(constraint_src, constraint_dest)
    print(f"✓ Copied constraints to {constraint_dest}")

    # Step 4: Create extreme STA script
    print("\n### Step 4: Creating extreme STA script ###")

    sta_script = SNAPSHOT_DIR / "run_sta.tcl"
    sta_content = """# Noodle 2 - Extreme STA for Ibex on Nangate45
# This script creates EXTREME timing violations (WNS < -1500ps)

puts "=== Noodle 2 Extreme STA - Ibex Design ==="
puts "Design: ibex_core"
puts "PDK: Nangate45"
puts ""

# Paths inside ORFS container
set platform_dir "/OpenROAD-flow-scripts/flow/platforms/nangate45"
set lib_file "$platform_dir/lib/NangateOpenCellLibrary_typical.lib"
set lef_file "$platform_dir/lef/NangateOpenCellLibrary.macro.mod.lef"
set tech_lef "$platform_dir/lef/NangateOpenCellLibrary.tech.lef"

# Input/output paths
set snapshot_dir "/snapshot"
set work_dir "/work"
set odb_file "$snapshot_dir/ibex_placed.odb"

puts "Loading timing library: $lib_file"
puts "Loading LEF: $lef_file"
puts "Loading design: $odb_file"
puts ""

# Read technology LEF first if it exists
if {[file exists $tech_lef]} {
    read_lef $tech_lef
}

# Read standard cell LEF
read_lef $lef_file

# Read timing library
read_liberty $lib_file

# Read the placed design
read_db $odb_file

# Create EXTREME clock constraint
# Ibex default: 2.2ns (450 MHz)
# For extreme violations: Use 0.5ns (2000 MHz) - 4.4x faster than default
# This should create WNS < -1500ps on the unoptimized placed design
create_clock -name core_clock -period 0.5 [get_ports clk_i]

# Minimal I/O delays to maximize internal path violations
set_input_delay 0.05 -clock core_clock [all_inputs -no_clocks]
set_output_delay 0.05 -clock core_clock [all_outputs]

puts "=== Running Static Timing Analysis ==="
puts "Clock constraint: 0.5ns (EXTREME - 4.4x default)"
puts ""

# Report worst paths
report_checks -path_delay min_max -fields {slew cap input_pin net} -digits 4 -format full_clock_expanded

# Get WNS and TNS
set wns [sta::worst_slack -max]
set tns [sta::total_negative_slack -max]

# Convert to picoseconds
set wns_ps [expr {int($wns * 1000)}]
set tns_ps [expr {int($tns * 1000)}]

puts ""
puts "=== Timing Summary ==="
puts "WNS: $wns ns ($wns_ps ps)"
puts "TNS: $tns ns ($tns_ps ps)"

# Calculate hot_ratio
if {$wns < 0} {
    set estimated_violations [expr {abs($tns / $wns)}]
    # Ibex has many more endpoints than GCD, estimate ~1000
    set hot_ratio [expr {min(1.0, $estimated_violations / 1000.0)}]
} else {
    set hot_ratio 0.0
}

puts "Hot ratio (estimated): [format %.4f $hot_ratio]"

# Generate timing report
set timing_report "$work_dir/timing_report.txt"
set fp [open $timing_report w]
puts $fp "=== Noodle 2 Extreme STA Report - Ibex ==="
puts $fp "Design: ibex_core (RISC-V CPU)"
puts $fp "PDK: Nangate45"
puts $fp "Clock period: 0.5 ns (EXTREME - 2000 MHz target)"
puts $fp ""
puts $fp "Timing Summary:"
puts $fp "  WNS: $wns ns ($wns_ps ps)"
puts $fp "  TNS: $tns ns ($tns_ps ps)"
puts $fp "  Hot ratio: [format %.4f $hot_ratio]"
puts $fp ""
puts $fp "Expected WNS < -1500ps for extreme demo"
puts $fp "=== End Report ==="
close $fp

puts "Generated timing report: $timing_report"

# Write JSON metrics
set metrics_file "$work_dir/metrics.json"
set fp [open $metrics_file w]
puts $fp "{"
puts $fp "  \\"design\\": \\"ibex_core\\","
puts $fp "  \\"pdk\\": \\"nangate45\\","
puts $fp "  \\"execution_type\\": \\"real_sta\\","
puts $fp "  \\"wns_ps\\": $wns_ps,"
puts $fp "  \\"tns_ps\\": $tns_ps,"
puts $fp "  \\"hot_ratio\\": [format %.6f $hot_ratio],"
puts $fp "  \\"clock_period_ns\\": 0.5,"
if {$wns_ps < 0} {
    puts $fp "  \\"status\\": \\"timing_violation\\""
} else {
    puts $fp "  \\"status\\": \\"timing_met\\""
}
puts $fp "}"
close $fp

puts "Generated metrics: $metrics_file"

puts ""
puts "=== Extreme STA Execution Complete ==="
puts "WNS: $wns_ps ps"
puts "Hot ratio: [format %.4f $hot_ratio]"
if {$wns_ps < -1500} {
    puts "Status: EXTREME VIOLATION ACHIEVED (WNS < -1500ps)"
    exit 0
} elseif {$wns_ps < 0} {
    puts "Status: TIMING VIOLATION (but not extreme enough)"
    exit 1
} else {
    puts "Status: TIMING MET (UNEXPECTED)"
    exit 1
}
"""

    with open(sta_script, 'w') as f:
        f.write(sta_content)

    print(f"✓ Created STA script at {sta_script}")

    # Step 5: Run STA in Docker to verify extreme violations
    print("\n### Step 5: Running STA to verify extreme violations ###")

    docker_cmd = [
        "docker", "run", "--rm",
        "-v", f"{SNAPSHOT_DIR}:/snapshot",
        "-v", f"{SNAPSHOT_DIR}:/work",
        "openroad/orfs:latest",
        "openroad", "-exit", "/snapshot/run_sta.tcl"
    ]

    success, output = run_command(
        docker_cmd,
        NOODLE2_ROOT,
        "Run STA in Docker"
    )

    # Check metrics file
    metrics_file = SNAPSHOT_DIR / "metrics.json"
    if metrics_file.exists():
        with open(metrics_file) as f:
            metrics = json.load(f)

        wns_ps = metrics['wns_ps']
        hot_ratio = metrics['hot_ratio']

        print(f"\n=== Snapshot Metrics ===")
        print(f"WNS: {wns_ps} ps")
        print(f"Hot ratio: {hot_ratio:.4f}")

        if wns_ps < -1500:
            print(f"✓ SUCCESS: Extreme violations achieved (WNS = {wns_ps}ps < -1500ps)")
            print(f"✓ Snapshot ready at {SNAPSHOT_DIR}")
            return True
        else:
            print(f"⚠ WARNING: WNS = {wns_ps}ps is not extreme enough (need < -1500ps)")
            print(f"  Consider using an even smaller clock period")
            return False
    else:
        print(f"✗ Metrics file not found at {metrics_file}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
