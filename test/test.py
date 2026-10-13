"""Actual RTL regression using cocotb and Icarus/Verilator (not the ISA model).
Run: cd test && make SIM=icarus
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer


async def cycles(dut, n):
    await ClockCycles(dut.clk, n)


async def reset(dut, gpio_inputs=0):
    dut.ena.value = 1
    dut.rst_n.value = 0
    dut.ui_in.value = 0x04  # CSn high, SCK=0
    dut.uio_in.value = gpio_inputs
    cocotb.start_soon(Clock(dut.clk, 10, unit='ns').start())
    await cycles(dut, 12)
    dut.rst_n.value = 1
    await cycles(dut, 12)


async def spi_transaction(dut, data, half_period=8):
    # SPI mode 0, 16 sys-clock cycles per SPI bit; gives >4x oversampling.
    dut.ui_in.value = 4
    await cycles(dut, 8)
    dut.ui_in.value = 0
    await cycles(dut, 8)
    for byte in data:
        for k in range(7, -1, -1):
            mosi = ((byte >> k) & 1) << 1
            dut.ui_in.value = mosi
            await cycles(dut, half_period)
            dut.ui_in.value = mosi | 1
            await cycles(dut, half_period)
    dut.ui_in.value = 0  # trailing falling SCLK edge
    await cycles(dut, 8)
    dut.ui_in.value = 4  # finish CSn frame
    await cycles(dut, 8)


async def write_program(dut, words):
    frame = [0x01, 0x00]
    for word in words:
        frame += [word >> 8, word & 0xff]
    await spi_transaction(dut, frame)
    assert (int(dut.uo_out.value) >> 7) == 0, 'WRITE must stop core'


async def capture(dut, count):
    records = []
    for _ in range(count):
        await RisingEdge(dut.clk)
        await Timer(1, unit='ns')
        records.append((int(dut.uio_out.value), int(dut.uio_oe.value),
                        int(dut.uo_out.value)))
    return records


@cocotb.test()
async def basic_load_run(dut):
    await reset(dut)
    # Configure PIO0 output, set high, wait 5 clocks, pull low, HALT.
    await write_program(dut, [0x4001, 0x3001, 0xC005, 0x3000, 0x0001])
    await spi_transaction(dut, [0x02, 0x00])
    await cycles(dut, 16)
    assert int(dut.uio_oe.value) == 1
    assert int(dut.uio_out.value) == 0
    assert (int(dut.uo_out.value) & 0xBF) == 5, 'PC after HALT = 5'


@cocotb.test()
async def uart_waveform(dut):
    await reset(dut)
    # Program matches firmware/uart_tx.asm
    program = [0x4001,0x3001,0x1055,0x2008,0x3000,0xC066,
               0xD000,0xC064,0x7000,0x8006,0x3001,0xC066,0x0001]
    await write_program(dut, program)
    monitor = cocotb.start_soon(capture(dut, 1600))
    await spi_transaction(dut, [0x02, 0x00])
    samples = await monitor
    tx = [o & 1 for o,_,_ in samples]
    edges = [(i,tx[i]) for i in range(1,len(tx)) if tx[i] != tx[i-1]]
    assert [v for _,v in edges] == [1,0,1,0,1,0,1,0,1,0,1]
    assert [edges[j+1][0] - edges[j][0] for j in range(1,10)] == [104]*9
    assert int(dut.uio_oe.value) == 1


@cocotb.test()
async def spi_master_mode0(dut):
    await reset(dut)
    # Program matches firmware/spi_mode0.asm, 0x96 MSB first.
    program = [0x4007,0x3004,0x1096,0x2008,0x3000,0xD009,
               0xC001,0xF001,0xC004,0xF001,0x7001,0x8005,0x3004,0x0001]
    await write_program(dut, program)
    monitor = cocotb.start_soon(capture(dut, 600))
    await spi_transaction(dut, [0x02, 0x00])
    samples = await monitor
    clk_edges = [(i, (o >> 1)&1, (o >> 2)&1)
                 for i, (o,oe,_) in enumerate(samples)
                 if i>0 and (o & 1) and not (samples[i-1][0]&1)]
    assert [(mosi,cs) for _,mosi,cs in clk_edges] == [
        (1,0),(0,0),(0,0),(1,0),(0,0),(1,0),(1,0),(0,0)]
    assert all((b[0]-a[0]) == 12 for a,b in zip(clk_edges,clk_edges[1:]))
    assert int(dut.uio_out.value) == 4


@cocotb.test()
async def i2c_ack_and_nack(dut):
    # Address 0x50, data 0x33, check ACK and STOP. 52 words in firmware.
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'build' / 'i2c_write.hex'
    words = [int(x,16) for x in path.read_text().splitlines()]
    await reset(dut, gpio_inputs=0x00)  # test slave responds ACK (SDA low)
    await write_program(dut, words)
    monitor = cocotb.start_soon(capture(dut, 1250))
    await spi_transaction(dut, [0x02,0x00])
    samples = await monitor
    bits = []
    for prev,cur in zip(samples,samples[1:]):
        oe_prev,oe = prev[1],cur[1]
        if (oe_prev&1) and not (oe&1):
            bits.append(0 if (oe&2) else 1)
    assert bits[:9] == [1,0,1,0,0,0,0,0,1]
    assert bits[9:18] == [0,0,1,1,0,0,1,1,1]
    assert len(bits) == 19  # includes STOP's SCL rising edge
    assert int(dut.uio_oe.value) == 0
    assert (int(dut.uo_out.value) & 0x40) == 0x40

    # Reload and retry with NACK: program should abort after address.
    dut.uio_in.value = 2
    await write_program(dut, words)
    monitor = cocotb.start_soon(capture(dut, 750))
    await spi_transaction(dut, [0x02,0x00])
    samples = await monitor
    pulses = sum(1 for p,c in zip(samples,samples[1:])
                 if (p[1]&1) and not (c[1]&1))
    assert pulses == 10
    assert int(dut.uio_oe.value) == 0
    assert (int(dut.uo_out.value) & 0x40) == 0


@cocotb.test()
async def uart_receives_byte(dut):
    from pathlib import Path
    words = [int(x,16) for x in (Path(__file__).resolve().parents[1]
             / 'build' / 'uart_rx.hex').read_text().splitlines()]
    await reset(dut, gpio_inputs=1)  # UART idle high
    await write_program(dut, words)
    await spi_transaction(dut, [0x02, 0x00])
    await cycles(dut, 20)  # let the core begin polling for START
    dut.uio_in.value = 0
    await cycles(dut, 104)  # START
    for i in range(8):
        dut.uio_in.value = (0x55 >> i) & 1
        await cycles(dut, 104)
    dut.uio_in.value = 1   # STOP
    await cycles(dut, 150)
    assert int(dut.uo_out.value) == 0x55, 'SHOWA must expose received byte'
    assert int(dut.uio_oe.value) == 0  # receiver is not driving RX


@cocotb.test()
async def spi_duplex_receives_byte(dut):
    from pathlib import Path
    words = [int(x,16) for x in (Path(__file__).resolve().parents[1]
             / 'build' / 'spi_duplex.hex').read_text().splitlines()]
    await reset(dut)
    await write_program(dut, words)

    async def drive_miso():
        result = 0x3c
        previous_clk = 0
        falling = 0
        dut.uio_in.value = ((result >> 7) & 1) << 3
        for _ in range(650):
            await RisingEdge(dut.clk)
            await Timer(1, unit='ns')
            clk = int(dut.uio_out.value) & 1
            if previous_clk and not clk and falling < 7:
                falling += 1
                dut.uio_in.value = ((result >> (7-falling)) & 1) << 3
            previous_clk = clk
        return falling

    slave = cocotb.start_soon(drive_miso())
    monitor = cocotb.start_soon(capture(dut, 650))
    await spi_transaction(dut, [0x02,0x00])
    falling = await slave
    records = await monitor
    mosi = [(o >> 1) & 1 for a,(o,oe,u) in enumerate(records)
            if a and (o & 1) and not (records[a-1][0] & 1)]
    assert mosi == [1,0,0,1,0,1,1,0], f'MOSI corrupted by MISO: {mosi}' 
    assert falling == 7
    assert int(dut.uo_out.value) == 0x3c, 'full duplex sampled 0x3c'
    assert int(dut.uio_out.value) == 4, 'SPI slave deselected at end'
    assert int(dut.uio_oe.value) == 7, 'MISO remained input'


@cocotb.test()
async def cpu_isa_random_differential(dut):
    """Compare actual RTL external state to an independent ISA model per clock."""
    import random
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
    from reference_model import Core
    from assemble import assemble

    rng = random.Random(0xC0DE531)
    await reset(dut, gpio_inputs=0xA6)
    for seed in range(5):
        lines = []
        n = 32
        for index in range(n - 1):
            op = rng.choice(['LDI', 'LDX', 'OUT', 'DIR', 'OUTA',
                 'SHINL','SHINR','SHINLB','SHINRB','SHOWA','SHOWB',
                 'IN', 'SHR','SHL','WAIT','DBIT','TEST','XORO','XORD',
                 'NOP','LOOP','JZ','JNZ','JMP'])
            if op in ('LDI','LDX','OUT','DIR','TEST'):
                lines.append(f'{op} {rng.randrange(256)}')
            elif op == 'WAIT':
                lines.append(f'WAIT {rng.choice([0,1,3,15,255])}')
            elif op in ('SHINL','SHINR','SHINLB','SHINRB'):
                lines.append(f'{op} {rng.randrange(8)}')
            elif op == 'DBIT':
                lines.append(f'DBIT {rng.randrange(8)}, '
                             f'{rng.choice(["lsb","msb"])}, '
                             f'{rng.choice(["out","oe"])}, '
                             f'{rng.choice(["invert","normal"])}')
            elif op in ('XORO','XORD'):
                lines.append(f'{op} {rng.randrange(128)}')
            elif op in ('LOOP','JMP','JZ','JNZ'):
                # Forward-only branches prove finite termination.
                lines.append(f'{op} {rng.randrange(index+1,n)}')
            else:
                lines.append(op)
        lines.append('HALT')
        words, _ = assemble('\n'.join(lines))
        dut.ena.value = 0
        await write_program(dut, words)
        await spi_transaction(dut, [0x02, 0x00], half_period=5+seed)
        model = Core(words + [0] * (64-len(words)))
        assert int(dut.uo_out.value) == 0xC0
        dut.ena.value = 1
        for tick in range(10000):
            await RisingEdge(dut.clk)
            await Timer(1, unit='ns')
            model.tick(0xA6)
            expected_uo = (model.result_byte if model.show_result else
                           ((int(model.running) << 7) | (int(model.z) << 6) | model.pc))
            actual = (int(dut.uio_out.value), int(dut.uio_oe.value),
                      int(dut.uo_out.value))
            expected = (model.gpio_out, model.gpio_oe, expected_uo)
            assert actual == expected, (f'seed={seed} tick={tick} '
                                        f'pc={model.pc} actual={actual} expected={expected}')
            if not model.running:
                break
        assert not model.running, f'seed {seed} did not halt'


@cocotb.test()
async def config_write_wraparound_and_halt(dut):
    await reset(dut)
    dut.ena.value = 0
    # Write address 63 and auto-increment wraps to address 0.
    await spi_transaction(dut, [0x01, 0x3f, 0x30, 0x5a, 0x00, 0x01], half_period=6)
    await spi_transaction(dut, [0x02, 0x3f], half_period=6)
    assert int(dut.uo_out.value) == 0xFF  # RUN, Z, PC=63
    dut.ena.value = 1
    await cycles(dut, 3)
    await Timer(1, unit='ns')
    assert int(dut.uio_out.value) == 0x5a
    assert (int(dut.uo_out.value) >> 7) == 0, 'wrapped HALT at address 0'
    dut.ena.value = 0
    await spi_transaction(dut, [0x02, 0x00])
    assert int(dut.uio_out.value) == 0
    assert int(dut.uio_oe.value) == 0


@cocotb.test()
async def wait_pause_and_resume(dut):
    await reset(dut)
    dut.ena.value = 0
    await write_program(dut, [0x4001,0x3001,0xC00A,0x3000,0x0001])
    await spi_transaction(dut, [0x02,0x00])
    dut.ena.value = 1
    for _ in range(3):
        await RisingEdge(dut.clk)
        await Timer(1, unit='ns')
    assert int(dut.uio_out.value) == 1
    pc = int(dut.uo_out.value) & 63
    dut.ena.value = 0
    await cycles(dut, 20)
    await Timer(1, unit='ns')
    assert int(dut.uio_out.value) == 1
    assert (int(dut.uo_out.value) & 63) == pc
    dut.ena.value = 1
    await cycles(dut, 13)
    await Timer(1, unit='ns')
    assert int(dut.uio_out.value) == 0
    assert (int(dut.uo_out.value) >> 7) == 0


@cocotb.test()
async def i2c_bus_resolver_ack_and_nack(dut):
    """Model physical pull-ups and slave ACK only during the 9th clock.

    Earlier constant-zero I2C tests check firmware decisions, but not the
    open-drain bus. This exercises the external pin-level resolution too.
    """
    from pathlib import Path
    words = [int(x, 16) for x in (Path(__file__).resolve().parents[1]
             / 'build' / 'i2c_write.hex').read_text().splitlines()]
    await reset(dut, gpio_inputs=0xff)
    await write_program(dut, words)

    async def bus_model(ack_data=True):
        rises = 0
        prev_scl = 1
        ack_active = False
        sampled = []
        for tick in range(1400):
            await RisingEdge(dut.clk)
            await Timer(1, unit='ns')
            oe = int(dut.uio_oe.value)
            out = int(dut.uio_out.value)
            # Open drain is driven LOW only when the corresponding OE bit=1.
            assert (out & 0x03) == 0, 'firmware must never drive I2C line high'
            scl = 0 if (oe & 1) else 1
            # ACK begins during low phase following eight data bits,
            # persists through SCL high, and ends after ACK falling edge.
            ack_index = (8, 17) if ack_data else (8,)
            if not scl and prev_scl and rises in ack_index:
                ack_active = True
            if not scl and prev_scl and rises in (9, 18):
                ack_active = False
            sda = 0 if ((oe & 2) or ack_active) else 1
            if not prev_scl and scl:
                sampled.append(sda)
                rises += 1
            prev_scl = scl
            dut.uio_in.value = (0xfc | scl | (sda << 1))
        return sampled

    monitor = cocotb.start_soon(bus_model(ack_data=True))
    await spi_transaction(dut, [0x02, 0x00])
    sampled = await monitor
    assert sampled[:9] == [1,0,1,0,0,0,0,0,0]
    assert sampled[9:18] == [0,0,1,1,0,0,1,1,0]
    assert len(sampled) == 19
    assert int(dut.uio_oe.value) == 0
    assert int(dut.uo_out.value) & 0x40  # ACK zero flag

    # ACK address, then NACK data: STOP still generated, status goes low.
    await write_program(dut, words)
    monitor = cocotb.start_soon(bus_model(ack_data=False))
    await spi_transaction(dut, [0x02, 0x00])
    sampled = await monitor
    assert sampled[:9] == [1,0,1,0,0,0,0,0,0]
    assert sampled[9:18] == [0,0,1,1,0,0,1,1,1]
    assert len(sampled) == 19
    assert (int(dut.uo_out.value) & 0x40) == 0
    assert int(dut.uio_oe.value) == 0
