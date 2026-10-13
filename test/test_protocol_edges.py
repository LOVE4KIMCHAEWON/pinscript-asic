"""Pin-level protocol checks shared by RTL and generic-netlist simulation.

Run with COCOTB_TEST_MODULES=test,test_protocol_edges. Only the top-level
ports are inspected, so these tests do not depend on internal RTL names.
"""
from pathlib import Path

import cocotb
from cocotb.triggers import RisingEdge, Timer

from test import reset, spi_transaction, write_program


ROOT = Path(__file__).resolve().parents[1]


def firmware(name):
    return [int(word, 16) for word in
            (ROOT / "build" / f"{name}.hex").read_text().splitlines()]


async def i2c_bus(dut, ack_address, ack_data, count=1400):
    """Resolve pull-ups and a slave that sinks only its ACK slots."""
    previous_scl, previous_sda = 1, 1
    rises = 0
    slave_low = False
    samples, starts, stops, falling = [], [], [], []
    ack_after_bits = ({8} if ack_address else set())
    if ack_address and ack_data:
        ack_after_bits.add(17)

    for tick in range(count):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        out, oe = int(dut.uio_out.value), int(dut.uio_oe.value)
        assert out & 3 == 0, "I2C output latches must remain low"
        assert oe & 0xfc == 0, "I2C demo must drive only SCL/SDA"
        scl = int(not (oe & 1))
        if previous_scl and not scl:
            falling.append(tick)
            if rises in ack_after_bits:
                slave_low = True
            elif rises in (9, 18):
                slave_low = False
        sda = int(not ((oe & 2) or slave_low))

        if previous_scl and scl and previous_sda != sda:
            (starts if sda == 0 else stops).append(tick)
        if not previous_scl and scl:
            samples.append((tick, sda))
            rises += 1

        # Other inputs are pulled high; the DUT samples the resolved bus.
        dut.uio_in.value = 0xfc | scl | (sda << 1)
        previous_scl, previous_sda = scl, sda

    return samples, starts, stops, falling, (previous_scl, previous_sda)


@cocotb.test()
async def i2c_start_stop_and_ack_slots(dut):
    """START/STOP and data must agree on the resolved open-drain bus."""
    await reset(dut, gpio_inputs=0xff)
    words = firmware("i2c_write")
    for ack_address, ack_data in ((True, True), (False, False), (True, False)):
        await write_program(dut, words)
        monitor = cocotb.start_soon(i2c_bus(dut, ack_address, ack_data))
        await spi_transaction(dut, [0x02, 0x00])
        samples, starts, stops, falling, idle = await monitor

        assert len(starts) == 1, "one SDA falling edge while SCL high is START"
        assert len(stops) == 1, "one SDA rising edge while SCL high is STOP"
        assert starts[0] < falling[0] < samples[0][0]
        assert samples[-1][0] < stops[0], "SCL must rise before STOP releases SDA"
        assert idle == (1, 1), "both pull-ups must restore the idle bus"

        expected = [1, 0, 1, 0, 0, 0, 0, 0, int(not ack_address)]
        if ack_address:
            expected += [0, 0, 1, 1, 0, 0, 1, 1, int(not ack_data)]
        # STOP includes one SCL rising edge while SDA is still held low.
        expected += [0]
        assert [sda for _, sda in samples] == expected
        assert len(falling) == len(samples)
        status = int(dut.uo_out.value)
        assert bool(status & 0x40) == (ack_address and ack_data)
        assert status & 0x80 == 0, "the one-shot firmware must halt"
        assert int(dut.uio_oe.value) == 0


async def spi_bus(dut, response=None, count=650):
    """Observe resolved pins and change slave MISO on falling SCK edges."""
    previous_clk, previous_mosi, previous_cs = 0, 0, 1
    last_mosi_change = 0
    frames = []
    frame = None
    dut.uio_in.value = 0 if response is None else ((response >> 7) & 1) << 3

    for tick in range(count):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        out, oe = int(dut.uio_out.value), int(dut.uio_oe.value)
        # SCK/MOSI have external pull-downs and CS has a pull-up.
        pins = (out & oe & 7) | (4 & ~oe & 7)
        clk, mosi, cs = pins & 1, (pins >> 1) & 1, (pins >> 2) & 1

        if mosi != previous_mosi:
            assert not clk, "Mode 0 MOSI must remain stable while SCK is high"
            last_mosi_change = tick

        if previous_cs and not cs:
            assert not clk, "select slave with SCK at its Mode 0 idle level"
            frame = {"start": tick, "rising": [], "falling": [],
                     "mosi": [], "setup": []}
        if not previous_clk and clk:
            assert not cs and not previous_cs, "every sample edge needs active CS"
            assert oe & 7 == 7, "master must drive SCK/MOSI/CS"
            assert oe & 8 == 0, "master must leave MISO as an input"
            assert frame is not None
            frame["rising"].append(tick)
            frame["mosi"].append(mosi)
            frame["setup"].append(tick - last_mosi_change)
        if previous_clk and not clk:
            assert not cs and frame is not None
            frame["falling"].append(tick)
            sampled = len(frame["mosi"])
            if response is not None and sampled < 8:
                dut.uio_in.value = ((response >> (7 - sampled)) & 1) << 3
        if not previous_cs and cs:
            assert not clk and not previous_clk, "deselect after SCK returns low"
            assert frame is not None
            frame["stop"] = tick
            if frame["rising"]:
                frames.append(frame)
            else:
                raise AssertionError("unexpected CS-low pulse without SPI clocks")
            frame = None

        previous_clk, previous_mosi, previous_cs = clk, mosi, cs

    assert frame is None, "SPI transaction must end within observation window"
    return frames, (previous_clk, previous_cs)


@cocotb.test()
async def spi_mode0_setup_hold_and_duplex_patterns(dut):
    """Validate timing, framing and independent TX/RX on top-level pins."""
    await reset(dut)
    cases = [("spi_mode0", None, 3)]
    cases += [("spi_duplex", byte, 4) for byte in (0x00, 0xff, 0xa5, 0x5a)]
    expected_tx = [1, 0, 0, 1, 0, 1, 1, 0]

    for name, response, minimum_setup in cases:
        await write_program(dut, firmware(name))
        monitor = cocotb.start_soon(spi_bus(dut, response))
        await spi_transaction(dut, [0x02, 0x00])
        frames, idle = await monitor

        assert len(frames) == 1, "one complete clocked SPI transfer is expected"
        frame = frames[0]
        assert frame["mosi"] == expected_tx, "RX must not corrupt the TX byte"
        assert len(frame["rising"]) == len(frame["falling"]) == 8
        assert all(b - a == 12 for a, b in
                   zip(frame["rising"], frame["rising"][1:]))
        assert all(fall - rise == 6 for rise, fall in
                   zip(frame["rising"], frame["falling"]))
        assert all(setup >= minimum_setup for setup in frame["setup"])
        assert frame["start"] < frame["rising"][0]
        assert frame["falling"][-1] < frame["stop"]
        assert idle == (0, 1), "Mode 0 ends with SCK low and slave deselected"
        assert int(dut.uio_out.value) == 4 and int(dut.uio_oe.value) == 7
        if response is not None:
            assert int(dut.uo_out.value) == response, "SHOWB must expose the RX byte"
