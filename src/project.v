// SPDX-License-Identifier: Apache-2.0
// PinScript: a firmware-defined, deterministic 8-pin protocol engine.
// Tiny Tapeout IHP CMOS5L top-level. All state is clocked by clk.
`default_nettype none
module tt_um_pinscript (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);
    // ui_in[2:0]: asynchronous configuration SPI (CS_n, MOSI, SCLK).
    // Configuration SPI must be considerably slower than clk.
    reg [2:0] sck_sync;
    reg [2:0] cs_sync;
    reg [2:0] mosi_sync;
    wire spi_rising = ~sck_sync[2] & sck_sync[1];
    wire spi_selected = ~cs_sync[2];

    // 64 x 16 programmable instruction store. Contents are unspecified
    // after reset; load the program over SPI before asserting RUN.
    reg [15:0] code_mem [0:63];
    reg [5:0] pc;
    wire [15:0] ir = code_mem[pc];
    reg [7:0] a;
    reg [7:0] b;  // independent receive accumulator for true full-duplex SPI
    reg [7:0] x;
    reg [7:0] gpio_out;
    reg [7:0] gpio_oe;
    reg [7:0] result_byte;
    reg       show_result;
    reg       z;
    reg       running;
    reg [7:0] wait_left;

    // SPI state machine: CMD, ADDRESS, HI_BYTE, LO_BYTE, ENTRY, IGNORE.
    localparam [2:0] ST_CMD=3'd0, ST_ADDR=3'd1, ST_HI=3'd2,
                     ST_LO=3'd3, ST_ENTRY=3'd4, ST_IGNORE=3'd5;
    reg [2:0] spi_state;
    reg [2:0] spi_bits;
    reg [7:0] spi_shift;
    reg [7:0] hi_byte;
    reg [5:0] wr_addr;
    wire [7:0] received_byte = {spi_shift[6:0], mosi_sync[1]};

    // Protocol pins are controlled solely by firmware. Debug/captured
    // result are multiplexed onto dedicated uo_out pins.
    assign uio_out = gpio_out;
    assign uio_oe  = gpio_oe;
    assign uo_out  = show_result ? result_byte : {running, z, pc};

    always @(posedge clk) begin
        if (!rst_n) begin
            sck_sync  <= 3'b000;
            cs_sync   <= 3'b111;
            mosi_sync <= 3'b000;
            spi_state <= ST_CMD;
            spi_bits  <= 3'b000;
            spi_shift <= 8'b0;
            hi_byte   <= 8'b0;
            wr_addr   <= 6'b0;
            pc        <= 6'b0;
            a         <= 8'b0;
            b         <= 8'b0;
            x         <= 8'b0;
            gpio_out  <= 8'b0;
            gpio_oe   <= 8'b0;
            result_byte <= 8'b0;
            show_result <= 1'b0;
            z         <= 1'b1;
            running   <= 1'b0;
            wait_left <= 8'b0;
        end else begin
            sck_sync  <= {sck_sync[1:0], ui_in[0]};
            mosi_sync <= {mosi_sync[1:0], ui_in[1]};
            cs_sync   <= {cs_sync[1:0], ui_in[2]};

            // Execution: a 1-cycle instruction, except WAIT N takes N+1
            // cycles total. The output latch changes on the execute edge.
            if (ena && running) begin
                if (wait_left != 8'd0) begin
                    wait_left <= wait_left - 8'd1;
                end else begin
                    pc <= pc + 6'd1;
                    case (ir[15:12])
                        4'h0: begin
                            // 0x0000 NOP; 0x0001 HALT.
                            if (ir[0]) running <= 1'b0;
                        end
                        4'h1: begin a <= ir[7:0]; z <= (ir[7:0] == 8'd0); end
                        4'h2: x <= ir[7:0];
                        4'h3: gpio_out <= ir[7:0];
                        4'h4: gpio_oe <= ir[7:0];
                        4'h5: begin
                            // Separate B accumulator supports simultaneous
                            // transmit from A and receive into B.
                            // ir[10] selects B for shifts and SHOW.
                            case (ir[9:8])
                                2'b01: begin
                                    if (ir[10]) begin
                                        b <= {b[6:0], uio_in[ir[2:0]]};
                                        z <= ({b[6:0], uio_in[ir[2:0]]} == 8'd0);
                                    end else begin
                                        a <= {a[6:0], uio_in[ir[2:0]]};
                                        z <= ({a[6:0], uio_in[ir[2:0]]} == 8'd0);
                                    end
                                end
                                2'b10: begin
                                    if (ir[10]) begin
                                        b <= {uio_in[ir[2:0]], b[7:1]};
                                        z <= ({uio_in[ir[2:0]], b[7:1]} == 8'd0);
                                    end else begin
                                        a <= {uio_in[ir[2:0]], a[7:1]};
                                        z <= ({uio_in[ir[2:0]], a[7:1]} == 8'd0);
                                    end
                                end
                                2'b11: begin
                                    result_byte <= ir[10] ? b : a;
                                    show_result <= 1'b1;
                                end
                                default: gpio_out <= a;
                            endcase
                        end
                        4'h6: begin a <= uio_in; z <= (uio_in == 8'd0); end
                        4'h7: begin
                            if (ir[0]) begin
                                a <= {a[6:0], 1'b0};
                                z <= (a[6:0] == 7'd0);
                            end else begin
                                a <= {1'b0, a[7:1]};
                                z <= (a[7:1] == 7'd0);
                            end
                        end
                        4'h8: begin
                            if (x != 8'd0) begin
                                x <= x - 8'd1;
                                if (x != 8'd1) pc <= ir[5:0];
                            end
                        end
                        4'h9: pc <= ir[5:0];
                        4'hA: if (z) pc <= ir[5:0];
                        4'hB: if (!z) pc <= ir[5:0];
                        4'hC: wait_left <= ir[7:0];
                        4'hD: begin
                            // DBIT pin: A[0] or A[7], optionally inverted,
                            // writes the output data latch or direction latch.
                            if (ir[4])
                                gpio_oe[ir[2:0]] <=
                                    (ir[3] ? a[7] : a[0]) ^ ir[5];
                            else
                                gpio_out[ir[2:0]] <=
                                    (ir[3] ? a[7] : a[0]) ^ ir[5];
                        end
                        4'hE: z <= ((a & ir[7:0]) == 8'd0);
                        4'hF: begin
                            // Low 7 pins can be toggled atomically; bit 7
                            // selects OE register rather than OUT register.
                            if (ir[7]) gpio_oe <= gpio_oe ^ {1'b0, ir[6:0]};
                            else gpio_out <= gpio_out ^ {1'b0, ir[6:0]};
                        end
                        default: ;
                    endcase
                end
            end

            // SPI is independent of program execution. On a WRITE command
            // or HALT command, stop the engine. Firmware may run in parallel
            // with a non-WRITE SPI frame, but changing code forces a pause.
            if (!spi_selected) begin
                spi_state <= ST_CMD;
                spi_bits <= 3'b000;
                spi_shift <= 8'b0;
            end else if (spi_rising) begin
                spi_shift <= received_byte;
                spi_bits <= spi_bits + 3'd1;
                if (spi_bits == 3'd7) begin
                    case (spi_state)
                        ST_CMD: begin
                            case (received_byte)
                                8'h01: begin
                                    spi_state <= ST_ADDR;
                                    running <= 1'b0;
                                    wait_left <= 8'b0;
                                    show_result <= 1'b0;
                                end
                                8'h02: spi_state <= ST_ENTRY;
                                8'h03: begin
                                    running <= 1'b0;
                                    wait_left <= 8'b0;
                                    show_result <= 1'b0;
                                    spi_state <= ST_IGNORE;
                                end
                                default: spi_state <= ST_IGNORE;
                            endcase
                        end
                        ST_ADDR: begin
                            wr_addr <= received_byte[5:0];
                            spi_state <= ST_HI;
                        end
                        ST_HI: begin
                            hi_byte <= received_byte;
                            spi_state <= ST_LO;
                        end
                        ST_LO: begin
                            code_mem[wr_addr] <= {hi_byte, received_byte};
                            wr_addr <= wr_addr + 6'd1;
                            spi_state <= ST_HI;
                        end
                        ST_ENTRY: begin
                            pc <= received_byte[5:0];
                            a <= 8'b0;
                            b <= 8'b0;
                            x <= 8'b0;
                            gpio_out <= 8'b0;
                            gpio_oe <= 8'b0;
                            result_byte <= 8'b0;
                            show_result <= 1'b0;
                            z <= 1'b1;
                            wait_left <= 8'b0;
                            running <= 1'b1;
                            spi_state <= ST_IGNORE;
                        end
                        default: ;
                    endcase
                end
            end
        end
    end
    // Unused top input pins are reserved for future expansion.
    wire _unused = &{ui_in[7:3], 1'b0};
endmodule
`default_nettype wire
