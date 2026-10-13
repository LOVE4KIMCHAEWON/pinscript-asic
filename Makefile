PYTHON ?= python3
.PHONY: all firmware software rtl synth gate-test verify lint clean-sim
all: verify
firmware:
	@for p in firmware/*.asm; do $(PYTHON) tools/assemble.py "$$p"; done
software: firmware
	$(PYTHON) -m pytest -q test/test_reference.py
rtl: firmware
	$(MAKE) -C test SIM=icarus GATES=no
synth:
	bash scripts/synth_generic.sh
gate-test: synth firmware
	$(MAKE) -C test SIM=icarus GATES=generic
verify: software rtl synth gate-test
lint:
	verilator --lint-only -Wall -Wno-fatal --top-module tt_um_pinscript src/project.v
clean-sim:
	rm -rf test/sim_build test/results.xml
