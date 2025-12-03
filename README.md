# LiteX Testing Project

This project integrates a custom SystemVerilog module with LiteScope for debugging on the ULX3S FPGA, using the **standard USB/UART connection** (no JTAG probe required).

## Structure

- `rtl/`: SystemVerilog source files.
  - `top.sv`: Top-level module connecting LiteScope UARTBone to user logic.
- `scripts/`: Python scripts.
  - `gen_litescope.py`: Generates the LiteScope core with UARTBone and input CSRs.
  - `interactive_control.py`: Example script to send inputs to the FPGA interactively.
- `build/`: Build artifacts.
- `Makefile`: Build automation.

## Prerequisites

- Yosys
- Nextpnr-ecp5
- Ecppack (Project Trellis)
- Python 3 with LiteX installed (use `.venv` if available).

## Building

Run `make` to generate the LiteScope core and build the bitstream:

```bash
make
```

## Programming

To upload the bitstream to ULX3S:

```bash
make prog
```

## Interactive Debugging (No JTAG needed)

1.  **Start LiteX Server**:
    Open a terminal and run the LiteX server to bridge the USB UART to the Wishbone bus.
    Replace `/dev/tty.usbserial-XXXX` with your actual serial port.

    ```bash
    .venv/bin/litex_server --uart --uart-port /dev/tty.usbserial-123456 --uart-baudrate 115200
    ```

2.  **Control Inputs Interactively**:
    In another terminal, run the control script to send data to your module:

    ```bash
    .venv/bin/python3 scripts/interactive_control.py
    ```
    You should see the LEDs on the ULX3S blinking as the script writes to the `user_inputs` register.

3.  **Capture Waveforms**:
    In a third terminal, use the LiteScope CLI to capture traces:

    ```bash
    .venv/bin/litescope_cli --csv analyzer.csv
    ```
    This will dump a `.vcd` file that you can open in GTKWave.

## Customization

- **User Logic**: Modify `rtl/top.sv`. The `user_inputs` wire contains data sent from the PC. The `probe_signals` wire sends data back to the analyzer.
- **Probes**: To change what signals are probed, modify the `probe_signals` assignment in `rtl/top.sv`.
