# LiteX Testing Project

This repository contains two distinct projects for the ULX3S FPGA:
1.  **LiteScope Logic Analyzer**: A custom SystemVerilog design (`rtl/top.sv`) instrumented with LiteScope for debugging without JTAG.
2.  **RISC-V SoC**: A full LiteX-generated SoC (`scripts/gen_soc.py`) running a VexRiscv CPU, for which you can write C firmware.

## Structure

- `rtl/`: SystemVerilog source files (for Logic Analyzer mode).
  - `top.sv`: Top-level module connecting LiteScope UARTBone to user logic.
  - `unified_memory.sv`: Custom memory controller module.
- `scripts/`: Python scripts.
  - `gen_soc.py`: Builds the RISC-V SoC (Gateware + Software headers).
  - `gen_litescope.py`: Generates the LiteScope core.
  - `interactive_control.py`: Host script for Logic Analyzer mode.
- `firmware/`: C firmware for the RISC-V SoC.
  - `main.c`: User application code.
  - `Makefile`: Builds the firmware using LiteX libraries.
- `build/`: Build artifacts.

## Prerequisites

- Yosys
- Nextpnr-ecp5
- Ecppack (Project Trellis)
- Python 3 with LiteX installed.
- RISC-V GCC Toolchain (bundled with LiteX or installed separately).

---

## Mode 1: Logic Analyzer (LiteScope)

This mode builds the `rtl/top.sv` design which lets you peek/poke signals using a UART connection.

### Building
Run `make` to generate the LiteScope core and build the bitstream:
```bash
make
```

### Programming
Upload the bitstream to ULX3S:
```bash
make prog
```

### Usage
1.  **Start LiteX Server**:
    Bridging USB UART to Wishbone bus.
    ```bash
    litex_server --uart --uart-port /dev/tty.usbserial-XXXX --uart-baudrate 115200
    ```

2.  **Interactive Control**:
    Send data to the `user_inputs` wire in `top.sv`:
    ```bash
    python3 scripts/interactive_control.py
    ```

3.  **Capture Waveforms**:
    ```bash
    litescope_cli --csv analyzer.csv
    ```

---

## Mode 2: RISC-V SoC + Firmware

This mode generates a complete SoC with a CPU, SDRAM, and UART, allowing you to run C code.

### 1. Build the SoC
Generate the gateware (bitstream) and software support files (headers/libraries):
```bash
make soc
```
*Output: `build/soc/gateware/riscv_soc.bit` and `build/soc/software/...`*

### 2. Writie & Build Firmware
The firmware source code is in `firmware/`.
- Edit `firmware/main.c` to change the code.
- Build the binary:
  ```bash
  cd firmware
  make
  ```
*Output: `firmware/firmware.bin`*

### 3. Run on FPGA
You can load the SoC bitstream and then the firmware over UART using `litex_term`.

```bash
# Assuming your bitstream is at build/soc/gateware/riscv_soc.bit
litex_term --kernel firmware/firmware.bin /dev/tty.usbserial-XXXX
```
*Note: If the bitstream is already flashed, you can just use `litex_term` to upload the firmware kernel.*
