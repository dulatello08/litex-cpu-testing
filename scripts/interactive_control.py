#!/usr/bin/env python3

import sys
import time
from litex import RemoteClient

# Connect to the LiteX server
wb = RemoteClient(csr_csv="csr.csv")
wb.open()

print("Connected to LiteX Server!")

try:
    print("Commands:")
    print("  read <addr>          : Read byte from address (hex/dec)")
    print("  write <addr> <data>  : Write byte <data> to address <addr>")
    print("  q                    : Quit")
    
    while True:
        cmd_str = input("> ").strip()
        if not cmd_str:
            continue
        if cmd_str.lower() == 'q':
            break
            
        parts = cmd_str.split()
        cmd = parts[0].lower()
        
        try:
            val = 0
            if cmd == 'read':
                if len(parts) < 2:
                    print("Usage: read <addr>")
                    continue
                addr = int(parts[1], 0)
                # Scheme: [15:0]=addr, [25]=req
                val = (addr & 0xFFFF) | (1 << 25)
                wb.regs.main_user_inputs.write(val)
                
                # Wait a bit for the transaction to happen (UART is slow, so it's likely done)
                # But just in case, we can read the output.
                # The output is constantly driven by mem_rdata.
                # Since mem_rdata holds the last read value, we just read the CSR.
                read_val = wb.regs.main_user_outputs.read()
                print(f"Read Req sent to Addr 0x{addr:04X}. Result: 0x{read_val & 0xFF:02X}")
                
            elif cmd == 'write':
                if len(parts) < 3:
                    print("Usage: write <addr> <data>")
                    continue
                addr = int(parts[1], 0)
                data = int(parts[2], 0)
                # Scheme: [15:0]=addr, [23:16]=data, [24]=we, [25]=req
                val = (addr & 0xFFFF) | ((data & 0xFF) << 16) | (1 << 24) | (1 << 25)
                wb.regs.main_user_inputs.write(val)
                print(f"Write Req sent: Addr 0x{addr:04X} = 0x{data:02X}")
                
            else:
                print("Unknown command")
                
        except ValueError:
            print("Invalid number format")

except KeyboardInterrupt:
    print("\nExiting...")
finally:
    wb.close()
    print("Connection closed.")
