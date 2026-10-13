# Generate and verify the generic netlist without local EDA tools

## One-machine Linux flow

Install Icarus Verilog, Yosys, and Python packages, following `README.md`.
From the project root:

```sh
make software
make rtl
make synth
make gate-test
```

The `make synth` output files are:

```
build/netlist_generic.v
build/netlist_generic.json
build/netlist_generic.sha256
build/yosys_generic.log
```

`make gate-test` reruns **the same 10 functional tests** against the
post-Yosys **generic** netlist. Confirm both RTL and gate tests pass before
claiming verified equivalence for the tested scenarios.

## No Linux setup: GitHub Actions

1. Create a repository and upload the entire contents of the ZIP, preserving
   `.github/workflows/test.yaml` and directory structure. Replace the
   placeholder `project.author` in `info.yaml` with your actual team name.
2. Open **Actions → regression**, then choose **Run workflow**. It installs
   Icarus and Yosys, assembles firmware and runs software/RTL/gate tests.
3. Only if the workflow finishes green, open its result and download the
   **generic-netlist-and-verification** artifact. This contains the generated
   netlist, JSON, checksum, and Yosys synthesis report.
4. Check the synthesis warnings, memory mapping (the 64×16 RAM typically
   uses flip-flops in a generic technology), and gate-level test logs.

This procedure has **not been executed by the authoring environment**. A
successful script installation or source upload does not itself verify the
circuit. If any step fails, the netlist cannot be treated as verified.

## For eventual physical design

A *generic* synthesized netlist cannot be used as a sign-off PDK netlist.
Use the official IHP CMOS5L Tiny Tapeout template and its `gds` workflow for
PDK mapping, routed standard cells and GDS. The project already contains a
starter `.github/workflows/gds.yaml` but this flow is not proven here.

IHP Tiny Tapeout gate-level simulation convention uses the **unpowered**
`nl` netlist (not `pnl`): after a successful hardening flow, copy
`runs/wokwi/final/nl/<top>.nl.v` to `test/gate_level_netlist.v` and use
`cd test && make GATES=yes` with the correct `PDK_ROOT` installed.

The official competition specifies a 6×4 tile allocation. The publicly
visible stock CMOS5L template may not yet list 6×4 among its accepted tile
sizes; use the contest-updated flow rather than silently changing the
required area or assuming success.
