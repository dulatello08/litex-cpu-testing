#!/usr/bin/env python3

import os
import argparse
import sys

from migen import *
from litex.soc.cores.clock import *
from litex.soc.integration.soc import SoCRegion
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litedram.modules import IS42S16160
from litedram.phy import GENSDRPHY

from litex.build.generic_platform import *
from litex.build.lattice import LatticePlatform
from litex.build.io import DDROutput

# Define minimal ULX3S platform
_io = [
    ("clk_25mhz", 0, Pins("G2"), IOStandard("LVCMOS33")),
    ("rst", 0, Pins("R1"), IOStandard("LVCMOS33")), # FIRE1 as reset
    ("serial", 0,
        Subsignal("tx", Pins("L4")), # FPGA transmits to ftdi
        Subsignal("rx", Pins("M1")), # FPGA receives from ftdi
        IOStandard("LVCMOS33")
    ),
    ("sdram_clock", 0, Pins("F19"), IOStandard("LVCMOS33")),
    ("sdram", 0,
        Subsignal("a",     Pins("M20 M19 L20 L19 K20 K19 K18 J20 J19 H20 N19 G20 G19")),
        Subsignal("dq",    Pins("J16 L18 M18 N18 P18 T18 T17 U20 E19 D20 D19 C20 E18 F18 J18 J17")),
        Subsignal("we_n",  Pins("T20")),
        Subsignal("ras_n", Pins("R20")),
        Subsignal("cas_n", Pins("T19")),
        Subsignal("cs_n",  Pins("P20")),
        Subsignal("cke",   Pins("F20")),
        Subsignal("ba",    Pins("P19 N20")),
        Subsignal("dm",    Pins("U19 E20")),
        IOStandard("LVCMOS33")
    ),
]

class Platform(LatticePlatform):
    default_clk_name   = "clk_25mhz"
    default_clk_period = 1e9/25e6

    def __init__(self, device="LFE5U-85F-6BG381C", **kwargs):
        LatticePlatform.__init__(self, device, _io, toolchain="trellis", **kwargs)

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq, sdram_rate="1:1"):
        self.rst = Signal()
        self.clock_domains.cd_sys    = ClockDomain()
        self.clock_domains.cd_sys_ps = ClockDomain(reset_less=True)

        # SDRAM clock domains
        self.clock_domains.cd_sys2x    = ClockDomain()
        self.clock_domains.cd_sys2x_ps = ClockDomain(reset_less=True)

        # PLL
        self.submodules.pll = pll = ECP5PLL()
        self.comb += pll.reset.eq(self.rst)
        pll.register_clkin(platform.request("clk_25mhz"), 25e6)
        
        # 50MHz System Clock
        pll.create_clkout(self.cd_sys,    sys_clk_freq)
        
        # 166MHz SDRAM Clock
        self.clock_domains.cd_sdram    = ClockDomain()
        self.clock_domains.cd_sdram_ps = ClockDomain(reset_less=True)
        
        pll.create_clkout(self.cd_sdram,    166e6)
        pll.create_clkout(self.cd_sdram_ps, 166e6, phase=270) # Phase shift for output
        
        # Drive SDRAM clock pin
        self.specials += DDROutput(1, 0, platform.request("sdram_clock"), ClockSignal("sdram_ps"))

class BaseSoC(SoCCore):
    def __init__(self, platform):
        sys_clk_freq = int(50e6)
        
        # SoCCore
        SoCCore.__init__(self, platform, clk_freq=sys_clk_freq,
            cpu_type="vexriscv",
            integrated_main_ram_size=0x0,
            integrated_rom_size=0x8000,
        )

        # CRG
        self.submodules.crg = _CRG(platform, sys_clk_freq)
        
        # SDRAM
        self.submodules.sdrphy = GENSDRPHY(platform.request("sdram"), sys_clk_freq=166e6, cl=3)
        self.add_sdram("sdram",
            phy                     = self.sdrphy,
            module                  = IS42S16160(166e6, "1:1"),
            origin                  = self.mem_map["main_ram"],
            size                    = 0x2000000, # 32MB
            l2_cache_size           = 8192,
            l2_cache_min_data_width = 128,
            l2_cache_reverse        = False
        )
        self.sdrphy.clock_domain = "sdram"

def main():
    platform = Platform()
    soc = BaseSoC(platform)
    builder = Builder(soc, output_dir="build/soc", csr_csv="csr.csv")
    builder.build(build_name="riscv_soc")

if __name__ == "__main__":
    main()
