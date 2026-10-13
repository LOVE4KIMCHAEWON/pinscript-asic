; Transmit 0x55 (ASCII 'U'), 8N1, TX=PIO0.
; System clock 12 MHz: 104 cycles/bit = 115385 baud (0.16% fast).
; Program may be rerun with SPI RUN command. Clock latency is deterministic.
    OUT 0x01       ; preload idle high before enabling TX
    DIR 0x01       ; avoid a spurious low startup pulse
    LDI 0x55
    LDX 8
    OUT 0x00       ; start bit
    WAIT 102       ; start->data: 104 clocks
bit:
    DBIT 0, lsb, out
    WAIT 100       ; between bits: 104 clocks including SHR/LOOP/DBIT
    SHR
    LOOP bit
    OUT 0x01       ; stop bit
    WAIT 102
    HALT
