# ASAP7 GCD Timing Constraints - EXTREME for timing violations
# Target: Create severe timing violations for demo

# Design name
current_design gcd

# Clock definition - EXTREMELY aggressive
# GCD can meet ~100ps, so 10ps will create severe violations
set clk_period 0.010
set clk_name core_clock  

# Create clock on clk port
create_clock -name $clk_name -period $clk_period [get_ports clk]

# Set clock uncertainty (very tight)
set_clock_uncertainty 0.002 [get_clocks $clk_name]

# Input delay constraints - all inputs constrained to clock
set_input_delay -clock $clk_name [expr $clk_period * 0.2] [get_ports req_msg*]
set_input_delay -clock $clk_name [expr $clk_period * 0.2] [get_ports req_val]
set_input_delay -clock $clk_name [expr $clk_period * 0.2] [get_ports reset]

# Output delay constraints  
set_output_delay -clock $clk_name [expr $clk_period * 0.2] [get_ports resp_msg*]
set_output_delay -clock $clk_name [expr $clk_period * 0.2] [get_ports req_rdy]

# Disable timing through reset path for cleaner analysis
set_false_path -from [get_ports reset]
