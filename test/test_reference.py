"""Pure-Python ISA/firmware regression: pytest -q test/test_reference.py"""
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from assemble import assemble, pack_spi
from reference_model import trace

ROOT = Path(__file__).resolve().parents[1]

def load(name):
    return assemble((ROOT / 'firmware' / name).read_text())[0]


def test_programs_fit():
    for file in ('uart_tx.asm', 'spi_mode0.asm', 'i2c_write.asm'):
        program = load(file)
        assert 0 < len(program) <= 64
        frame = pack_spi(program)
        assert frame[:2] == b'\x01\x00'
        assert len(frame) == 2 + 2*len(program)
        assert frame[2:] == b''.join(x.to_bytes(2, 'big') for x in program)


def test_assembler_rejects_bad_addresses():
    with pytest.raises(ValueError, match='branch address'):
        assemble('JMP 64')
    with pytest.raises(ValueError, match='maximum 64'):
        assemble('NOP\n'*65)
    with pytest.raises(ValueError, match='duplicate'):
        assemble('dup: NOP\ndup: HALT')


def test_uart_115200_timing():
    c, events = trace(load('uart_tx.asm'))
    assert not c.running and c.gpio_oe == 1
    tx = [(t, o & 1) for t,o,_ in events if t > 1]
    assert [v for _,v in tx] == [1,0,1,0,1,0,1,0,1,0,1]
    # Start bit and every data/stop boundary occur after exactly 104 cycles.
    assert [tx[k+1][0]-tx[k][0] for k in range(1,10)] == [104]*9


def test_spi_mode0_edges():
    c, events = trace(load('spi_mode0.asm'))
    prev_clk = 0
    sampled, rising, falling = [], [], []
    for t, out, oe in events:
        clk = out & 1
        cs = (out >> 2) & 1
        if prev_clk == 0 and clk == 1:
            assert cs == 0
            sampled.append((out >> 1) & 1)
            rising.append(t)
        if prev_clk == 1 and clk == 0: falling.append(t)
        prev_clk = clk
    assert sampled == [1,0,0,1,0,1,1,0]  # 0x96, MSB-first
    assert len(rising) == len(falling) == 8
    assert [b-a for a,b in zip(rising,falling)] == [6]*8
    assert [b-a for a,b in zip(rising,rising[1:])] == [12]*7
    assert c.gpio_out == 4 and c.gpio_oe == 7


def test_i2c_2_byte_write_ack():
    c, events = trace(load('i2c_write.asm'), pins=0) # ACKs pull SDA low
    # Rising clock is transition of OE0 1->0, and SDA OE 1 => zero, 0=>one.
    prev_oe = 0
    bits = []
    for _,_,oe in events:
        if (prev_oe & 1) and not (oe & 1):
            bits.append(0 if (oe & 2) else 1)
        prev_oe = oe
    assert bits[:9] == [1,0,1,0,0,0,0,0, 1]
    # During ACK, firmware releases SDA. A slave pulls it low externally;
    # the OE trace indicates released (=1 here), not physical bus level.
    assert bits[9:18] == [0,0,1,1,0,0,1,1,1]
    assert len(bits) == 19  # final SCL release is part of STOP, not a data clock
    assert bits[-1] == 0  # SDA held low until STOP release
    assert c.z and c.gpio_oe == 0


def test_i2c_nack_terminates_after_address():
    c, events = trace(load('i2c_write.asm'), pins=2)
    prev_oe = 0
    pulses = 0
    for _,_,oe in events:
        if (prev_oe & 1) and not (oe & 1): pulses += 1
        prev_oe = oe
    assert pulses == 10  # 9 data/ACK clocks plus STOP SCL release
    assert not c.z
    assert c.gpio_oe == 0


def test_spi_full_duplex_receives_0x3c():
    rx = 0x3c
    state = {'prev_clk': 0, 'index': -1}
    def slave(c):
        clk, cs = c.gpio_out & 1, (c.gpio_out >> 2) & 1
        if clk and not state['prev_clk'] and not cs:
            state['index'] += 1
        state['prev_clk'] = clk
        i = state['index']
        bit = ((rx >> (7-i)) & 1) if 0 <= i < 8 else 0
        return bit << 3
    c, events = trace(load('spi_duplex.asm'), pins=slave)
    rising = []
    mosi = []
    pclk = 0
    for t,o,oe in events:
        clk = o & 1
        if clk and not pclk:
            rising.append(t)
            mosi.append((o >> 1) & 1)
        pclk = clk
    assert mosi == [1,0,0,1,0,1,1,0], 'MOSI must be independent of MISO'
    assert len(rising) == 8
    assert [b-a for a,b in zip(rising,rising[1:])] == [12]*7
    assert state['index'] == 7
    assert c.a == 0 and c.b == rx and c.result_byte == rx and c.show_result
    assert c.gpio_out == 0x04 and c.gpio_oe == 0x07


def test_uart_receive_samples_0x55():
    byte = 0x55
    start = 30
    baud_period = 104
    def serial(c):
        t = c.cycles
        if t < start: return 1
        bit_number = (t-start)//baud_period
        if bit_number == 0: return 0  # start
        if 1 <= bit_number <= 8: return (byte >> (bit_number-1)) & 1
        return 1   # stop and idle
    c, _ = trace(load('uart_rx.asm'), pins=serial)
    assert c.show_result and c.result_byte == byte and c.a == byte
    assert c.gpio_oe == 0  # RX remains high-impedance


def test_input_shift_both_directions():
    # Explicit pin selection and zero-flag update for both receive modes.
    c, _ = trace(assemble('LDI 0x80\nSHINL 3\nSHINR 2\nSHOWA\nHALT')[0], pins=0x08)
    assert c.result_byte == 0 and c.z  # 0x80 -> SHINL(pin3=1) gives 1, then SHINR(pin2=0) gives 0


def test_b_register_is_independent():
    source = 'LDI 0xa5\nSHINLB 0\nSHINRB 0\nSHOWB\nHALT'
    c, _ = trace(assemble(source)[0], pins=1)
    assert c.a == 0xa5, 'RX must not alter TX register'
    assert c.b == 0x80 and c.result_byte == 0x80
    assert assemble('SHOWB')[0] == [0x5700]
    assert assemble('SHINLB 3')[0] == [0x5503]
    assert assemble('SHINRB 4')[0] == [0x5604]


def test_all_reference_programs_fit():
    for name in ('uart_tx', 'uart_rx', 'spi_mode0', 'spi_duplex', 'i2c_write'):
        words = load(name + '.asm')
        assert len(words) <= 64
        assert (ROOT / 'build' / (name + '.hex')).read_text().splitlines() == [
            f'{word:04x}' for word in words
        ]


def test_wait_and_branch_corner_cases():
    # N+1 cycles are consumed by WAIT including the instruction issue cycle.
    code = assemble('LDX 2\nWAIT 0\nLOOP done\nNOP\ndone: WAIT 255\nHALT')[0]
    c, _ = trace(code)
    assert not c.running
    assert c.cycles == 260
    assert c.pc == 6


def test_spi_duplex_all_256_return_bytes():
    """For every slave byte, TX remains 0x96 and RX result equals slave byte."""
    for rx in range(256):
        state = {'prev': 0, 'index': -1}
        def slave(c):
            clk = c.gpio_out & 1
            if clk and not state['prev'] and not (c.gpio_out & 4):
                state['index'] += 1
            state['prev'] = clk
            idx = state['index']
            return (((rx >> (7-idx)) & 1) << 3) if 0 <= idx < 8 else 0
        c, events = trace(load('spi_duplex.asm'), pins=slave)
        assert c.result_byte == rx and c.b == rx
        assert c.a == 0 and c.gpio_out == 4
        prev_clk = 0
        mosi = []
        for _, out, _ in events:
            clk = out & 1
            if clk and not prev_clk:
                mosi.append((out >> 1) & 1)
            prev_clk = clk
        assert mosi == [1,0,0,1,0,1,1,0]


def test_shift_flags_b_and_pin_selection():
    for pin in range(8):
        program = assemble(f'LDI 0x80\nSHINLB {pin}\nSHINRB {pin}\nSHOWB\nHALT')[0]
        c, _ = trace(program, pins=(1 << pin))
        assert c.b == 0x80 and not c.z
        assert c.a == 0x80
        assert c.result_byte == 0x80
        c, _ = trace(program, pins=0)
        assert c.b == 0 and c.z


def test_uart_tx_all_256_payloads():
    """Check bit centers of all 256 possible UART payloads (8N1)."""
    from bisect import bisect_right
    base = load('uart_tx.asm')
    assert base[2] == 0x1055
    for payload in range(256):
        code = base.copy()
        code[2] = 0x1000 | payload
        c, events = trace(code)
        times = [t for t, o, oe in events]
        outs = [o & 1 for t, o, oe in events]
        starts = [t for i,(t,o,oe) in enumerate(events)
                  if i and o & 1 == 0 and (events[i-1][1] & 1)]
        assert starts, f'no start for 0x{payload:02x}'
        start = starts[0]
        def level(t):
            idx = bisect_right(times, t) - 1
            return outs[idx] if idx >= 0 else 0
        assert level(start + 52) == 0
        for bit in range(8):
            assert level(start + 104*(bit+1) + 52) == ((payload >> bit) & 1)
        assert level(start + 104*9 + 52) == 1
        assert c.gpio_oe == 1 and not c.running


def test_i2c_open_drain_with_external_pullups_and_ack_policy():
    """Check bus-resolved SCL/SDA for ACK, and NACK on second response."""
    from reference_model import Core
    words = load('i2c_write.asm')
    for ack_data in (True, False):
        c = Core(words + [0] * (64-len(words)))
        pin_inputs = 0xff
        rise_count = 0
        prev_scl = 1
        ack_active = False
        sampled = []
        for _ in range(1400):
            c.tick(pin_inputs)
            assert c.gpio_out & 3 == 0  # I2C pins never actively driven high
            scl = int(not bool(c.gpio_oe & 1))
            ack_edges = (8, 17) if ack_data else (8,)
            if not scl and prev_scl and rise_count in ack_edges:
                ack_active = True
            if not scl and prev_scl and rise_count in (9, 18):
                ack_active = False
            sda = int(not bool((c.gpio_oe & 2) or ack_active))
            if not prev_scl and scl:
                sampled.append(sda)
                rise_count += 1
            prev_scl = scl
            pin_inputs = 0xfc | scl | (sda << 1)
        assert sampled[:9] == [1,0,1,0,0,0,0,0,0]
        assert sampled[9:18] == [0,0,1,1,0,0,1,1,int(not ack_data)]
        assert sampled[18:] == [0]
        assert c.z == ack_data and c.gpio_oe == 0 and not c.running
