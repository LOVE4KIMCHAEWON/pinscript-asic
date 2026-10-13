"""UART startup and sampling corners, resolved solely through external pins."""
from pathlib import Path
import sys

import cocotb
from cocotb.triggers import Timer

from test import capture, cycles, reset, spi_transaction, write_program

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from assemble import assemble

PAYLOADS = (0x00, 0xFF, 0x01, 0x80, 0xA5, 0x5A)


def firmware(name):
    return assemble((ROOT / "firmware" / name).read_text(encoding="utf-8"))[0]


@cocotb.test()
async def uart_tx_idle_pullup_and_six_8n1_payloads(dut):
    await reset(dut)
    base = firmware("uart_tx.asm")
    payload_index = next(index for index, word in enumerate(base)
                         if (word >> 12) == 1)
    for payload in PAYLOADS:
        code = base.copy()
        code[payload_index] = 0x1000 | payload
        dut.ena.value = 0
        await write_program(dut, code)
        # Model the idle pull-up: TX reads high when the pad is undriven.
        # Observing OUT alone would miss a low glitch when DIR is set first.
        monitor = cocotb.start_soon(capture(dut, 1500))
        await spi_transaction(dut, [0x02, 0x00])
        dut.ena.value = 1
        records = await monitor
        tx = [(out & 1) if (oe & 1) else 1 for out, oe, _ in records]
        starts = [index for index in range(1, len(tx))
                  if tx[index - 1] and not tx[index]]
        assert starts, f"0x{payload:02x}: no START bit"
        start = starts[0]
        frame = [0] + [(payload >> bit) & 1 for bit in range(8)] + [1]
        assert start + 104 * len(frame) <= len(tx), "capture truncated frame"
        for bit, level in enumerate(frame):
            actual = tx[start + bit * 104:start + (bit + 1) * 104]
            assert actual == [level] * 104, (
                f"0x{payload:02x}: bit {bit} is not a full 104-clock bit; "
                "a startup low pulse must not precede START")
        assert all(oe & 1 for _, oe, _ in records[start:start + 1040])
        assert all(tx[start + 1040:]), "TX must retain idle high after STOP"
        assert int(dut.uio_oe.value) == 1
        assert int(dut.uio_out.value) & 1
        assert not (int(dut.uo_out.value) & 0x80), "TX program must halt"


@cocotb.test()
async def uart_rx_payload_baud_and_asynchronous_start_sweep(dut):
    await reset(dut, gpio_inputs=1)
    code = firmware("uart_rx.asm")
    # +/- 2 clocks from the nominal 104-clock bit period, and three phases
    # strictly between core edges. Each combination uses the actual firmware.
    for payload in PAYLOADS:
        for period in (102, 104, 106):
            for phase_ns in (1, 3, 7):
                dut.uio_in.value = 1
                dut.ena.value = 0
                await write_program(dut, code)
                await spi_transaction(dut, [0x02, 0x00])
                dut.ena.value = 1
                await cycles(dut, 20)
                monitor = cocotb.start_soon(capture(dut, 1200))
                await Timer(phase_ns, unit="ns")
                dut.uio_in.value = 0
                await Timer(period * 10, unit="ns")
                for bit in range(8):
                    dut.uio_in.value = (payload >> bit) & 1
                    await Timer(period * 10, unit="ns")
                dut.uio_in.value = 1
                await Timer(period * 20, unit="ns")
                records = await monitor
                context = f"byte=0x{payload:02x}, period={period}, phase={phase_ns}ns"
                assert int(dut.uo_out.value) == payload, context
                assert all(oe == 0 for _, oe, _ in records), (
                    f"{context}: receiver must leave all GPIO as inputs")
                assert records[-1][2] == records[-2][2] == payload, context
