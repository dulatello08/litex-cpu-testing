#!/usr/bin/env python3

import os
import argparse
import sys

# Monkeypatching to fix Python 3.14 / Migen name extraction issues
from litex.soc.interconnect import csr
from migen.fhdl import structure

# Patch _CSRBase (covers CSR, CSRStorage, CSRStatus)
_original_CSRBase_init = csr._CSRBase.__init__
def _new_CSRBase_init(self, *args, **kwargs):
    try:
        _original_CSRBase_init(self, *args, **kwargs)
    except ValueError:
        name = f"csr_{id(self)}"
        if 'name' in kwargs:
            kwargs['name'] = name
        else:
            args_list = list(args)
            if len(args_list) > 1:
                args_list[1] = name
            else:
                kwargs['name'] = name
            args = tuple(args_list)
        _original_CSRBase_init(self, *args, **kwargs)

csr._CSRBase.__init__ = _new_CSRBase_init

# Patch ClockDomain
_cd_counter = 0
_original_ClockDomain_init = structure.ClockDomain.__init__
def _new_ClockDomain_init(self, name=None, reset_less=False):
    global _cd_counter
    if name is None:
        try:
            _original_ClockDomain_init(self, name, reset_less)
        except ValueError:
            _cd_counter += 1
            name = f"cd_fallback_{_cd_counter}"
            print(f"DEBUG: Patching ClockDomain name to {name}")
            _original_ClockDomain_init(self, name, reset_less)
    else:
        _original_ClockDomain_init(self, name, reset_less)

structure.ClockDomain.__init__ = _new_ClockDomain_init


from migen import *
from litex.soc.cores.clock import *
from litex.soc.integration.soc import SoCRegion
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litescope import LiteScopeAnalyzer

from litex.build.generic_platform import *
from litex.build.lattice import LatticePlatform

# Define minimal ULX3S platform
_io = [
    ("clk_25mhz", 0, Pins("G2"), IOStandard("LVCMOS33")),
    ("rst", 0, Pins("R1"), IOStandard("LVCMOS33")), # FIRE1 as reset
    ("serial", 0,
        Subsignal("tx", Pins("L4")), # FPGA transmits to ftdi
        Subsignal("rx", Pins("M1")), # FPGA receives from ftdi
        IOStandard("LVCMOS33")
    ),
    ("user_inputs_port", 0, Pins(" ".join([f"inputs_{i}" for i in range(32)]))), # Virtual pins for output
    ("user_outputs_port", 0, Pins(" ".join([f"outputs_{i}" for i in range(32)]))), # Virtual pins for input
    ("user_probe", 0, Pins(" ".join([f"probe_{i}" for i in range(32)]))), # Virtual pins
]

class Platform(LatticePlatform):
    default_clk_name   = "clk_25mhz"
    default_clk_period = 1e9/25e6

    def __init__(self, device="LFE5U-85F", **kwargs):
        LatticePlatform.__init__(self, device, _io, **kwargs)

# Custom CRG to ensure sys clock domain is named "sys"
class MyCRG(Module):
    def __init__(self, clk):
        self.clock_domains.cd_sys = ClockDomain(name="sys")
        self.comb += self.cd_sys.clk.eq(clk)

class LiteScopeSoC(SoCMini):
    def __init__(self, platform, clk_freq=25e6):
        SoCMini.__init__(self, platform, clk_freq=clk_freq,
            ident="LiteScope Standalone", ident_version=True, with_ctrl=False)

        # CRG
        self.submodules.crg = MyCRG(platform.request("clk_25mhz"))
        
        # Connect system reset to our rst pin
        try:
            rst_pin = platform.request("rst")
            self.comb += self.crg.cd_sys.rst.eq(rst_pin)
        except:
            pass

        # Create scope domain explicitly
        self.clock_domains.cd_scope = ClockDomain(name="scope")
        self.cd_scope.name = "scope"

        # UARTBone (Communication with Host via FTDI USB)
        # This replaces JTAG. We use the main serial port.
        self.add_uartbone("serial", baudrate=115200)

        # Input Control (CSR Storage)
        # This allows the user to "put inputs" from the PC
        self.user_inputs = csr.CSRStorage(32, name="user_inputs", description="Inputs for the user module")
        self.add_csr("user_inputs")
        
        # Expose as port
        self.user_inputs_port = platform.request("user_inputs_port")
        self.comb += self.user_inputs_port.eq(self.user_inputs.storage)

        # Output Status (CSR Status)
        # This allows the user to "get outputs" from the FPGA
        self.user_outputs = csr.CSRStatus(32, name="user_outputs", description="Outputs from the user module")
        self.add_csr("user_outputs")

        # Expose as port
        self.user_outputs_port = platform.request("user_outputs_port")
        self.comb += self.user_outputs.status.eq(self.user_outputs_port)

        # User Probe Signals
        self.user_probe_port = platform.request("user_probe")
        
        # Analyzer
        analyzer_signals = [
            self.user_probe_port,
            self.user_inputs.storage, # Also probe the inputs we are sending
        ]
        
        self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals,
            depth        = 512,
            clock_domain = "sys", # This will drive scope domain with sys
            csr_csv      = "analyzer.csv")
        self.add_csr("analyzer")

def main():
    platform = Platform()
    soc = LiteScopeSoC(platform)
    
    # Recursive function to find and rename clock domains
    visited = set()
    def rename_fallback_to(node, new_name):
        if id(node) in visited:
            return False
        visited.add(id(node))
        
        found = False
        if hasattr(node, "clock_domains"):
            for cd in vars(node.clock_domains).values():
                if isinstance(cd, ClockDomain):
                    if cd.name.startswith("cd_fallback_"):
                        print(f"DEBUG: Renaming {cd.name} to {new_name}")
                        cd.name = new_name
                        found = True
        
        if hasattr(node, "submodules"):
            try:
                for child in node.submodules:
                    if rename_fallback_to(child, new_name):
                        found = True
            except TypeError:
                pass
        return found

    rename_fallback_to(soc, "scope")
        
    builder = Builder(soc, output_dir="build/litescope", csr_csv="csr.csv")
    builder.build(build_name="litescope_core", run=False)

if __name__ == "__main__":
    main()
