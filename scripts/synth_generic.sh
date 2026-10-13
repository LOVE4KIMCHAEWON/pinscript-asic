#!/usr/bin/env bash
# Reproducible generic-cell synthesis (NOT IHP PDK mapping, NOT timing sign-off).
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v yosys >/dev/null 2>&1; then
    echo 'ERROR: yosys not installed. Debian/Ubuntu: sudo apt install yosys' >&2
    exit 127
fi
mkdir -p build
YOSYS_TOP='tt_um_pinscript'
yosys -Q -T -l build/yosys_generic.log -p \
 "read_verilog src/project.v; \
  hierarchy -check -top ${YOSYS_TOP}; \
  synth -top ${YOSYS_TOP}; \
  check -assert; \
  stat; \
  write_verilog -noattr build/netlist_generic.v; \
  write_json build/netlist_generic.json"
test -s build/netlist_generic.v
test -s build/netlist_generic.json
sha256sum build/netlist_generic.v > build/netlist_generic.sha256
printf '\nGenerated build/netlist_generic.v, .json, .sha256 and yosys_generic.log\n'
printf 'Generic Yosys gates are NOT CMOS5L mapped standard cells.\n'
