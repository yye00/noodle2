# ASAP7 Ibex Timing Constraints - EXTREME for timing violations
# Target: Create significant WNS/TNS violations for ECO optimization testing

current_design ibex_core

# Aggressive clock period - 0.1ns = 100ps (10 GHz) to create severe timing violations
# SDC uses nanoseconds as the default time unit
# Original: 1.0ns (1000ps), current WNS with 1.0ns clock is -66.73ps
# With 0.1ns (100ps) clock, expect massive WNS violations
set clk_period 0.1
set clk_name core_clock

create_clock -name $clk_name -period $clk_period [get_ports {clk_i}]

# Tight clock uncertainty (5ps = 0.005ns)
set_clock_uncertainty 0.005 [get_clocks $clk_name]

# Aggressive input/output delays (20% of clock period)
set io_delay [expr $clk_period * 0.2]

# Set input delays on all inputs
set_input_delay $io_delay -clock [get_clocks $clk_name] [all_inputs]

# Set output delays on all outputs
set_output_delay $io_delay -clock [get_clocks $clk_name] [all_outputs]

# Don't touch clock port
set_false_path -from [get_ports clk_i]
set_false_path -from [get_ports rst_ni]
