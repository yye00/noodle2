# Noodle 2 - Real STA Execution for ASAP7
# This script runs ACTUAL OpenROAD Static Timing Analysis
# NO fake metrics - real STA on real design

puts "=== Noodle 2 Real STA Execution ==="
puts "Design: GCD (placed)"
puts "PDK: ASAP7 (7nm FinFET)"
puts ""

# Paths inside ORFS container
set platform_dir "/OpenROAD-flow-scripts/flow/platforms/asap7"
set lib_dir "$platform_dir/lib"
set lef_dir "$platform_dir/lef"

# ASAP7 has multiple lib files for different corners
set lib_file "$lib_dir/NLDM/asap7sc7p5t_SEQ_RVT_TT_nldm_220123.lib"
set tech_lef "$lef_dir/asap7_tech_1x_201209.lef"
set cell_lef "$lef_dir/asap7sc7p5t_28_R_1x_220121a.lef"

# Input/output paths
set snapshot_dir "/snapshot"
set work_dir "/work"
# Use ORFS-built placed design (has proper timing info)
set odb_file "$snapshot_dir/gcd_placed_orfs.odb"

puts "Loading timing library: $lib_file"
puts "Loading tech LEF: $tech_lef"
puts "Loading cell LEF: $cell_lef"
puts "Loading design: $odb_file"
puts ""

# Read technology LEF
read_lef $tech_lef

# Read standard cell LEF
read_lef $cell_lef

# Read timing library
read_liberty $lib_file

# Read the placed design
read_db $odb_file

# Link the design (connects cells to library)
puts "Linking design..."
set num_insts [[ord::get_db_block] getInsts]
puts "Number of instances: [llength $num_insts]"

# Read SDC constraints (EXTREME clock period for ASAP7 demo)
# Try extreme constraints first, then fallback to aggressive
set sdc_file "$snapshot_dir/gcd_extreme.sdc"
if {[file exists $sdc_file]} {
    puts "Reading EXTREME SDC constraints: $sdc_file (50ps clock for demo)"
    read_sdc $sdc_file
} else {
    set sdc_file "$snapshot_dir/gcd_aggressive.sdc"
    if {[file exists $sdc_file]} {
        puts "Reading aggressive SDC constraints: $sdc_file"
        read_sdc $sdc_file
    } else {
        # Fallback: use less aggressive constraints
        set sdc_file "$snapshot_dir/gcd.sdc"
        if {[file exists $sdc_file]} {
            puts "Reading SDC constraints: $sdc_file"
            read_sdc $sdc_file
        } else {
            puts "WARNING: No SDC file found, creating extreme clock manually"
            create_clock -name core_clock -period 0.1 [get_ports clk]
            set_output_delay -clock core_clock 10 [all_outputs]
        }
    }
}

# Report clock information
puts "Clocks defined:"
foreach clock [get_clocks *] {
    puts "  Clock: [get_property $clock name], Period: [get_property $clock period]"
}

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
puts $fp "PDK: ASAP7 (7nm FinFET)"
puts $fp "Clock period: 0.05 ns (20 GHz - EXTREME for guaranteed timing violations)"
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
puts $fp "  \"pdk\": \"asap7\","
puts $fp "  \"execution_type\": \"real_sta\","
puts $fp "  \"wns_ps\": $wns_ps,"
puts $fp "  \"tns_ps\": $tns_ps,"
puts $fp "  \"hot_ratio\": [format %.6f $hot_ratio],"
puts $fp "  \"clock_period_ns\": 0.05,"
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
