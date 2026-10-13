; I2C 7-bit address 0x50 + W (0xA0), then byte 0x33.
; PIO0=SCL, PIO1=SDA. Add EXTERNAL pull-ups to both pins.
; All gpio_out bits are zero; 1 in gpio_oe sinks bus, 0 releases it.
; uo[6] is ZERO_FLAG, 1 on ACK, 0 on NACK after last TEST.
    OUT 0x00
    DIR 0x00       ; release both lines, IDLE
    WAIT 8
    DIR 0x02       ; START: SDA low while SCL high
    WAIT 8
    DIR 0x03       ; SCL low
    LDI 0xA0
    LDX 8
address_bit:
    DBIT 1, msb, oe, invert   ; open drain: 0=drive low, 1=release
    WAIT 15
    XORD 0x01      ; SCL release/high
    WAIT 15
    XORD 0x01      ; SCL drive low
    SHL
    LOOP address_bit
    DBIT 1, lsb, oe           ; A=0 after eight shifts; release SDA
    WAIT 15
    XORD 0x01                ; release SCL for ACK
    WAIT 8
    IN
    TEST 0x02                 ; ACK when SDA==0
    XORD 0x01                ; drive SCL low
    JNZ nack

    LDI 0x33
    LDX 8
data_bit:
    DBIT 1, msb, oe, invert
    WAIT 15
    XORD 0x01
    WAIT 15
    XORD 0x01
    SHL
    LOOP data_bit
    DBIT 1, lsb, oe
    WAIT 15
    XORD 0x01
    WAIT 8
    IN
    TEST 0x02
    XORD 0x01
    JNZ nack
stop:
    DIR 0x03       ; SDA low, SCL low
    WAIT 15
    DIR 0x02       ; SCL high, SDA low
    WAIT 15
    DIR 0x00       ; STOP: SDA released while SCL high
    HALT
nack:
    DIR 0x03
    WAIT 15
    DIR 0x02
    WAIT 15
    DIR 0x00
    HALT
