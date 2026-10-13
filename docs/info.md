# PinScript protocol emulator ASIC

## How it works

PinScript is an SPI-reprogrammable, 16-bit-instruction protocol I/O sequencer. It provides eight independent bidirectional GPIO with deterministic instructions for sampling, setting pin values, setting output-enable, branching on input samples and delaying an exact number of clock cycles. Unlike a fixed UART/I²C/SPI controller, its protocol is defined in firmware that can be changed after fabrication.

The chip has a 64-word program store, independent eight-bit A and B accumulators, an eight-bit X loop counter, an eight-bit output register, an eight-bit OE register, a six-bit PC, and a zero flag. Five sample programs implement UART transmit/receive, SPI Mode 0 transmit/full-duplex receive and I²C open-drain writes of an address byte plus one data byte with ACK detection. Input shift instructions capture serial bits into A or B; SHOWA/SHOWB display the selected byte on the dedicated output bus.

## How to test

Use a 12 MHz system clock. Keep `rst_n` low for at least two rising edges, then release. Drive configuration SPI on ui0=SCLK, ui1=MOSI, ui2=CSn (idle CS high and clock low). A single CS-low frame beginning with `01 00` followed by high/low bytes of each instruction loads memory. Release CS, then a new frame `[02,00]` starts execution. A `[03]` frame halts.

With `firmware/uart_tx.asm` loaded, connect logic analyzer to bidirectional pin 0 and observe UART `0x55`, 115200 baud 8N1. With `firmware/uart_rx.asm`, present an 8N1 UART frame on uio0 and read the received byte from `uo[7:0]` after the program halts. With `firmware/spi_mode0.asm` loaded, observe SPI clock (uio0), MOSI (uio1) and CSn (uio2). With `firmware/spi_duplex.asm`, also connect MISO at uio3; the received byte appears on `uo[7:0]`. With `firmware/i2c_write.asm`, connect open-drain SDA/SCL pull-ups externally and a device at 7-bit address 0x50. Never exceed Tiny Tapeout I/O ratings.

## Pinout

| Input ui | Signal |
| --- | --- |
| 0 | Configuration SCLK |
| 1 | Configuration MOSI |
| 2 | Configuration CSn |
| 3–7 | unused/reserved |

| Output uo | Signal |
| --- | --- |
| 0–5 | CPU program counter in debug mode |
| 6 | CPU zero flag in debug mode |
| 7 | CPU running flag in debug mode |

After executing `SHOWA` or `SHOWB`, all `uo[7:0]` display the selected accumulator until the next RUN/WRITE/HALT/reset.

| Bidirectional uio | Signal |
| --- | --- |
| 0–7 | Firmware-controlled protocol I/O |

## External hardware

Programming requires an SPI master and a system clock. I²C requires appropriate external pull-ups and a compatible target device. All connections must satisfy chip I/O voltage specifications.

## Project status

Prototype RTL + firmware and 16 passing Python reference tests; 10 Cocotb RTL tests and automated generic synthesis are provided but not yet executed in this environment. PDK mapping, STA, GDS and physical sign-off remain unverified.
