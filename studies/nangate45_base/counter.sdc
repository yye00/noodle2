# Simple timing constraints for counter design
# Clock period: 10ns (100 MHz)

create_clock -name clk -period 10.0 [get_ports clk]
set_clock_uncertainty 0.5 [get_clocks clk]

# Input delays (relative to clock)
set_input_delay -clock clk 2.0 [get_ports rst_n]
set_input_delay -clock clk 2.0 [get_ports enable]

# Output delays (relative to clock)
set_output_delay -clock clk 2.0 [get_ports count*]

# Drive strengths
set_driving_cell -lib_cell BUF_X1 -pin Z [all_inputs]

# Load capacitance
set_load 0.05 [all_outputs]
