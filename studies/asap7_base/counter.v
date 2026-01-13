// 4-bit Counter for Noodle 2 ASAP7 Demo
// Simple synchronous counter with enable

module counter (
    input  wire clk,
    input  wire rst_n,
    input  wire enable,
    output reg [3:0] count
);

always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        count <= 4'b0000;
    else if (enable)
        count <= count + 1'b1;
end

endmodule
