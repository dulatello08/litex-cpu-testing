//
// unified_memory.sv
// NeoCore 16x32 CPU - Unified Von Neumann Memory (BRAM-backed)
//
// Single unified memory for both instructions and data.
// Re-implemented using 16 interleaved memory banks via GENERATE blocks
// to force explicit Block RAM inference on ECP5.
//
// Organization:
//   16 Banks, interleaved by byte.
//   Bank 0 stores addresses 0, 16, 32...
//   Bank 1 stores addresses 1, 17, 33...

module unified_memory #(
    parameter MEM_SIZE_BYTES = 65536,  // 64 KB default
    parameter ADDR_WIDTH = 32
)(
    input  logic        clk,
    input  logic        rst,

    // Instruction fetch port (Port A of BRAMs)
    input  logic [ADDR_WIDTH-1:0] if_addr,
    input  logic                  if_req,
    output logic [127:0]          if_rdata,
    output logic                  if_ack,

    // Data access port (Port B of BRAMs)
    input  logic [ADDR_WIDTH-1:0] data_addr,
    input  logic [31:0]           data_wdata,
    input  logic [1:0]            data_size,  // 00=byte, 01=half, 10=word
    input  logic                  data_we,
    input  logic                  data_req,
    output logic [31:0]           data_rdata,
    output logic                  data_ack
);

    localparam BANKS = 16;
    localparam BANK_DEPTH = MEM_SIZE_BYTES / BANKS;
    localparam BANK_ADDR_W = $clog2(BANK_DEPTH);
    localparam BANK_SEL_W = 4; // log2(16)

    // -------------------------------------------------------------------------
    // Address / Control Logic (Combinational)
    // -------------------------------------------------------------------------
    
    // -- Port A (Instruction) --
    logic [BANK_ADDR_W-1:0] if_row_base;
    logic [BANK_SEL_W-1:0]  if_offset;
    logic [BANK_SEL_W-1:0]  if_offset_reg;
    logic [BANK_ADDR_W-1:0] if_bank_addrs [0:BANKS-1];
    
    assign if_row_base = if_addr[ADDR_WIDTH-1 : BANK_SEL_W];
    assign if_offset   = if_addr[BANK_SEL_W-1 : 0];

    always_comb begin
        for (int i = 0; i < BANKS; i++) begin
            if (i < if_offset) 
                if_bank_addrs[i] = if_row_base + 1;
            else 
                if_bank_addrs[i] = if_row_base;
        end
    end

    // -- Port B (Data) --
    logic [BANK_ADDR_W-1:0] data_row_base;
    logic [BANK_SEL_W-1:0]  data_offset;
    logic [BANK_SEL_W-1:0]  data_offset_reg;
    logic [1:0]             data_size_reg;
    logic [BANK_ADDR_W-1:0] data_bank_addrs [0:BANKS-1];
    logic [BANKS-1:0]       data_bank_we;
    logic [7:0]             data_bank_wdata [0:BANKS-1];

    assign data_row_base = data_addr[ADDR_WIDTH-1 : BANK_SEL_W];
    assign data_offset   = data_addr[BANK_SEL_W-1 : 0];
    
    // Port B Address Calculation
    always_comb begin
        for (int i = 0; i < BANKS; i++) begin
            if (i < data_offset) 
                data_bank_addrs[i] = data_row_base + 1;
            else 
                data_bank_addrs[i] = data_row_base;
        end
    end

    // Port B Write Enable / Data Rotation Logic
    always_comb begin
        data_bank_we = '0;
        
        // 1. Write Enables
        if (data_we && data_req) begin
            logic [15:0] base_mask;
            case (data_size)
                2'b00: base_mask = 16'b0000_0000_0000_0001; // Byte
                2'b01: base_mask = 16'b0000_0000_0000_0011; // Half
                2'b10: base_mask = 16'b0000_0000_0000_1111; // Word
                default: base_mask = '0;
            endcase
            data_bank_we = (base_mask << data_offset) | (base_mask >> (16 - data_offset));
        end
        
        // 2. Write Data Rotation
        // WData is 32-bits (4 bytes). We place them at MSB of 128-bit structure and rotate.
        // Similar to previous implementation, expanded here for clarity if needed, 
        // but simple loop works fine for synthesis.
        begin
            logic [127:0] wdata_exp;
            logic [127:0] wdata_rot;
            wdata_exp = {data_wdata, 96'h0};
            wdata_rot = (wdata_exp >> (data_offset * 8)) | (wdata_exp << ((16 - data_offset) * 8));
            
            for (int i = 0; i < BANKS; i++) begin
                data_bank_wdata[i] = wdata_rot[127 - (i*8) -: 8];
            end
        end
    end

    // -------------------------------------------------------------------------
    // Memory Generation
    // -------------------------------------------------------------------------
    
    // Wires to carry read data out of the generate block
    logic [7:0] if_bank_rdata [0:BANKS-1];
    logic [7:0] data_bank_rdata [0:BANKS-1];

    generate
        for (genvar i = 0; i < BANKS; i++) begin : bank_gen
            // Local memory array for this bank
            // (* ram_style = "block" *) // Optional hint for Yosys
            logic [7:0] mem [0:BANK_DEPTH-1];
            logic [7:0] rdata_a;
            logic [7:0] rdata_b;
            
            // Port A (Instruction Fetch) - Read Only
            always_ff @(posedge clk) begin
                rdata_a <= mem[if_bank_addrs[i]];
            end
            
            // Port B (Data Access) - Read / Write
            always_ff @(posedge clk) begin
                if (data_bank_we[i]) begin
                    mem[data_bank_addrs[i]] <= data_bank_wdata[i];
                end
                rdata_b <= mem[data_bank_addrs[i]];
            end
            
            assign if_bank_rdata[i] = rdata_a;
            assign data_bank_rdata[i] = rdata_b;
        end
    endgenerate

    // -------------------------------------------------------------------------
    // Output Registers / Alignment Logic
    // -------------------------------------------------------------------------

    // Port A Output Control
    always_ff @(posedge clk) begin
        if (rst) begin
            if_ack <= 1'b0;
            if_offset_reg <= '0;
        end else begin
            if (if_req) begin
                if_offset_reg <= if_offset;
                if_ack <= 1'b1;
            end else begin
                if_ack <= 1'b0;
            end
        end
    end
    
    // Port A Alignment (Combinational)
    always_comb begin
        logic [127:0] rdata_raw;
        logic [127:0] rdata_aligned;
        
        for (int i = 0; i < BANKS; i++) begin
            rdata_raw[127 - (i*8) -: 8] = if_bank_rdata[i];
        end
        
        rdata_aligned = (rdata_raw << (if_offset_reg * 8)) | (rdata_raw >> ((16 - if_offset_reg) * 8));
        if_rdata = rdata_aligned;
    end

    // Port B Output Control
    always_ff @(posedge clk) begin
        if (rst) begin
            data_ack <= 1'b0;
            data_offset_reg <= '0;
            data_size_reg <= '0;
        end else begin
            if (data_req) begin
                data_offset_reg <= data_offset;
                data_size_reg <= data_size;
                data_ack <= 1'b1;
            end else begin
                data_ack <= 1'b0;
            end
        end
    end

    // Port B Alignment (Combinational)
    always_comb begin
        logic [127:0] rdata_raw;
        logic [127:0] rdata_aligned;
        
        for (int i = 0; i < BANKS; i++) begin
            rdata_raw[127 - (i*8) -: 8] = data_bank_rdata[i];
        end
        
        // Rotate LEFT
        rdata_aligned = (rdata_raw << (data_offset_reg * 8)) | (rdata_raw >> ((16 - data_offset_reg) * 8));
        
        case (data_size_reg)
            2'b00: data_rdata = {24'h0, rdata_aligned[127:120]};
            2'b01: data_rdata = {16'h0, rdata_aligned[127:112]};
            2'b10: data_rdata = rdata_aligned[127:96];
            default: data_rdata = 32'h0;
        endcase
    end

endmodule : unified_memory

