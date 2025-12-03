module top (
    input  wire clk_25mhz,
    input  wire [6:0] btn,
    output wire [7:0] led,
    output wire ftdi_rxd, // FPGA TX
    input  wire ftdi_txd, // FPGA RX
    output wire wifi_en
);

    // Disable WiFi
    assign wifi_en = 1'b0;

    // Clock and Reset
    wire clk = clk_25mhz;
    // btn[1] is FIRE1, use as reset
    wire rst = btn[1];

    // LiteScope + UARTBone
    // The UARTBone now handles the FTDI pins.
    // We get inputs from the "user_inputs" CSR.
    
    // Unified Memory Signals
    wire [31:0] mem_rdata;
    wire mem_ack;
    
    // Scheme for user_inputs (32 bits):
    // [15:0]  : Address (16 bits)
    // [23:16] : Write Data (8 bits)
    // [24]    : Write Enable (1 = Write, 0 = Read)
    // [25]    : Request (1 = Active)
    
    unified_memory #(
        .MEM_SIZE_BYTES(65536)
    ) mem_inst (
        .clk(clk),
        .rst(rst),
        
        // Instruction Port (Unused)
        .if_addr(32'b0),
        .if_req(1'b0),
        .if_rdata(),
        .if_ack(),
        
        // Data Port
        .data_addr({16'b0, user_inputs[15:0]}),
        .data_wdata({24'b0, user_inputs[23:16]}),
        .data_size(2'b00), // Byte mode
        .data_we(user_inputs[24]),
        .data_req(user_inputs[25]),
        .data_rdata(mem_rdata),
        .data_ack(mem_ack)
    );

    // Display read byte on LEDs
    assign led = mem_rdata[7:0];
    
    // Probe signals
    assign probe_signals[15:0]  = user_inputs[15:0]; // Probe Address
    assign probe_signals[23:16] = mem_rdata[7:0];    // Probe Read Data
    assign probe_signals[24]    = mem_ack;           // Probe Ack
    assign probe_signals[31:25] = 0;

    litescope_core litescope_inst (
        .clk_25mhz(clk),
        .rst(rst),
        .serial_rx(ftdi_txd), // UARTBone RX (from PC)
        .serial_tx(ftdi_rxd), // UARTBone TX (to PC)
        .user_probe(probe_signals),
        .user_inputs_port(user_inputs),
        .user_outputs_port({24'b0, mem_rdata[7:0]}) // Send read byte back to PC
    );

endmodule
