# Noodle 2 - Real STA Execution for Sky130 Microwatt
# This script runs ACTUAL OpenROAD Static Timing Analysis
# NO fake metrics - real STA on real design

puts "=== Noodle 2 Real STA Execution ==="
puts "Design: Microwatt OpenPOWER Core (placed)"
puts "PDK: Sky130HD (130nm)"
puts ""

# Paths inside ORFS container
set platform_dir "/OpenROAD-flow-scripts/flow/platforms/sky130hd"
set lib_file "$platform_dir/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
set lef_file "$platform_dir/lef/sky130_fd_sc_hd_merged.lef"

# Input/output paths
set snapshot_dir "/snapshot"
set work_dir "/work"
set odb_file "$snapshot_dir/microwatt_placed.odb"

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

# Create aggressive clock (4ns = 250 MHz for extreme demo)
create_clock -name ext_clk -period 4.0 [get_ports ext_clk]

# JTAG clock (slow)
create_clock -name jtag_tck -period 100.0 [get_ports jtag_tck]
set_clock_groups -name async_clks -asynchronous \
  -group [get_clocks ext_clk] \
  -group [get_clocks jtag_tck]

set_clock_uncertainty 0.25 [get_clocks ext_clk]

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

# Calculate hot_ratio based on timing health using a WNS-focused formula
if {$wns_ps < 0} {
    set wns_magnitude [expr {abs($wns_ps)}]
    # 8th power scaling: (|WNS_ps| / 4000)^8
    set wns_ratio [expr {$wns_magnitude / 4000.0}]
    set hot_ratio [expr {min(1.0, pow($wns_ratio, 8))}]
} else {
    set hot_ratio 0.0
}

puts "Hot ratio (estimated): [format %.4f $hot_ratio]"

# Generate timing report
set timing_report "$work_dir/timing_report.txt"
set fp [open $timing_report w]
puts $fp "=== Noodle 2 Real STA Report ==="
puts $fp "Design: Microwatt OpenPOWER Core (placed)"
puts $fp "PDK: Sky130HD (130nm)"
puts $fp "Clock period: 4.0 ns (250 MHz)"
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
puts $fp "  \"design\": \"microwatt\","
puts $fp "  \"pdk\": \"sky130hd\","
puts $fp "  \"execution_type\": \"real_sta\","
puts $fp "  \"wns_ps\": $wns_ps,"
puts $fp "  \"tns_ps\": $tns_ps,"
puts $fp "  \"hot_ratio\": [format %.6f $hot_ratio],"
puts $fp "  \"clock_period_ns\": 4.0,"
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
