# Verification record — PinScript v2

All statuses below refer **only to operations actually performed** in the
available container, as of 2026-10-13 (Sydney). The container cannot resolve
external software package servers, and has no `iverilog`, `verilator`,
`yosys`, `cocotb`, or IHP CMOS5L Liberty/PDK installation. Thus **no RTL or
post-synthesis result is claimed as passing** in this environment.

## Executed and passing

- `make software`: **16/16 pytest tests passed**; assembled all **5**
  protocol firmwares (13 / 12 / 14 / 16 / 52 instruction words).
- Exhaustive software ISA regression covers **all 256 UART TX bytes** and
  **all 256 SPI slave response bytes** while checking that concurrent TX always sends `0x96`.
- Tests check reference-model UART timings, SPI edge interval and data,
  I2C ACK/NACK STOP behavior, UART RX, both directions of pin-input shifting,
  secondary B-register isolation and edge cases in `WAIT` / `LOOP`.
- `python3 -m compileall -q tools test`: passed.
- `bash -n scripts/synth_generic.sh`: passed.
- Python syntax is validated for the cocotb suite (not executed against RTL).

## Ready to execute but **not yet run**

| Command | Tool needed | What will be checked |
| --- | --- | --- |
| `make rtl` | Icarus Verilog, Cocotb 2.x | 10 RTL protocol / control / random differential tests |
| `make synth` | Yosys | Generic-gate netlist in Verilog/JSON, structural checks, cell report |
| `make gate-test` | Yosys, Icarus, Cocotb | Run same external pin-level tests on generic synthesized netlist |
| `make lint` | Verilator | Elaborate/lint top design (warnings subject to review) |
| `gds` GitHub Action | Tiny Tapeout CMOS5L PDK/flow | Physical design, timing, DRC/LVS, post-route simulation |

`make synth` writes `build/netlist_generic.v`, `build/netlist_generic.json`,
`build/netlist_generic.sha256`, and `build/yosys_generic.log`. **These outputs
are not present until Yosys actually runs.** The netlist is a Yosys **generic**
cell representation, not a PDK-mapped netlist. Physical pin cells, liberty
mapping, setup/hold closure, and GDS are separate tasks.

When pushed to GitHub, `.github/workflows/test.yaml` will install these tools,
execute reference/RTL/gate-level regressions, and upload the netlist and logs
as workflow artifacts. The workflow has **not been run** in this session.

## Design bug discovered and fixed

The original `spi_duplex.asm` shifted both TX and RX using register `A`, so
incoming data corrupted later transmitted bits. The original test checked RX
and SCK period **but did not check MOSI**. The processor now has independent
register `B`; firmware uses `SHINLB 3`, shifts only `A` to advance TX, and
reports B using `SHOWB`. An exhaustive 256-byte software test and a new RTL
MOSI assertion prevent regression. Code and ISA documentation were updated.

## Other risks / silicon sign-off blockers

1. **Yosys RTL synthesis not executed:** no measured generic gate count or
   stdcell area. 64×16 program RAM is typically mapped to FF + combinational
   mux, potentially expensive; the 6×4 tile target is not yet established.
2. **No STA / no PDK mapped netlist:** 12 MHz is a requested clock frequency,
   not an achieved Fmax. The generic netlist cannot establish silicon timing.
3. **SPI input CDC:** three-stage source-input synchronizers plus a sampled
   edge detector. No MTBF calculation, analog metastability analysis or
   asynchronous reset-release testing was performed.
4. **Firmware limitations:** I2C does not support multi-master arbitration,
   clock stretching or repeated START; UART RX is one-shot, lacks oversampling
   and stop-bit checking; SPI full duplex supports one byte, no FIFO.
5. **Electrical I/O:** need correct external pull-ups and voltage adaptation,
   TT bidirectional macro implementation, bus contention checks on hardware.
6. **Rigor:** even a successful simulation and generic synthesis do not prove
   equivalence in all cases or guarantee correctness on fabricated silicon.
7. **Physical design:** GDS, antenna, DRC, LVS, IR-drop and routed parasitic
   STA remain unperformed, intentionally deferred by request.
