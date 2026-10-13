; 8-bit SPI mode-0 master, send 0x96; PIO0=SCK, PIO1=MOSI,
; PIO2=CSn, PIO3=MISO (unused in TX example).
; At 12 MHz core clock: SCK 1 MHz, 6 clocks high and low after first bit.
    OUT 0x04       ; preload CSn=1 before enabling outputs
    DIR 0x07       ; SCK=0, MOSI=0, no spurious CSn-low pulse
    LDI 0x96
    LDX 8
    OUT 0x00       ; assert CSn
bit:
    DBIT 1, msb, out
    WAIT 1         ; MOSI setup
    XORO 0x01      ; rising SCK: sample MOSI
    WAIT 4         ; high for 6 clocks
    XORO 0x01      ; falling SCK
    SHL
    LOOP bit
    OUT 0x04       ; deselect
    HALT
