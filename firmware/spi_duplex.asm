; SPI Mode 0 full-duplex: MSB-first TX=0x96, sample RX into B.
; 12 MHz system, 1 MHz SCK. A shifts transmitted bits only;
; B shifts received bits only. PIO0=SCK, PIO1=MOSI,
; PIO2=CSn, PIO3=MISO input. 6 clocks high/low per bit.
    OUT 0x04          ; preload idle before enabling outputs
    DIR 0x07          ; avoid a spurious CSn-low startup pulse
    LDI 0x96
    LDX 8
    OUT 0x00
bit:
    DBIT 1, msb, out
    WAIT 2
    XORO 0x01          ; SCK rising edge: slave output becomes valid
    SHINLB 3           ; capture input into B, preserve A
    SHL                ; transmit shift happens after MOSI was sampled
    WAIT 2
    XORO 0x01          ; SCK falling edge
    LOOP bit
    OUT 0x04           ; deselect
    SHOWB              ; report complete RX byte on dedicated uo pins
    HALT
