PROJ = litex_testing
PIN_DEF = ulx3s_v316.lpf
DEVICE = 85k

# Files
SRCS = rtl/top.sv rtl/unified_memory.sv build/litescope/gateware/litescope_core.v

# Tools
YOSYS = yosys
NEXTPNR = nextpnr-ecp5
ECPPACK = ecppack
PYTHON = .venv/bin/python3

all: $(PROJ).bit

# Generate LiteScope
build/litescope/gateware/litescope_core.v: scripts/gen_litescope.py
	$(PYTHON) scripts/gen_litescope.py
	# Fix LUT4 parameter case for Yosys
	sed 's/\.init (/.INIT (/g' build/litescope/gateware/litescope_core.v > build/litescope/gateware/litescope_core.v.tmp && mv build/litescope/gateware/litescope_core.v.tmp build/litescope/gateware/litescope_core.v

# Synthesis
$(PROJ).json: $(SRCS) build/litescope/gateware/litescope_core.v
	# Copy init file to current dir for yosys to find it
	cp build/litescope/gateware/*.init .
	$(YOSYS) -p "read_verilog -sv $(SRCS); synth_ecp5 -top top -json $@"

# PnR
$(PROJ).config: $(PROJ).json $(PIN_DEF)
	$(NEXTPNR) --$(DEVICE) --package CABGA381 --json $(PROJ).json --lpf $(PIN_DEF) --textcfg $@

# Bitstream
$(PROJ).bit: $(PROJ).config
	$(ECPPACK) $< $@

prog: $(PROJ).bit
	fujprog $(PROJ).bit

clean:
	rm -f *.json *.config *.bit *.init
	rm -rf build/litescope

.PHONY: all clean prog
