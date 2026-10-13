# Executed verification results

Source commit: `07c0cece8d6e671b7c5ff27bc5715701700c5004`

[GitHub Actions run](https://github.com/LOVE4KIMCHAEWON/pinscript-asic/actions/runs/38347520297)

| Suite | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| software | 16 | 0 | 0 |
| rtl | 20 | 0 | 0 |
| generic | 20 | 0 | 0 |

Yosys completed `hierarchy -check`, `synth`, and `check -assert`.

The RTL and synthesized netlist passed the same external-pin test suite. This is regression evidence for tested scenarios, not a formal equivalence proof.

Netlist SHA-256: `60cb932d8f718734aae5607b2ad9b796560d96e2c15714188be85b9ba07a2736`

RTL SHA-256: `63094b6174e9cf79b682c9a9c22e7a05a2c11dffbfc4503b1e52b147c5875108`

## Tool versions

- yosys: `Yosys 0.33 (git sha1 2584903a060)`
- iverilog: `Icarus Verilog version 12.0 (stable) ()`
- verilator: `Verilator 5.020 2024-01-01 rev (Debian 5.020-1)`
- python: `Python 3.12.15`
- cocotb: `2.0.1`

## Generic synthesis statistics

Total cells: **3572**. Unmapped memories: **0**.

| Cell type | Count |
| --- | ---: |
| `$_ANDNOT_` | 350 |
| `$_AND_` | 16 |
| `$_DFFE_PP_` | 960 |
| `$_DFF_P_` | 5 |
| `$_MUX_` | 1516 |
| `$_NAND_` | 23 |
| `$_NOR_` | 68 |
| `$_NOT_` | 136 |
| `$_ORNOT_` | 36 |
| `$_OR_` | 322 |
| `$_SDFFE_PN0P_` | 13 |
| `$_SDFFE_PP0P_` | 10 |
| `$_SDFF_PN0_` | 69 |
| `$_SDFF_PN1_` | 4 |
| `$_XNOR_` | 3 |
| `$_XOR_` | 41 |

## Lint warnings reviewed

- `%Warning-DECLFILENAME: src/project.v:5:8: Filename 'project' does not match MODULE name: 'tt_um_pinscript'`
- `%Warning-UNUSEDSIGNAL: src/project.v:19:15: Bits of signal are not used: 'mosi_sync'[2]`
- `%Warning-UNUSEDSIGNAL: src/project.v:27:17: Bits of signal are not used: 'ir'[11]`
- `%Warning-UNUSEDSIGNAL: src/project.v:44:15: Bits of signal are not used: 'spi_shift'[7]`

These warnings concern the top filename and intentionally unused register/instruction bits; no latch, width, or multiple-driver warning was reported.

Generic synthesis and functional simulation; no PDK mapping, STA, GDS or place-and-route.

[Synthesis log](yosys.log) contains the structural checks.
