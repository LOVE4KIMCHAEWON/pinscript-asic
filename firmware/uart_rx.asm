; UART receive demo: sample eight LSB-first bits at 115200baud @12MHz.
; PIO0 is RX input. After detecting start, capture byte into A, then
; display received byte on dedicated uo[7:0]; RX pin remains input.
; One-shot example, no oversampling, framing-error detection or FIFO.
    DIR 0x00
poll_start:
    IN
    TEST 0x01
    JNZ poll_start       ; wait until pin0 goes low (UART start)
    LDI 0x00             ; IN overwrote A, clear before accumulation
    LDX 8
    WAIT 150             ; data bit 0 center (incl following instructions)
bit:
    SHINR 0              ; receive LSB-first, shift bit into MSB
    WAIT 101             ; 104 clocks between sample points
    LOOP bit
    SHOWA                ; expose A on dedicated output pins uo[7:0]
    HALT
