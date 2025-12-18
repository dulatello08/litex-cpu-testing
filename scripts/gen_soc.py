#!/usr/bin/env python3

import os
import argparse
import sys

from migen import *
from litex.soc.cores.clock import *
from litex.soc.integration.soc import SoCRegion
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.interconnect.csr import *
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
        
        # 50MHz SDRAM Clock (Sync with Sys)
        self.clock_domains.cd_sdram    = ClockDomain()
        self.clock_domains.cd_sdram_ps = ClockDomain(reset_less=True)
        
        pll.create_clkout(self.cd_sdram,    50e6)
        pll.create_clkout(self.cd_sdram_ps, 50e6, phase=90) # Phase shift for output

        # Reset
        try:
            rst_pin = platform.request("rst")
            self.comb += self.rst.eq(rst_pin)
        except:
            pass
        
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
        self.submodules.sdrphy = GENSDRPHY(platform.request("sdram"), sys_clk_freq=50e6, cl=3)
        self.add_sdram("sdram",
            phy                     = self.sdrphy,
            module                  = IS42S16160(50e6, "1:1"),
            origin                  = self.mem_map["main_ram"],
            size                    = 0x2000000, # 32MB
            l2_cache_size           = 8192,
            l2_cache_min_data_width = 128,
            l2_cache_reverse        = False
        )
        self.sdrphy.clock_domain = "sdram"
        
        # Unified Memory (Custom Module)
        self.submodules.unified_memory = UnifiedMemory(platform)

class UnifiedMemory(Module, AutoCSR):
    def __init__(self, platform):
        # Data Port CSRs
        self.d_addr  = CSRStorage(32, description="Data Address")
        self.d_wdata = CSRStorage(32, description="Data Write Data")
        self.d_rdata = CSRStatus(32,  description="Data Read Data")
        self.d_ctrl  = CSRStorage(4,  description="Data Control: [0]:REQ, [1]:WE, [3:2]:SIZE")
        self.d_ack   = CSRStatus(1,   description="Data Acknowledge")

        # Instruction Port CSRs
        self.i_addr   = CSRStorage(32, description="Instruction Address")
        self.i_req    = CSRStorage(1,  description="Instruction Request")
        self.i_rdata0 = CSRStatus(32, description="Instruction Read Data [31:0]")
        self.i_rdata1 = CSRStatus(32, description="Instruction Read Data [63:32]")
        self.i_rdata2 = CSRStatus(32, description="Instruction Read Data [95:64]")
        self.i_rdata3 = CSRStatus(32, description="Instruction Read Data [127:96]")
        self.i_ack    = CSRStatus(1,  description="Instruction Acknowledge")

        # Signals
        d_rdata_sig = Signal(32)
        d_ack_sig   = Signal()
        i_rdata_sig = Signal(128)
        i_ack_sig   = Signal()

        # Connect Status
        self.comb += [
            self.d_rdata.status.eq(d_rdata_sig),
            self.d_ack.status.eq(d_ack_sig),
            self.i_rdata0.status.eq(i_rdata_sig[0:32]),
            self.i_rdata1.status.eq(i_rdata_sig[32:64]),
            self.i_rdata2.status.eq(i_rdata_sig[64:96]),
            self.i_rdata3.status.eq(i_rdata_sig[96:128]),
            self.i_ack.status.eq(i_ack_sig)
        ]

        # Add Source
        platform.add_source("rtl/unified_memory.sv")

        # Instantiate
        self.specials += Instance("unified_memory",
            p_MEM_SIZE_BYTES = 65536,
            i_clk        = ClockSignal(),
            i_rst        = ResetSignal(),

            # Instruction Port
            i_if_addr    = self.i_addr.storage,
            i_if_req     = self.i_req.storage,
            o_if_rdata   = i_rdata_sig,
            o_if_ack     = i_ack_sig,

            # Data Port
            i_data_addr  = self.d_addr.storage,
            i_data_wdata = self.d_wdata.storage,
            i_data_size  = self.d_ctrl.storage[2:4],
            i_data_we    = self.d_ctrl.storage[1],
            i_data_req   = self.d_ctrl.storage[0],
            o_data_rdata = d_rdata_sig,
            o_data_ack   = d_ack_sig
        )

def main():
    platform = Platform()
    soc = BaseSoC(platform)
    builder = Builder(soc, output_dir="build/soc", csr_csv="csr.csv")
    builder.build(build_name="riscv_soc")

if __name__ == "__main__":
    main()
