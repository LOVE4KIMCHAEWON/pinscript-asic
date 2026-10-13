# PinScript v2 delivery — 2026-10-13

**Project scope:** FPGA/ASIC synthesizable RTL of an SPI-reprogrammable 8-pin
protocol I/O processor and an automated simulation/synthesis workflow.

## Implemented

- 64×16 programmable instruction memory, 6-bit PC, 8-bit A/B/X registers,
  zero flag, deterministic WAIT counter, GPIO output/OE registers.
- Config SPI loader with WRITE, RUN, HALT and 3-stage async-input sampling.
- True SPI Mode 0 full duplex via independent TX A / RX B accumulators;
  UART TX/RX and I2C open-drain write demonstration programs.
- Python assembler, SPI upload utility, reference ISA model, Cocotb RTL
  tests, randomized clock-by-clock model comparison, GitHub Actions.
- Yosys generic-cell netlist generator and gate-level Cocotb replay.

## Evidence in author's environment

- `make software` **15 passed** (including exhaustive 256 UART TX bytes and
  256 SPI RX bytes); all five firmwares assembled, <=64 words each.
- Python syntax, shell script syntax, `info.yaml` and CI YAML parsed.
- RTL/cocotb and Yosys executable stages were attempted but could not run:
  this environment lacks Cocotb, Icarus, Yosys and network package access.
- No generic or IHP stdcell netlist, timing result, area estimate, GDS,
  post-route validation, FPGA test, or silicon test is represented as done.

## Files to start with

- `src/project.v` — top-level synthesizable RTL
- `docs/ARCHITECTURE.md` — timing and instruction set contract
- `firmware/` and `build/*.hex, *.bin, *.lst` — executable examples
- `test/test.py` — ten real RTL/generic-netlist Cocotb cases
- `test/test_reference.py` — fifteen **executed** reference regressions
- `scripts/synth_generic.sh` — runnable Yosys netlist build
- `docs/CI_GUIDE.md` — run the entire RTL+netlist verification in GitHub Actions
- `VERIFICATION.md` — exact limitations

## Not a final competition submission

Replace the entrant name in `info.yaml`, make the repository publicly
accessible, run and fix RTL/gate-level regressions, and run IHP PDK mapping
plus 6×4 validation/STA before claiming chip readiness. Physical hardening,
GDS, DRC/LVS and tapeout have intentionally not been performed here.
