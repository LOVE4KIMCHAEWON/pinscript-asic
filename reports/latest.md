# Executed verification results

Source commit: `fd3bd888f8212cd5dd77dca21dff331e8fd90033`

[GitHub Actions run](https://github.com/LOVE4KIMCHAEWON/pinscript-asic/actions/runs/38346980218)

| Suite | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| software | 16 | 0 | 0 |
| rtl | 18 | 0 | 0 |
| generic | 18 | 0 | 0 |

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

Generic synthesis and functional simulation; no PDK mapping, STA, GDS or place-and-route.

See `yosys.log` for warnings and generic cell statistics.
