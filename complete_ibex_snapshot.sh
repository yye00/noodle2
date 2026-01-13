#!/bin/bash
# Complete ibex extreme snapshot creation after ORFS synthesis
# This script should be run after the ORFS synthesis/placement completes

set -e

echo "=== Completing Ibex Extreme Snapshot Creation ==="

# Wait for synthesis to complete if still running
while pgrep -f "docker run.*ibex.*synth" > /dev/null; do
    echo "Waiting for synthesis to complete..."
    sleep 30
done

echo "✓ Synthesis complete"

# Check if synthesis log exists and was successful
if [ ! -f "/tmp/orfs_synth.log" ]; then
    echo "✗ Synthesis log not found"
    exit 1
fi

if ! grep -q "Finished" /tmp/orfs_synth.log; then
    echo "✗ Synthesis may have failed - check /tmp/orfs_synth.log"
    exit 1
fi

echo "=== Running floorplan and placement ==="

# Run floorplan
docker run --rm openroad/orfs:latest bash -c \
    "cd /OpenROAD-flow-scripts/flow && \
     make DESIGN_CONFIG=designs/nangate45/ibex/config.mk floorplan" \
    > /tmp/orfs_floorplan.log 2>&1

if [ $? -ne 0 ]; then
    echo "✗ Floorplan failed - check /tmp/orfs_floorplan.log"
    exit 1
fi

echo "✓ Floorplan complete"

# Run placement
docker run --rm openroad/orfs:latest bash -c \
    "cd /OpenROAD-flow-scripts/flow && \
     make DESIGN_CONFIG=designs/nangate45/ibex/config.mk place" \
    > /tmp/orfs_place.log 2>&1

if [ $? -ne 0 ]; then
    echo "✗ Placement failed - check /tmp/orfs_place.log"
    exit 1
fi

echo "✓ Placement complete"

# Extract the ODB file from Docker container
echo "=== Extracting ODB file ==="

# Create snapshot directory
mkdir -p studies/nangate45_extreme_ibex

# Copy ODB from Docker (need to run a container to access the file)
docker run --rm \
    -v $(pwd)/studies/nangate45_extreme_ibex:/snapshot \
    openroad/orfs:latest \
    bash -c "cp /OpenROAD-flow-scripts/flow/results/nangate45/ibex/base/3_place.odb /snapshot/ibex_placed.odb"

if [ ! -f "studies/nangate45_extreme_ibex/ibex_placed.odb" ]; then
    echo "✗ Failed to extract ODB file"
    exit 1
fi

echo "✓ ODB file extracted"

# Create STA script with extreme clock constraint
echo "=== Creating STA script ==="

cat > studies/nangate45_extreme_ibex/run_sta.tcl << 'EOF'
# Noodle 2 - Extreme STA for Ibex on Nangate45
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

# Write JSON metrics
set metrics_file "$work_dir/metrics.json"
set fp [open $metrics_file w]
puts $fp "{"
puts $fp "  \"design\": \"ibex_core\","
puts $fp "  \"pdk\": \"nangate45\","
puts $fp "  \"execution_type\": \"real_sta\","
puts $fp "  \"wns_ps\": $wns_ps,"
puts $fp "  \"tns_ps\": $tns_ps,"
puts $fp "  \"hot_ratio\": [format %.6f $hot_ratio],"
puts $fp "  \"clock_period_ns\": 0.5,"
if {$wns_ps < 0} {
    puts $fp "  \"status\": \"timing_violation\""
} else {
    puts $fp "  \"status\": \"timing_met\""
}
puts $fp "}"
close $fp

puts ""
puts "=== Extreme STA Execution Complete ==="
puts "WNS: $wns_ps ps"
puts "Hot ratio: [format %.4f $hot_ratio]"
if {$wns_ps < -1500} {
    puts "Status: EXTREME VIOLATION ACHIEVED (WNS < -1500ps)"
    exit 0
} else {
    puts "Status: WNS not extreme enough (need < -1500ps)"
    exit 1
}
EOF

echo "✓ STA script created"

# Run STA to verify extreme violations
echo "=== Running STA to verify extreme violations ==="

docker run --rm \
    -v $(pwd)/studies/nangate45_extreme_ibex:/snapshot \
    -v $(pwd)/studies/nangate45_extreme_ibex:/work \
    openroad/orfs:latest \
    openroad -exit /snapshot/run_sta.tcl > /tmp/orfs_sta.log 2>&1

if [ $? -ne 0 ]; then
    echo "✗ STA failed or WNS not extreme enough - check /tmp/orfs_sta.log"
    cat studies/nangate45_extreme_ibex/metrics.json
    exit 1
fi

echo "✓ STA complete - extreme violations achieved!"

# Display metrics
echo ""
echo "=== Snapshot Metrics ==="
cat studies/nangate45_extreme_ibex/metrics.json | python3 -m json.tool

echo ""
echo "=== SUCCESS ==="
echo "Ibex extreme snapshot ready at: studies/nangate45_extreme_ibex/"
echo ""
echo "Next steps:"
echo "1. Update demo_nangate45_extreme.sh to use this snapshot"
echo "2. Run the demo to verify F115 and F116"
