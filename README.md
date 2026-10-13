# PinScript — programmable protocol-emulator ASIC (engineering prototype)

PinScript is an open-source, 64-instruction, cycle-deterministic PIO processor targeting the **Jane Street 2026 protocol-emulator ASIC competition** and **Tiny Tapeout IHP CMOS5L** (`cmos5l` Verilog template). The core is firmware programmable after fabrication. Five example programs cover **UART TX/RX**, **SPI master TX/full-duplex**, and **I²C open-drain writes** using one common engine.

> **Status: RTL, protocol regression and Yosys generic synthesis verified.** Executed test counts, source commit, tool versions and checksums are recorded in [reports/latest.md](reports/latest.md) and [reports/summary.json](reports/summary.json). The repository includes the generated Verilog/JSON netlist and JUnit evidence. Physical implementation, PDK mapping and silicon timing are outside this delivery.

## Hardware architecture

- Clocked 8-bit datapath (`A` TX accumulator, `B` independent RX accumulator, `X` loop counter), 6-bit program counter, zero flag.
- 64 × 16-bit instruction memory (normally inferred as flip-flops + mux; no SRAM macro assumed).
- 16 opcode families: immediate output, output-enable control, bit insertion from `A[0]`/`A[7]`, **input-bit shift accumulation into A or B**, shifts, input sampling, conditional loops/branches, **a captured-byte debug output**, and **cycle-counted waits**.
- 8 bidirectional firmware-controlled `uio[7:0]` pins: each has its own output latch and active-high output-enable. Open-drain protocols use output=0 and dynamically change only OE.
- Separate, always-available **write-only SPI configuration port** on `ui[2:0]` that can reload firmware and restart the processor.
- 8 dedicated outputs normally show debug indicators (PC, Z flag, running state). `SHOWA`/`SHOWB` switches them to display an entire received byte; the next `RUN`, configuration `WRITE`/`HALT`, or reset restores debug mode.
- No inferred latches, no internal clock gating, no vendor-specific IP in the RTL.

### Pin mapping

| TT pins | Meaning |
| --- | --- |
| `ui[0]` | Host `CFG_SCLK` (SPI mode 0, input) |
| `ui[1]` | Host `CFG_MOSI` (SPI input) |
| `ui[2]` | Host `CFG_CS_N` (active-low SPI chip select) |
| `ui[7:3]` | Reserved inputs; currently unused |
| `uio[7:0]` | Protocol GPIO; `uio_oe=1` means driven, `0` means high-Z |
| `uo[5:0]` | Program counter in debug mode |
| `uo[6]` | Zero flag in debug mode (from most recent flag-setting instruction) |
| `uo[7]` | RUNNING flag in debug mode |
| `uo[7:0]` | Selected A/B byte after firmware executes `SHOWA` or `SHOWB` (until next RUN/WRITE/HALT/reset) |
| `clk` | Single main system clock (example projects use **12 MHz**) |
| `rst_n` | Active-low synchronous reset (registers, **not** program memory) |
| `ena` | Enables CPU execution when high (SPI loader remains available) |

**Important electrical considerations:** TT provides `uio_out` and `uio_oe` for output/tri-state; external board or testbench must resolve those into the `uio_in` input values. I²C requires appropriate external SDA/SCL pull-ups and voltage compatibility with the IHP I/O cells. Check the actual Tiny Tapeout pin electrical ratings before connecting external parts. Do not drive an actively driven pin from an external device.

### SPI programming transport

Configuration SPI is **input-only** (no MISO or readback) and uses MSB-first bytes sampled on the rising edge. This is an independently clock-domain-synchronized protocol: the system clock should substantially exceed SPI SCK; at **12 MHz** use **250 kHz** as a conservative configuration rate. Keep CS high between commands.

| Transaction under a single CS-low frame | Effect |
| --- | --- |
| `01 AA HH LL [HH LL ...]` | Halt CPU, write words from address `AA[5:0]`, auto-increment wrapping at 64. Each word high byte first. |
| `02 EE` | Reset CPU registers/outputs and execute from address `EE[5:0]`. |
| `03` | Halt CPU (GPIO output/OE latches remain unchanged). |

A partial final word is ignored. SPI instructions end when CS rises. Changing firmware while running halts the core. **Program RAM is uninitialized on reset**; always WRITE before RUN. The transport has no parity, CRC, status/MISO, or transfer acknowledgement in this version. The chip is not yet a self-contained host programmer.

### ISA (16-bit instruction words, transported high byte first)

All instructions execute in one system-clock period, except `WAIT N`, which consumes **N+1 periods**: an execute edge plus N following stalled cycles. Instruction fetch is combinational; architectural GPIO latches change on the instruction edge. Branch addresses are in the low six bits.

| Opcode | Mnemonic | Semantics |
| --- | --- | --- |
| `0` | `NOP` / `HALT` | `0000` no-op; `0001` halt |
| `1` | `LDI n` | `A=n`, Z=(n==0) |
| `2` | `LDX n` | `X=n` (8-bit loop counter) |
| `3` | `OUT n` | `gpio_out=n` |
| `4` | `DIR n` | `gpio_oe=n` |
| `5` | `OUTA`, `SHINL p`, `SHINR p`, `SHINLB p`, `SHINRB p`, `SHOWA`, `SHOWB` | Input-bit shifts choose A or independent B accumulator; SHOWA/SHOWB expose the selected register on uo[7:0]. |
| `6` | `IN` | `A=uio_in`, Z=(A==0) |
| `7` | `SHR` / `SHL` | Shift A right/left with zero fill, update Z |
| `8` | `LOOP label` | If X>0 decrement X; branch to label if post-decrement X>0 |
| `9` | `JMP label` | Unconditional branch |
| `A` | `JZ label` | Branch if Z=1 |
| `B` | `JNZ label` | Branch if Z=0 |
| `C` | `WAIT n` | Pause N subsequent cycles, N=0..255 |
| `D` | `DBIT p, lsb\|msb, out\|oe, [invert]` | Write selected (possibly inverted) A bit to one chosen output or OE bit |
| `E` | `TEST n` | Z=((A & n)==0); preserve A |
| `F` | `XORO n` / `XORD n` | XOR bitmask into outputs or OEs; **mask limited to 7 lower pins** (0..127) |

`DBIT` subfields: `ir[2:0]=pin`, `ir[3]=MSB source`, `ir[4]=OE destination`, `ir[5]=invert bit`. For opcode 5: `0x5000`=OUTA, `0x510p`=SHINL pin p, `0x520p`=SHINR pin p, `0x5300`=SHOWA; `0x550p`=SHINLB pin p, `0x560p`=SHINRB pin p, `0x5700`=SHOWB. A 64-instruction maximum is enforced by the assembler. The program counter wraps at address 63.

### Reference firmware

| Program | System clk | Operation | Word count |
| --- | ---: | --- | ---: |
| `uart_tx.asm` | 12 MHz | 115200 baud 8N1 UART, sends `0x55` on PIO0 (actual 115385 baud; 0.16% fast) | 13 |
| `uart_rx.asm` | 12 MHz | Detect UART START on PIO0, sample 8 data bits, report captured byte on `uo[7:0]` | 12 |
| `spi_mode0.asm` | 12 MHz | 1 MHz, MSB-first SPI Mode 0 write `0x96` (PIO0 SCK, PIO1 MOSI, PIO2 CSn) | 14 |
| `spi_duplex.asm` | 12 MHz | 1 MHz Mode 0 full duplex, send `0x96` from A and independently capture MISO into B | 16 |
| `i2c_write.asm` | 12 MHz | ~324 kHz I²C master write to 7-bit address `0x50`, data `0x33`; ACK/NACK & STOP (PIO0 SCL, PIO1 SDA) | 52 |

The I²C firmware does **not** support clock stretching, arbitration loss, bus recovery, or repeated START. UART RX is one-shot and lacks majority-vote oversampling/framing validation; SPI duplex records one byte and has no FIFO. These are demonstrations, not complete peripheral IP blocks. Because output timing is instruction dependent, inspect the schedule when adding instructions to firmware loops.

## Software, RTL and netlist build

Developed for Linux, with Python 3.10+, `pytest`, Cocotb 2.x, Icarus Verilog
(`iverilog`), and Yosys. Optionally install Verilator for lint. Example:

```bash
sudo apt-get update
sudo apt-get install -y make iverilog yosys verilator
python3 -m pip install -r requirements-test.txt
```

From the root of this repository:

```bash
make software       # assembly + 16 Python ISA reference tests
make rtl            # 20 cocotb tests against RTL
make synth          # generated generic-cell Verilog/JSON netlist via Yosys
make gate-test      # rerun the same cocotb suite on generic netlist
make verify         # all above steps; fails if tools are missing
make lint           # optional Verilator structural lint
```

`make synth` regenerates `build/netlist_generic.v`,
`build/netlist_generic.json`, a SHA-256 file and `build/yosys_generic.log`.
Yosys maps the design to generic logic and flip-flops. The committed netlist
was generated by Yosys and replayed through the same external-pin tests as
the RTL. IHP SG13CMOS5L Liberty mapping and static timing remain future work.

`.github/workflows/test.yaml` runs all four stages on an Ubuntu GitHub runner
with Icarus/Yosys, preserves separate test reports, and uploads the generated
netlist/logs as artifacts. Passing runs on `main` also commit the netlist and
verification evidence. See
[`VERIFICATION.md`](VERIFICATION.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), and [`docs/CI_GUIDE.md`](docs/CI_GUIDE.md).

The assembler emits `build/NAME.hex` (16-bit instruction words),
`build/NAME.lst` (annotated instructions) and `build/NAME.bin` (SPI programming
bytes beginning with `01 00`). Five valid binaries are included.

To program via a Linux SPI master such as a Raspberry Pi, wire electrically compatible SPI to `ui[0:2]`, hold `rst_n=1`, supply 12 MHz `clk`, then:

```bash
pip install spidev
python3 tools/upload_spidev.py build/spi_mode0.bin --bus 0 --device 0 --speed 250000
```

The uploader sends the `.bin` payload under one CS frame, then `[0x02, 0x00]` under a **second** CS frame to run at PC=0. A microcontroller, FPGA or logic analyzer capable of generating SPI mode 0 can do the same. This interface is not electrically compatible with arbitrary 5 V hosts.

## Tapeout preparation (not yet completed)

`info.yaml` uses a **6x4 tile target**, per Jane Street's announcement. The
original GDS workflow is preserved as `docs/templates/gds.yaml.disabled`.
The active Actions workflow performs simulation and generic synthesis only.
`docs/info.md` is the project's datasheet.

1. Run `python3 -m pytest -q test/test_reference.py` and `cd test && make SIM=icarus`. Get cycle-accurate functional coverage on the **RTL** rather than only the Python model.
2. Run synthesis with the actual `ihp-sg13cmos5l` libraries. Measure sequential/mux area: instruction memory currently maps to ~1,024 storage bits, not an SRAM macro. **Do not assume** it fits 6x4 from source-line count.
3. Run Tiny Tapeout/LibreLane place-and-route, timing closure, DRC, LVS, and precheck. Check IO pin/tri-state handling and that the `6x4` validator accepts this entry.
4. After gate-level test, test on FPGA or silicon-compatible IO rig. Test asynchronous SPI at boundaries, external electrical I²C pull-up rise times, random branch programs, and clock ranges.
5. Confirm entrant/team metadata and use the competition's official registration/submission workflow when ready for a physical submission.

**Open issues:** no actual mapped silicon area or max frequency is claimed, only an intended clock; no GDS has been generated, no sign-off or hardware validation. A hardened competition entry requires those steps and probably further architecture optimization.

## License and sources

Apache License 2.0. Designed as a new reference implementation for the [Jane Street competition](https://blog.janestreet.com/protocol-emulator-asic-competition/) using the standard [Tiny Tapeout CMOS5L Verilog template](https://github.com/TinyTapeout/ttihp-verilog-template/tree/cmos5l). No Jane Street endorsement or prize qualification is claimed.
