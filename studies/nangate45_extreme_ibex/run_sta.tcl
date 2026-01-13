# Noodle 2 - Extreme STA script for Ibex Core
# This script runs STA only and does NOT write files (metrics.json already exists)

puts "=== Noodle 2 Extreme STA - Ibex Core ==="

# Read design files
read_lef /OpenROAD-flow-scripts/flow/platforms/nangate45/lef/NangateOpenCellLibrary.tech.lef
read_lef /OpenROAD-flow-scripts/flow/platforms/nangate45/lef/NangateOpenCellLibrary.macro.mod.lef
read_liberty /OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib

# Read the placed design
read_db /snapshot/ibex_placed.odb

# EXTREME clock constraint: 0.35ns (2857 MHz)
create_clock -name core_clock -period 0.35 [get_ports clk_i]

# Minimal I/O delays
set_input_delay 0.02 -clock core_clock [all_inputs -no_clocks]
set_output_delay 0.02 -clock core_clock [all_outputs]

puts "Clock period: 0.35ns (EXTREME - 6.3x nominal)"
puts ""

# Run STA and report
puts "Running Static Timing Analysis..."
report_checks -path_delay min_max -fields {slew cap input_pin net} -digits 4 -format full_clock_expanded

# Get timing metrics
set wns [sta::worst_slack -max]
set tns [sta::total_negative_slack -max]
set wns_ps [expr {int($wns * 1000)}]
set tns_ps [expr {int($tns * 1000)}]

# Estimate hot_ratio
if {$wns < 0} {
    set violations [expr {abs($tns / $wns)}]
    set hot_ratio [expr {min(1.0, $violations / 2500.0)}]
} else {
    set hot_ratio 0.0
}

puts ""
puts "=== Timing Summary ==="
puts "WNS: $wns_ps ps"
puts "TNS: $tns_ps ps"
puts "Hot ratio (estimated): [format %.4f $hot_ratio]"
puts ""

# NOTE: We do NOT write metrics.json here - it already exists in the snapshot
# This script is for runtime STA only

exit 0
