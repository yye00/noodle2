# Microwatt Extreme - Aggressive 4ns clock (250 MHz) for timing closure demo
current_design microwatt

set clk_name ext_clk
set clk_port_name ext_clk
set clk_period 4.0
set clk_io_pct 0.2

set clk_port [get_ports $clk_port_name]
create_clock -name $clk_name -period $clk_period $clk_port

# IO constraints
set_input_delay [expr $clk_period * $clk_io_pct] -clock $clk_name [all_inputs]
set_output_delay [expr $clk_period * $clk_io_pct] -clock $clk_name [all_outputs]

# JTAG clock (kept slow)
set jtag_clk_name jtag_tck
create_clock -name $jtag_clk_name -period 100.0 [get_ports jtag_tck]
set_clock_groups -name group1 -logically_exclusive \
  -group [get_clocks $jtag_clk_name] \
  -group [get_clocks $clk_name]

set_max_fanout 10 [current_design]
set_driving_cell -lib_cell sky130_fd_sc_hd__inv_2 -pin Y [all_inputs]
set_load 0.03344 [all_outputs]

set_clock_uncertainty 0.25 [get_clocks $clk_name]
set_clock_transition 0.15 [get_clocks $clk_name]

set_timing_derate -early 0.95
set_timing_derate -late 1.05
