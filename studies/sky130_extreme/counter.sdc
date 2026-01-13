# Simple timing constraints for counter design
# Sky130 PDK - using sky130_fd_sc_hd standard cell library
# Clock period: 10ns (100 MHz)

create_clock -name clk -period 10.0 [get_ports clk]
set_clock_uncertainty 0.5 [get_clocks clk]

# Input delays (relative to clock)
set_input_delay -clock clk 2.0 [get_ports rst_n]
set_input_delay -clock clk 2.0 [get_ports enable]

# Output delays (relative to clock)
set_output_delay -clock clk 2.0 [get_ports count*]

# Drive strengths - using Sky130 standard cells
# Sky130 cells: sky130_fd_sc_hd__buf_1 is a basic buffer in the HD library
set_driving_cell -lib_cell sky130_fd_sc_hd__buf_1 -pin X [all_inputs]

# Load capacitance (in pF, typical for Sky130)
set_load 0.05 [all_outputs]
