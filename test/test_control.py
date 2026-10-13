"""Directed CPU/loader regressions using only external pins.

Run alongside test.py with COCOTB_TEST_MODULES=test,test_control. These tests
also work with the synthesized generic netlist; no RTL hierarchy is inspected.
"""
import cocotb
from cocotb.triggers import Timer

from test import cycles, reset, spi_transaction, write_program


async def settle(dut, count=1):
    await cycles(dut, count)
    await Timer(1, unit="ns")


def bits(data):
    return [(byte >> index) & 1 for byte in data for index in range(7, -1, -1)]


async def spi_bits_frame(dut, payload, half_ns=80, phase_ns=0):
    """Send exact bit count, with clock edges independent of the core clock."""
    dut.ui_in.value = 4
    await Timer(80 + phase_ns, unit="ns")
    dut.ui_in.value = 0
    await Timer(80, unit="ns")
    for bit in payload:
        dut.ui_in.value = bit << 1
        await Timer(half_ns, unit="ns")
        dut.ui_in.value = (bit << 1) | 1
        await Timer(half_ns, unit="ns")
    dut.ui_in.value = 0
    await Timer(80, unit="ns")
    dut.ui_in.value = 4
    await Timer(80, unit="ns")


@cocotb.test()
async def loader_reframes_unknown_and_truncated_commands(dut):
    await reset(dut)
    dut.ena.value = 0
    original = [0x30A5, 0x405A, 0x0001]
    await write_program(dut, original)
    await spi_transaction(dut, [0x02, 0])
    dut.ena.value = 1
    await settle(dut, 3)
    assert (int(dut.uio_out.value), int(dut.uio_oe.value), int(dut.uo_out.value)) == (
        0xA5, 0x5A, 0x43)

    # Bytes after an unknown opcode are ignored until the next CS frame.
    # An incomplete RUN command must not consume an entry from a later frame.
    for frame in ([0x7F, 0x02, 0x00], [0x02]):
        await spi_transaction(dut, frame)
        assert (int(dut.uio_out.value), int(dut.uio_oe.value), int(dut.uo_out.value)) == (
            0xA5, 0x5A, 0x43)

    # An incomplete word, whether a whole high byte or seven low-byte bits,
    # must not commit. The next CS frame must discard all partial state.
    for fragment in (bits([0x01, 0x00, 0x30]),
                     bits([0x01, 0x00, 0x30, 0x00])[:-1],
                     bits([0x01])):
        await spi_bits_frame(dut, fragment)
        assert int(dut.uo_out.value) == 0x43
        dut.ena.value = 0
        await spi_transaction(dut, [0x02, 0x00])
        assert int(dut.uo_out.value) == 0xC0
        dut.ena.value = 1
        await settle(dut, 3)
        assert (int(dut.uio_out.value), int(dut.uio_oe.value), int(dut.uo_out.value)) == (
            0xA5, 0x5A, 0x43)


@cocotb.test()
async def loader_halt_preserves_gpio_and_clears_result_mux(dut):
    await reset(dut)
    # HALT must stop a currently stalled CPU, retaining GPIO and direction.
    await write_program(dut, [0x4001, 0x3001, 0xC0FF, 0x9002])
    await spi_transaction(dut, [0x02, 0x00])
    assert int(dut.uo_out.value) == 0xC3
    # A second command in the same frame must be ignored.
    await spi_transaction(dut, [0x03, 0x02, 0x00])
    assert (int(dut.uio_out.value), int(dut.uio_oe.value), int(dut.uo_out.value)) == (
        1, 1, 0x43)
    await settle(dut, 300)
    assert int(dut.uo_out.value) == 0x43

    # SHOWA normally hides the RUN/Z/PC status. A config HALT restores it.
    await write_program(dut, [0x10A6, 0x5300, 0xC0FF, 0x9002])
    await spi_transaction(dut, [0x02, 0x00])
    assert int(dut.uo_out.value) == 0xA6
    await spi_transaction(dut, [0x03])
    assert int(dut.uo_out.value) == 0x03
    await settle(dut, 300)
    assert int(dut.uo_out.value) == 0x03


@cocotb.test()
async def run_resets_all_execution_state(dut):
    await reset(dut, gpio_inputs=1)
    dut.ena.value = 0
    words = [0] * 28
    # Dirty both accumulators, loop counter, GPIO, flags, result, and WAIT.
    words[:8] = [0x10FF, 0x2003, 0x30FF, 0x40FF, 0x5500, 0x5700,
                 0xC0FF, 0x9006]
    # A/B/X/Z/WAIT reset probes, reporting any branch failure through GPIO.
    words[16:22] = [0x5000, 0x5700, 0x801A, 0xB01A, 0x3012, 0x0001]
    words[26:28] = [0x30E1, 0x0001]
    await write_program(dut, words)
    await spi_transaction(dut, [0x02, 0x00])
    dut.ena.value = 1
    await settle(dut, 7)
    assert (int(dut.uio_out.value), int(dut.uio_oe.value), int(dut.uo_out.value)) == (
        0xFF, 0xFF, 1)
    dut.ena.value = 0
    await spi_transaction(dut, [0x02, 16])
    assert (int(dut.uio_out.value), int(dut.uio_oe.value), int(dut.uo_out.value)) == (
        0, 0, 0xD0)
    dut.ena.value = 1
    await settle(dut)
    assert int(dut.uio_out.value) == 0, "RUN must clear A and WAIT"
    await settle(dut)
    assert int(dut.uo_out.value) == 0, "RUN must clear B"
    await settle(dut, 4)
    assert int(dut.uio_out.value) == 0x12, "RUN must clear X and set Z"
    assert int(dut.uio_oe.value) == 0
    await settle(dut, 300)
    assert int(dut.uio_out.value) == 0x12, "probe must halt"


@cocotb.test()
async def synchronous_reset_preserves_loaded_instruction_memory(dut):
    await reset(dut)
    await write_program(dut, [0x4001, 0x30A5, 0x0001])
    await spi_transaction(dut, [0x02, 0])
    assert (int(dut.uio_out.value), int(dut.uio_oe.value)) == (0xA5, 1)
    dut.ena.value = 0
    dut.rst_n.value = 0
    await settle(dut, 12)
    assert (int(dut.uio_out.value), int(dut.uio_oe.value), int(dut.uo_out.value)) == (
        0, 0, 0x40)
    dut.rst_n.value = 1
    await settle(dut, 12)
    # No WRITE occurs after reset: RUN executes the previously loaded RAM.
    await spi_transaction(dut, [0x02, 0])
    dut.ena.value = 1
    await settle(dut, 3)
    assert (int(dut.uio_out.value), int(dut.uio_oe.value), int(dut.uo_out.value)) == (
        0xA5, 1, 0x43)


@cocotb.test()
async def execution_pc_wraps_at_instruction_63(dut):
    await reset(dut)
    dut.ena.value = 0
    await spi_transaction(dut, [0x01, 63, 0x30, 0xAA])
    await write_program(dut, [0x405A, 0x0001])
    await spi_transaction(dut, [0x02, 63])
    assert int(dut.uo_out.value) == 0xFF
    dut.ena.value = 1
    await settle(dut)
    assert (int(dut.uio_out.value), int(dut.uo_out.value)) == (0xAA, 0xC0)
    await settle(dut)
    assert (int(dut.uio_oe.value), int(dut.uo_out.value)) == (0x5A, 0xC1)
    await settle(dut)
    assert int(dut.uo_out.value) == 0x42


@cocotb.test()
async def loader_accepts_conservative_asynchronous_spi_edges(dut):
    await reset(dut)
    dut.ena.value = 0
    # Non-integral core-clock periods and initial offsets exercise each
    # synchronizer phase while respecting conservative setup/hold times.
    for index, (half_ns, phase_ns) in enumerate(((61, 1), (79, 3), (113, 7))):
        value = (0x96, 0x69, 0xC3)[index]
        await spi_bits_frame(dut, bits([0x01, 0, 0x30, value, 0x40, 0xA5, 0, 1]),
                             half_ns=half_ns, phase_ns=phase_ns)
        await spi_bits_frame(dut, bits([0x02, 0]),
                             half_ns=half_ns, phase_ns=phase_ns)
        assert int(dut.uo_out.value) == 0xC0
        dut.ena.value = 1
        await settle(dut, 3)
        assert (int(dut.uio_out.value), int(dut.uio_oe.value), int(dut.uo_out.value)) == (
            value, 0xA5, 0x43)
        dut.ena.value = 0
