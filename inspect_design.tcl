#!/usr/bin/env tclsh
# Inspect design to understand critical paths

puts "=== Design Inspection ==="

# Load libs and design
read_lef /OpenROAD-flow-scripts/flow/platforms/nangate45/lef/NangateOpenCellLibrary.macro.mod.lef
read_liberty /OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib
read_db /snapshot/gcd_placed.odb

# Get design info
puts "Design: [get_name [ord::get_db_block]]"
puts "Instance count: [[ord::get_db_block] getInstCount]"
puts "Net count: [[ord::get_db_block] getNetCount]"

# Create clock with very short period to see critical paths
create_clock -name clk -period 0.001 [get_ports clk]

# Report longest paths without output delay
report_checks -path_delay max -fields {slew cap input_pin net} -format full_clock_expanded -digits 4

puts "=== End Inspection ==="
exit 0
