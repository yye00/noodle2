# ASAP7 Timing Constraints for GCD Design (Aggressive)
# Based on ORFS constraint.sdc but with aggressive clock for violations

current_design gcd

set clk_name core_clock
set clk_port_name clk
# Aggressive clock: 150ps (vs normal 310ps) to create timing violations
set clk_period 150
set clk_io_pct 0.2

set clk_port [get_ports $clk_port_name]

create_clock -name $clk_name -period $clk_period $clk_port

set non_clock_inputs [lsearch -inline -all -not -exact [all_inputs] $clk_port]

set_input_delay [expr $clk_period * $clk_io_pct] -clock $clk_name $non_clock_inputs
set_output_delay [expr $clk_period * $clk_io_pct] -clock $clk_name [all_outputs]
