#!/bin/bash
# Create Ibex Extreme Snapshot - Single Container Approach
# Runs all ORFS steps in one container to preserve intermediate files

set -e

echo "========================================"
echo "Creating Ibex Extreme Snapshot (v2)"
echo "========================================"
echo ""

SNAPSHOT_DIR="$(pwd)/studies/nangate45_extreme_ibex"
mkdir -p "$SNAPSHOT_DIR"

echo "Snapshot directory: $SNAPSHOT_DIR"
echo ""

# Run all ORFS steps in a single container with volume mount
echo "=== Running ORFS flow (synthesis -> placement) ==="
echo "This takes ~10-15 minutes..."
echo ""

docker run --rm \
    -v "$SNAPSHOT_DIR:/snapshot" \
    openroad/orfs:latest \
    bash -c '
set -e

cd /OpenROAD-flow-scripts/flow

echo "Step 1: Clean previous builds..."
make DESIGN_CONFIG=designs/nangate45/ibex/config.mk clean_all > /dev/null 2>&1 || true

echo "Step 2: Running synthesis..."
make DESIGN_CONFIG=designs/nangate45/ibex/config.mk synth

echo "Step 3: Running floorplan..."
make DESIGN_CONFIG=designs/nangate45/ibex/config.mk floorplan

echo "Step 4: Running placement..."
make DESIGN_CONFIG=designs/nangate45/ibex/config.mk place

echo "Step 5: Locating ODB file..."
ODB_PATH=$(find results/nangate45/ibex -name "*place*.odb" -o -name "3_*.odb" | head -1)

if [ -z "$ODB_PATH" ]; then
    echo "Error: Could not find placed ODB file"
    find results/nangate45/ibex -type f -name "*.odb"
    exit 1
fi

echo "Found ODB: $ODB_PATH"
cp "$ODB_PATH" /snapshot/ibex_placed.odb
echo "ODB copied to /snapshot/ibex_placed.odb"

# Create extreme STA script
cat > /snapshot/run_sta.tcl << '"'"'EOFTCL'"'"'
# Extreme STA for Ibex - Generate WNS < -1500ps
puts "=== Extreme STA for Ibex Core ==="

# Read design
read_lef /OpenROAD-flow-scripts/flow/platforms/nangate45/lef/NangateOpenCellLibrary.tech.lef
read_lef /OpenROAD-flow-scripts/flow/platforms/nangate45/lef/NangateOpenCellLibrary.macro.mod.lef
read_liberty /OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib
read_db /snapshot/ibex_placed.odb

# EXTREME clock constraint: 0.35ns (2857 MHz)
# Ibex nominal: 2.2ns (450 MHz)
# This is 6.3x faster than nominal, should give WNS < -1500ps
create_clock -name core_clock -period 0.35 [get_ports clk_i]

set_input_delay 0.02 -clock core_clock [all_inputs -no_clocks]
set_output_delay 0.02 -clock core_clock [all_outputs]

puts "Clock period: 0.35ns (EXTREME - 6.3x nominal)"
puts ""

# Run STA
puts "Running STA..."

# Get metrics
set wns [sta::worst_slack -max]
set tns [sta::total_negative_slack -max]
set wns_ps [expr {int($wns * 1000)}]
set tns_ps [expr {int($tns * 1000)}]

puts ""
puts "=== Timing Results ==="
puts "WNS: $wns_ps ps"
puts "TNS: $tns_ps ps"

# Estimate hot_ratio
if {$wns < 0} {
    set violations [expr {abs($tns / $wns)}]
    # Ibex has ~2000-3000 timing endpoints
    set hot_ratio [expr {min(1.0, $violations / 2500.0)}]
} else {
    set hot_ratio 0.0
}

puts "Hot ratio (estimated): [format %.4f $hot_ratio]"

# Write metrics JSON
set fp [open /snapshot/metrics.json w]
puts $fp "{"
puts $fp "  \"design\": \"ibex_core\","
puts $fp "  \"pdk\": \"nangate45\","
puts $fp "  \"execution_type\": \"real_sta\","
puts $fp "  \"wns_ps\": $wns_ps,"
puts $fp "  \"tns_ps\": $tns_ps,"
puts $fp "  \"hot_ratio\": [format %.6f $hot_ratio],"
puts $fp "  \"clock_period_ns\": 0.35,"
puts $fp "  \"status\": \"timing_violation\""
puts $fp "}"
close $fp

# Write metadata
set fp [open /snapshot/metadata.json w]
puts $fp "{"
puts $fp "  \"design\": \"ibex_core\","
puts $fp "  \"pdk\": \"NANGATE45\","
puts $fp "  \"clock_period_ns\": 0.35,"
puts $fp "  \"creation_method\": \"docker_orfs_single_container\","
puts $fp "  \"purpose\": \"extreme_demo\","
puts $fp "  \"orfs_stage\": \"placed\""
puts $fp "}"
close $fp

puts ""
puts "=== Snapshot Creation Complete ==="
if {$wns_ps < -1500} {
    puts "✓ EXTREME violation achieved (WNS < -1500ps)"
} else {
    puts "⚠ WNS = $wns_ps ps (target < -1500ps)"
}
exit 0
EOFTCL

echo "Step 6: Running extreme STA..."
openroad -exit /snapshot/run_sta.tcl

echo ""
echo "=== SUCCESS ==="
ls -lh /snapshot/
' 2>&1 | tee /tmp/ibex_creation.log

# Check results
if [ ! -f "$SNAPSHOT_DIR/metrics.json" ]; then
    echo ""
    echo "✗ Failed to create snapshot"
    tail -100 /tmp/ibex_creation.log
    exit 1
fi

echo ""
echo "=== Snapshot Metrics ==="
cat "$SNAPSHOT_DIR/metrics.json"
echo ""

# Validate
WNS=$(grep -oP '"wns_ps":\s*\K-?\d+' "$SNAPSHOT_DIR/metrics.json")
HOT_RATIO=$(grep -oP '"hot_ratio":\s*\K[0-9.]+' "$SNAPSHOT_DIR/metrics.json")

echo "=== Validation ==="
if [ "$WNS" -lt -1500 ]; then
    echo "✓ WNS = ${WNS}ps (target < -1500ps) - PASS"
else
    echo "⚠ WNS = ${WNS}ps (target < -1500ps)"
fi

if [ $(echo "$HOT_RATIO > 0.3" | bc -l) -eq 1 2>/dev/null ] || [ "$HOT_RATIO" = "1.000000" ]; then
    echo "✓ hot_ratio = ${HOT_RATIO} (target > 0.3) - PASS"
else
    echo "⚠ hot_ratio = ${HOT_RATIO} (target > 0.3)"
fi

echo ""
echo "========================================"
echo "Ibex Extreme Snapshot Created!"
echo "========================================"
echo "Location: $SNAPSHOT_DIR"
echo ""
echo "Files:"
ls -lh "$SNAPSHOT_DIR"
