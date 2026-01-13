# ASAP7 Timing Constraints for GCD Design
# Aggressive clock period: 0.5 ns (2 GHz target for 7nm) to create violations

create_clock -name clk -period 0.5 [get_ports clk]

# Set input delays
set_input_delay -clock clk 0.05 [get_ports req_val]
set_input_delay -clock clk 0.05 [get_ports reset]
set_input_delay -clock clk 0.05 [get_ports {req_msg[*]}]
set_input_delay -clock clk 0.05 [get_ports resp_rdy]

# Set output delays
set_output_delay -clock clk 0.05 [get_ports resp_val]
set_output_delay -clock clk 0.05 [get_ports req_rdy]
set_output_delay -clock clk 0.05 [get_ports {resp_msg[*]}]

# Set loads and driving cells
set_load 0.005 [all_outputs]
