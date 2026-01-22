# Noodle 2 - Real STA Execution for ASAP7 Ibex Extreme
# This script runs ACTUAL OpenROAD Static Timing Analysis
# NO fake metrics - real STA on real design

puts "=== Noodle 2 Real STA Execution ==="
puts "Design: Ibex RISC-V Core (placed)"
puts "PDK: ASAP7 (7nm FinFET)"
puts ""

# Paths inside ORFS container
set platform_dir "/OpenROAD-flow-scripts/flow/platforms/asap7"
set lib_dir "$platform_dir/lib/NLDM"

# ASAP7 library files (FF corner for worst-case timing)
set lib_files [list \
    "$lib_dir/asap7sc7p5t_AO_RVT_FF_nldm_211120.lib.gz" \
    "$lib_dir/asap7sc7p5t_INVBUF_RVT_FF_nldm_220122.lib.gz" \
    "$lib_dir/asap7sc7p5t_OA_RVT_FF_nldm_211120.lib.gz" \
    "$lib_dir/asap7sc7p5t_SIMPLE_RVT_FF_nldm_211120.lib.gz" \
    "$lib_dir/asap7sc7p5t_SEQ_RVT_FF_nldm_220123.lib" \
]

# Input/output paths (mounted by Docker)
set snapshot_dir "/snapshot"
set work_dir "/work"
set odb_file "$snapshot_dir/ibex_placed.odb"
set sdc_file "$snapshot_dir/ibex_extreme.sdc"

puts "Loading design: $odb_file"
puts "Loading SDC: $sdc_file"
puts ""

# Read timing libraries
foreach lib $lib_files {
    puts "Loading library: $lib"
    read_liberty $lib
}

# Read the placed design
read_db $odb_file

# Source RC settings for parasitics
source "$platform_dir/setRC.tcl"

# Read SDC constraints (EXTREME 100ps clock)
read_sdc $sdc_file

# Estimate parasitics for placed design
estimate_parasitics -placement

# Run timing analysis
puts ""
puts "=== TIMING ANALYSIS RESULTS ==="
puts ""

# Report worst slack
set wns [sta::worst_slack -max]
puts "WNS (Worst Negative Slack): $wns ps"

# Report total negative slack
set tns [sta::total_negative_slack -max]
puts "TNS (Total Negative Slack): $tns ps"

# Report design area
report_design_area

# Report check types for DRV violations
report_check_types -max_slew -max_cap -max_fanout

# Write metrics to file for Noodle 2 to parse
set metrics_file "$work_dir/sta_metrics.json"
set fp [open $metrics_file "w"]
puts $fp "{"
puts $fp "  \"wns_ps\": $wns,"
puts $fp "  \"tns_ps\": $tns,"
puts $fp "  \"execution_type\": \"real_sta\""
puts $fp "}"
close $fp

puts ""
puts "Metrics written to: $metrics_file"
puts "=== STA Complete ==="

exit
