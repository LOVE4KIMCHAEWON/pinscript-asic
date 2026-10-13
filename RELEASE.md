# PinScript RTL/netlist delivery

The complete user-supplied v2 project is imported into the repository.
[Import provenance](docs/IMPORT.md) records the original archive checksum.

Delivered files include synthesizable RTL, five assembled firmware examples,
an assembler and SPI uploader, a software ISA model, 16 Python tests, 20
external-pin RTL/netlist tests, synthesis automation, and a GitHub Actions
workflow. The UART and SPI startup drivers preload their idle values before
enabling the pins.

The generated netlist is in `build/netlist_generic.v` and
`build/netlist_generic.json`, with a SHA-256 checksum. Executed CI evidence
is in `reports/latest.md`, `reports/summary.json`, the three JUnit files and
`reports/yosys.log`. Full logs and firmware are also available as Actions
artifacts. The report records its tested source commit and tool versions.

See [VERIFICATION.md](VERIFICATION.md) for coverage, fixes, warning review and
limits, and [docs/CI_GUIDE.md](docs/CI_GUIDE.md) for reproduction.

The scope ends at generic Yosys synthesis and functional netlist replay.
The original GDS workflow is retained as an inactive reference. No physical
design, PDK mapping, timing sign-off or competition submission was performed.
