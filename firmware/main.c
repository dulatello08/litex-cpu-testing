#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// LiteX headers
#include <generated/csr.h>
#include <irq.h>
#include <libbase/console.h>
#include <libbase/uart.h>

// UART Helpers
static char serial_read(void) {
  char c;
  // Wait for RX not empty (0 = Not Empty, 1 = Empty)
  while (uart_rxempty_read() == 1)
    ;
  c = uart_rxtx_read();
  // Clear UART events (RX/TX pending)
  uart_ev_pending_write(uart_ev_pending_read());
  return c;
}

static void uart_putc(char c) {
  if (c == '\n')
    uart_putc('\r');
  while (uart_txfull_read())
    ;
  uart_rxtx_write(c);
  uart_ev_pending_write(uart_ev_pending_read());
}

static void putstr(const char *s) {
  while (*s) {
    uart_putc(*s);
    s++;
  }
}

static void puthex(uint32_t val) {
  const char hex[] = "0123456789ABCDEF";
  putstr("0x");
  for (int i = 7; i >= 0; i--) {
    uart_putc(hex[(val >> (i * 4)) & 0xF]);
  }
}

static uint32_t gethex(void) {
  uint32_t val = 0;
  char c;
  // Skip leading whitespace
  while (1) {
    c = serial_read();
    uart_putc(c); // Echo
    if (c != ' ' && c != '\r' && c != '\n')
      break;
  }

  // Parse hex
  while (1) {
    if (c >= '0' && c <= '9') {
      val = (val << 4) | (c - '0');
    } else if (c >= 'A' && c <= 'F') {
      val = (val << 4) | (c - 'A' + 10);
    } else if (c >= 'a' && c <= 'f') {
      val = (val << 4) | (c - 'a' + 10);
    } else {
      return val;
    }
    c = serial_read();
    uart_putc(c); // Echo
  }
}

// Map printf to our functions for convenience
int printf(const char *fmt, ...) {
  putstr(fmt);
  return 0;
}

// Unified Memory Helpers
void um_data_wait_ack(void) {
  while (unified_memory_d_ack_read() == 0)
    ;
}

void um_inst_wait_ack(void) {
  while (unified_memory_i_ack_read() == 0)
    ;
}

void um_write_word(uint32_t addr, uint32_t data) {
  unified_memory_d_addr_write(addr);
  unified_memory_d_wdata_write(data);
  // Control: [0]:REQ=1, [1]:WE=1, [3:2]:SIZE=2 (Word) -> 1011 -> 0xB
  unified_memory_d_ctrl_write(0xB);
  um_data_wait_ack();
  unified_memory_d_ctrl_write(0);
}

uint32_t um_read_word(uint32_t addr) {
  unified_memory_d_addr_write(addr);
  // Control: [0]:REQ=1, [1]:WE=0, [3:2]:SIZE=2 (Word) -> 1001 -> 0x9
  unified_memory_d_ctrl_write(0x9);
  um_data_wait_ack();
  uint32_t data = unified_memory_d_rdata_read();
  unified_memory_d_ctrl_write(0);
  return data;
}

void um_read_inst(uint32_t addr, uint32_t *out_buf) {
  unified_memory_i_addr_write(addr);
  unified_memory_i_req_write(1);
  um_inst_wait_ack();
  out_buf[0] = unified_memory_i_rdata0_read();
  out_buf[1] = unified_memory_i_rdata1_read();
  out_buf[2] = unified_memory_i_rdata2_read();
  out_buf[3] = unified_memory_i_rdata3_read();
  unified_memory_i_req_write(0);
}

int main(void) {
  putstr("\n\n=== Unified Memory Firmware Interactive Mode ===\n");
  putstr("Commands:\n");
  putstr("  w <addr> <data> : Write Word\n");
  putstr("  r <addr>        : Read Word\n");
  putstr("  i <addr>        : Fetch Instruction (128-bit)\n");

  uint32_t addr, data;
  uint32_t buf[4];

  while (1) {
    putstr("\n> ");
    char cmd = serial_read();
    uart_putc(cmd); // Echo command
    uart_putc(' ');

    switch (cmd) {
    case 'w':
      if (cmd == '\r' || cmd == '\n')
        break; // Ignore empty newlines
      addr = gethex();
      data = gethex();
      um_write_word(addr, data);
      putstr(" OK");
      break;
    case 'r':
      addr = gethex();
      data = um_read_word(addr);
      putstr(" = ");
      puthex(data);
      break;
    case 'i':
      addr = gethex();
      um_read_inst(addr, buf);
      putstr(" = ");
      puthex(buf[3]);
      putstr("_");
      puthex(buf[2]);
      putstr("_");
      puthex(buf[1]);
      putstr("_");
      puthex(buf[0]);
      break;
    default:
      if (cmd != '\r' && cmd != '\n') {
        putstr("?");
      }
      break;
    }
  }
  return 0;
}
