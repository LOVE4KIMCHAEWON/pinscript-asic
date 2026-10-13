"""PinScript ISA executable specification; does not simulate Verilog event scheduling.
Used for independent software-level firmware tests. Cycle numbers start at zero.
"""
from dataclasses import dataclass

@dataclass
class Core:
    code: list[int]
    pc: int = 0
    a: int = 0
    b: int = 0
    x: int = 0
    gpio_out: int = 0
    gpio_oe: int = 0
    result_byte: int = 0
    show_result: bool = False
    z: bool = True
    running: bool = True
    wait_left: int = 0
    cycles: int = 0

    def tick(self, pins: int = 0xff):
        if self.running:
            if self.wait_left:
                self.wait_left -= 1
            else:
                ir = self.code[self.pc]
                op, imm = ir >> 12, ir & 0xff
                self.pc = (self.pc + 1) & 63
                if op == 0:
                    if ir & 1: self.running = False
                elif op == 1:
                    self.a = imm; self.z = (imm == 0)
                elif op == 2: self.x = imm
                elif op == 3: self.gpio_out = imm
                elif op == 4: self.gpio_oe = imm
                elif op == 5:
                    mode = (ir >> 8) & 3
                    select_b = bool(ir & 0x0400)
                    if mode == 1:
                        if select_b:
                            self.b = ((self.b << 1) & 0xff) | ((pins >> (ir & 7)) & 1)
                            self.z = (self.b == 0)
                        else:
                            self.a = ((self.a << 1) & 0xff) | ((pins >> (ir & 7)) & 1)
                            self.z = (self.a == 0)
                    elif mode == 2:
                        if select_b:
                            self.b = (self.b >> 1) | (((pins >> (ir & 7)) & 1) << 7)
                            self.z = (self.b == 0)
                        else:
                            self.a = (self.a >> 1) | (((pins >> (ir & 7)) & 1) << 7)
                            self.z = (self.a == 0)
                    elif mode == 3:
                        self.result_byte = self.b if select_b else self.a
                        self.show_result = True
                    else:
                        self.gpio_out = self.a
                elif op == 6:
                    self.a = pins; self.z = (pins == 0)
                elif op == 7:
                    self.a = ((self.a << 1) & 0xff) if (ir & 1) else self.a >> 1
                    self.z = (self.a == 0)
                elif op == 8:
                    if self.x:
                        self.x -= 1
                        if self.x: self.pc = ir & 63
                elif op == 9: self.pc = ir & 63
                elif op == 10:
                    if self.z: self.pc = ir & 63
                elif op == 11:
                    if not self.z: self.pc = ir & 63
                elif op == 12: self.wait_left = imm
                elif op == 13:
                    bit = ((self.a >> (7 if ir & 8 else 0)) & 1) ^ ((ir >> 5) & 1)
                    mask = 1 << (ir & 7)
                    if ir & 16:
                        self.gpio_oe = (self.gpio_oe & ~mask) | (bit * mask)
                    else:
                        self.gpio_out = (self.gpio_out & ~mask) | (bit * mask)
                elif op == 14: self.z = ((self.a & imm) == 0)
                elif op == 15:
                    if imm & 128: self.gpio_oe ^= imm & 127
                    else: self.gpio_out ^= imm & 127
        self.cycles += 1


def trace(code, pins=0, max_cycles=20000):
    c = Core(list(code))
    events = []
    while c.running and c.cycles < max_cycles:
        old = (c.gpio_out, c.gpio_oe)
        c.tick(pins(c) if callable(pins) else pins)
        if old != (c.gpio_out, c.gpio_oe):
            events.append((c.cycles, c.gpio_out, c.gpio_oe))
    if c.running:
        raise AssertionError('no HALT before simulation timeout')
    return c, events
