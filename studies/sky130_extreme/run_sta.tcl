# Noodle 2 - Real STA Execution for Sky130
# This script runs ACTUAL OpenROAD Static Timing Analysis
# NO fake metrics - real STA on real design

puts "=== Noodle 2 Real STA Execution ==="
puts "Design: GCD (placed)"
puts "PDK: Sky130HD (130nm)"
puts ""

# Paths inside ORFS container
set platform_dir "/OpenROAD-flow-scripts/flow/platforms/sky130hd"
set lib_file "$platform_dir/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
set lef_file "$platform_dir/lef/sky130_fd_sc_hd_merged.lef"

# Input/output paths
set snapshot_dir "/snapshot"
set work_dir "/work"
set odb_file "$snapshot_dir/gcd_placed.odb"

puts "Loading timing library: $lib_file"
puts "Loading LEF: $lef_file"
puts "Loading design: $odb_file"
puts ""

# Read standard cell LEF
read_lef $lef_file

# Read timing library
read_liberty $lib_file

# Read the placed design
read_db $odb_file

# Create a clock (moderate for 130nm - 100MHz target)
create_clock -name clk -period 10.0 [get_ports clk]

# Set output delays only (avoid warning about input delay on clock port)
set_output_delay -clock clk 0.5 [all_outputs]

puts "=== Running Static Timing Analysis ==="
puts ""

# Report timing
report_checks -path_delay min_max -fields {slew cap input_pin net} -digits 4

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

# Calculate hot_ratio based on TNS / (WNS * estimated endpoints)
# This is an approximation - hot_ratio represents fraction of timing-critical area
if {$wns < 0} {
    # If we have violations, estimate hot_ratio from TNS/WNS ratio
    set estimated_violations [expr {abs($tns / $wns)}]
    # Assume ~100 endpoints max, calculate ratio
    set hot_ratio [expr {min(1.0, $estimated_violations / 100.0)}]
} else {
    set hot_ratio 0.0
}

puts "Hot ratio (estimated): [format %.4f $hot_ratio]"

# Generate timing report
set timing_report "$work_dir/timing_report.txt"
set fp [open $timing_report w]
puts $fp "=== Noodle 2 Real STA Report ==="
puts $fp "Design: GCD (placed)"
puts $fp "PDK: Sky130HD (130nm)"
puts $fp "Clock period: 10.0 ns (100 MHz)"
puts $fp ""
puts $fp "Timing Summary:"
puts $fp "  WNS: $wns ns ($wns_ps ps)"
puts $fp "  TNS: $tns ns ($tns_ps ps)"
puts $fp "  Hot ratio: [format %.4f $hot_ratio]"
puts $fp ""
puts $fp "=== End Report ==="
close $fp

puts "Generated timing report: $timing_report"

# Write JSON metrics
set metrics_file "$work_dir/metrics.json"
set fp [open $metrics_file w]
puts $fp "{"
puts $fp "  \"design\": \"gcd\","
puts $fp "  \"pdk\": \"sky130hd\","
puts $fp "  \"execution_type\": \"real_sta\","
puts $fp "  \"wns_ps\": $wns_ps,"
puts $fp "  \"tns_ps\": $tns_ps,"
puts $fp "  \"hot_ratio\": [format %.6f $hot_ratio],"
puts $fp "  \"clock_period_ns\": 10.0,"
if {$wns_ps < 0} {
    puts $fp "  \"status\": \"timing_violation\""
} else {
    puts $fp "  \"status\": \"timing_met\""
}
puts $fp "}"
close $fp

puts "Generated metrics: $metrics_file"

puts ""
puts "=== Real STA Execution Complete ==="
puts "WNS: $wns_ps ps"
puts "Hot ratio: [format %.4f $hot_ratio]"
if {$wns_ps < 0} {
    puts "Status: TIMING VIOLATION"
} else {
    puts "Status: TIMING MET"
}
puts "Return code: 0"

exit 0
