# ASAP7 Timing Constraints for Counter Design
# Clock period: 1.0 ns (1 GHz target for 7nm)

create_clock -name clk -period 1.0 [get_ports clk]

set_input_delay -clock clk 0.1 [get_ports rst_n]
set_input_delay -clock clk 0.1 [get_ports enable]

set_output_delay -clock clk 0.1 [get_ports count[*]]

set_load 0.005 [all_outputs]
set_driving_cell -lib_cell BUFx2_ASAP7_75t_R [all_inputs]
