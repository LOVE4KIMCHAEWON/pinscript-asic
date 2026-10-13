# Reproduce RTL and generic-netlist verification

## GitHub Actions

Push to the repository or open **Actions → regression → Run workflow**.
The active workflow `.github/workflows/test.yaml` uses Ubuntu 24.04 and
Python 3.12. It installs Icarus Verilog, Yosys, Verilator and pinned Python
dependencies, then:

1. Assembles all five firmware examples and checks that committed outputs
   match the regenerated files.
2. Runs the software reference tests and the external-pin RTL suite.
3. Lints RTL, synthesizes the generic netlist and runs structural assertions.
4. Replays the same external-pin suite on the generated netlist.
5. Records JUnit counts, source/firmware/netlist checksums, tool versions,
   generic cell counts and reviewed lint warnings.

On a passing `main` run, the workflow commits the generated netlist and
verification evidence using the repository's Actions token. The resulting
report identifies the tested source commit; the later artifact-only commit
contains those outputs. The Actions token does not recursively trigger a
new push workflow. Pull-request runs validate and upload artifacts without
pushing generated files to `main`.

The **generic-netlist-and-verification** artifact preserves logs, separate
RTL/generic JUnit files, firmware, Verilog/JSON netlist and its checksum.
For authoritative pass/fail and source provenance, read `reports/latest.md`
and `reports/summary.json`, and check the linked Actions run.

## Local Linux flow

```sh
sudo apt-get update
sudo apt-get install -y make iverilog yosys verilator
python3 -m pip install -r requirements-test.txt
make software
make rtl
make lint
make synth
make gate-test
```

`make synth` writes `build/netlist_generic.v`, `.json`, `.sha256` and
`build/yosys_generic.log`. To preserve independent JUnit files:

```sh
make rtl COCOTB_RESULTS_FILE=results-rtl.xml
make gate-test COCOTB_RESULTS_FILE=results-generic.xml
sha256sum -c build/netlist_generic.sha256
```

Verilog and JSON synthesis output may vary across Yosys/ABC versions.
Use the tool versions in the report when comparing generated files.
Both simulation modes load firmware through the top-level SPI pins; tests
do not depend on internal RTL register names.

## Physical design scope

Only simulation and generic synthesis are active. The original physical
workflow is preserved at `docs/templates/gds.yaml.disabled`; it cannot run
from that location. Generic gates are not IHP standard cells, and no STA,
GDS or place-and-route is performed by the active workflow.
