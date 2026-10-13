# SPDX-License-Identifier: Apache-2.0
SIM ?= icarus
TOPLEVEL_LANG ?= verilog
SRC_DIR = $(CURDIR)/../src
PROJECT_SOURCES = project.v
ifeq ($(GATES),generic)
  SIM_BUILD = sim_build/generic
  VERILOG_SOURCES += $(CURDIR)/../build/netlist_generic.v
else ifneq ($(GATES),yes)
  SIM_BUILD = sim_build/rtl
  VERILOG_SOURCES += $(addprefix $(SRC_DIR)/,$(PROJECT_SOURCES))
else
  SIM_BUILD = sim_build/gl
  COMPILE_ARGS += -DGL_TEST -DFUNCTIONAL -DSIM
  VERILOG_SOURCES += $(PDK_ROOT)/ihp-sg13cmos5l/libs.ref/sg13cmos5l_io/verilog/sg13cmos5l_io.v
  VERILOG_SOURCES += $(PDK_ROOT)/ihp-sg13cmos5l/libs.ref/sg13cmos5l_stdcell/verilog/sg13cmos5l_stdcell.v
  VERILOG_SOURCES += $(CURDIR)/gate_level_netlist.v
endif
COMPILE_ARGS += -I$(SRC_DIR)
VERILOG_SOURCES += $(CURDIR)/tb.v
TOPLEVEL = tb
COCOTB_TEST_MODULES = test,test_control
include $(shell cocotb-config --makefiles)/Makefile.sim
