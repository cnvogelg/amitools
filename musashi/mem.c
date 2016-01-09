/* MusashiCPU <-> vamos memory interface
 *
 * written by Christian Vogelgsang <chris@vogelgsang.org>
 * under the GNU Public License V2
 */

#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "mem.h"

/* THOR: I need a *little* more memory than 16MB.
** This gives 256MB max.
*/
#define NUM_PAGES   4096

/* ----- Data ----- */
static uint8_t *ram_data;
static uint     ram_size;
static uint     ram_pages;

static read_func_t    r_func[NUM_PAGES][3];
static write_func_t   w_func[NUM_PAGES][3];
static void *         r_ctx[NUM_PAGES][3];
static void *         w_ctx[NUM_PAGES][3];

static invalid_func_t invalid_func;
static void *invalid_ctx;
static int mem_trace = 0;
static trace_func_t trace_func;
static void *trace_ctx;
static int is_end = 0;
static uint special_page = NUM_PAGES;

/* ----- RAW Access ----- */
extern uint8_t *mem_raw_ptr(void)
{
  return ram_data;
}

extern uint mem_raw_size(void)
{
  return ram_size;
}

/* ----- Default Funcs ----- */
static void default_invalid(int mode, int width, uint addr, void *ctx)
{
  printf("INVALID: %c(%d): %06x\n",(char)mode,width,addr);
}

static int default_trace(int mode, int width, uint addr, uint val, void *ctx)
{
  printf("%c(%d): %06x: %x\n",(char)mode,width,addr,val);
  return 0;
}

/* ----- End Access ----- */
static uint rx_end(uint addr, void *ctx)
{
  return 0;
}

static uint r16_end(uint addr, void *ctx)
{
  return 0x4e70; // RESET opcode
}

static void wx_end(uint addr, uint val, void *ctx)
{
  // do nothing
}

/* ----- Invalid Access ----- */
void mem_set_all_to_end(void)
{
  int i;
  for(i=0;i<NUM_PAGES;i++) {
    r_func[i][0] = rx_end;
    r_func[i][1] = r16_end;
    r_func[i][2] = rx_end;
    w_func[i][0] = wx_end;
    w_func[i][1] = wx_end;
    w_func[i][2] = wx_end;
  }
  is_end = 1;
}

static uint r8_fail(uint addr, void *ctx)
{
  invalid_func('R', 0, addr, invalid_ctx);
  mem_set_all_to_end();
  return 0;
}

static uint r16_fail(uint addr, void *ctx)
{
  invalid_func('R', 1, addr, invalid_ctx);
  mem_set_all_to_end();
  return 0;
}

static uint r32_fail(uint addr, void *ctx)
{
  invalid_func('R', 2, addr, invalid_ctx);
  mem_set_all_to_end();
  return 0;
}

static void w8_fail(uint addr, uint val, void *ctx)
{
  invalid_func('W', 0, addr, invalid_ctx);
  mem_set_all_to_end();
}

static void w16_fail(uint addr, uint val, void *ctx)
{
  invalid_func('W', 1, addr, invalid_ctx);
  mem_set_all_to_end();
}

static void w32_fail(uint addr, uint val, void *ctx)
{
  invalid_func('W', 2, addr, invalid_ctx);
  mem_set_all_to_end();
}

/* ----- RAM access ----- */
static uint mem_r8_ram(uint addr, void *ctx)
{
  return ram_data[addr];
}

static uint mem_r16_ram(uint addr, void *ctx)
{
  return (ram_data[addr] << 8) | ram_data[addr+1];
}

static uint mem_r32_ram(uint addr, void *ctx)
{
  return (ram_data[addr] << 24) | (ram_data[addr+1] << 16) | (ram_data[addr+2] << 8) | (ram_data[addr+3]);
}

static void mem_w8_ram(uint addr, uint val, void *ctx)
{
  ram_data[addr] = val;
}

static void mem_w16_ram(uint addr, uint val, void *ctx)
{
  ram_data[addr] = val >> 8;
  ram_data[addr+1] = val & 0xff;
}

static void mem_w32_ram(uint addr, uint val, void *ctx)
{
  ram_data[addr]   = val >> 24;
  ram_data[addr+1] = (val >> 16) & 0xff;
  ram_data[addr+2] = (val >> 8) & 0xff;
  ram_data[addr+3] = val & 0xff;
}

/* ----- Musashi Interface ----- */

#include "m68kcpu.h"

void print_cpu_state(m68ki_cpu_core *cpu)
{
  int i;
  volatile int *p = 0;
  unsigned int a7 = cpu->dar[8 + 7];
  
  fprintf(stderr,"CPU crashed - detailed information:\n");
  fprintf(stderr,"PC          : 0x%08x\n",cpu->pc);
  fprintf(stderr,"Previous PC : 0x%08x\n",cpu->ppc);

  fprintf(stderr,"D0-7 : ");
  for(i = 0;i < 8;i++) {
    fprintf(stderr,"0x%08x ",cpu->dar[i]);
  }
  fprintf(stderr,"\nA0-7 : ");
  for(i = 0;i < 8;i++) {
    fprintf(stderr,"0x%08x ",cpu->dar[i + 8]);
  }
  fprintf(stderr,"\n Stack:");
  for(i = -32;i <= 32;i += 4) {
    unsigned int adr = a7 + i;
    uint page        = adr >> 16;
    if (page < NUM_PAGES) {
      unsigned int val = m68k_read_memory_32(adr);
      fprintf(stderr,"0x%08x ",val);
    }
    if ((i & 0x10) == 0x0c)
      fprintf(stderr,"\n");
  }
  fprintf(stderr,"\n");
#if 0  
  *p++;
#endif
}
			    
void crash_me(void)
{
  print_cpu_state(&m68ki_cpu);
}

unsigned int  m68k_read_memory_8(unsigned int address)
{
  uint page = address >> 16;
  if (page < NUM_PAGES) {
    uint val = r_func[page][0](address, r_ctx[page][0]);
    if(mem_trace) {
      if(trace_func('R',0,address,val,trace_ctx)) {
	mem_set_all_to_end();
      }
    }
    return val;
  } else {
    uint val = 0x00; /* CPU goes bezerk */
    crash_me();
    if(trace_func('R',0,address,val,trace_ctx)) {
      mem_set_all_to_end();
    }
    return val;
  }
}

unsigned int  m68k_read_memory_16(unsigned int address)
{
  uint page = address >> 16;
  if (page < NUM_PAGES) {
    uint val = r_func[page][1](address, r_ctx[page][1]);
    if(mem_trace) {
      if(trace_func('R',1,address,val,trace_ctx)) {
      mem_set_all_to_end();
      }
    }
    return val;
  } else {
    uint val = 0x4e70; /* CPU goes bezerk */
    crash_me();
    if(trace_func('R',1,address,val,trace_ctx)) {
      mem_set_all_to_end();
    }
    return val;
  }
}

unsigned int  m68k_read_memory_32(unsigned int address)
{
  uint page = address >> 16;
  if (page < NUM_PAGES) {
    uint val = r_func[page][2](address, r_ctx[page][2]);
    if(mem_trace) {
      if(trace_func('R',2,address,val,trace_ctx)) {
	mem_set_all_to_end();
      }
    }
    return val;
  } else {
    uint val = 0x0; /* CPU goes bezerk */
    crash_me();
    if(trace_func('R',2,address,val,trace_ctx)) {
      mem_set_all_to_end();
    }
    return val;
  }
}

void m68k_write_memory_8(unsigned int address, unsigned int value)
{
  uint page = address >> 16;
  if (page < NUM_PAGES) {
    w_func[page][0](address, value, w_ctx[page][0]);
    if(mem_trace) {
      if(trace_func('W',0,address,value,trace_ctx)) {
	mem_set_all_to_end();
      }
    }
  } else {
    crash_me();
    if(trace_func('W',0,address,value,trace_ctx)) {
      mem_set_all_to_end();
    }
  }
}

void m68k_write_memory_16(unsigned int address, unsigned int value)
{
  uint page = address >> 16;
  if (page < NUM_PAGES) {
    w_func[page][1](address, value, w_ctx[page][1]);
    if(mem_trace) {
      if(trace_func('W',1,address,value,trace_ctx)) {
	mem_set_all_to_end();
      }
    }
  } else {
    crash_me();
    if(trace_func('W',1,address,value,trace_ctx)) {
      mem_set_all_to_end();
    }
  }
}

void m68k_write_memory_32(unsigned int address, unsigned int value)
{
  uint page = address >> 16;
  if (page < NUM_PAGES) {
    w_func[page][2](address, value, w_ctx[page][2]);
    if(mem_trace) {
      if(trace_func('W',2,address,value,trace_ctx)) {
	mem_set_all_to_end();
      }
    }
  } else {
    crash_me();
    if(trace_func('W',2,address,value,trace_ctx)) {
      mem_set_all_to_end();
    }
  }
}

/* Disassemble support */

unsigned int m68k_read_disassembler_16 (unsigned int address)
{
  uint page = address >> 16;
  
  if (page < NUM_PAGES) {
    uint val = r_func[page][1](address, r_ctx[page][1]);
    return val;
  } else {
    return 0x4afc; /* illegal */
  }
}

unsigned int m68k_read_disassembler_32 (unsigned int address)
{
  uint page = address >> 16;
  if (page < NUM_PAGES) {
    uint val = r_func[page][2](address, r_ctx[page][1]);
    return val;
  } else {
    return 0x0;
  }
}

/* ----- API ----- */

int mem_init(uint ram_size_kib)
{
  int i;
  ram_size = ram_size_kib * 1024;
  ram_pages = ram_size_kib / 64;
  ram_data = (uint8_t *)malloc(ram_size);

  for(i=0;i<NUM_PAGES;i++) {
    if(i < ram_pages) {
      r_func[i][0] = mem_r8_ram;
      r_func[i][1] = mem_r16_ram;
      r_func[i][2] = mem_r32_ram;
      w_func[i][0] = mem_w8_ram;
      w_func[i][1] = mem_w16_ram;
      w_func[i][2] = mem_w32_ram;
    } else {
      r_func[i][0] = r8_fail;
      r_func[i][1] = r16_fail;
      r_func[i][2] = r32_fail;
      w_func[i][0] = w8_fail;
      w_func[i][1] = w16_fail;
      w_func[i][2] = w32_fail;
    }
  }

  trace_func = default_trace;
  invalid_func = default_invalid;

  return (ram_data != NULL);
}

void mem_free(void)
{
  free(ram_data);
  ram_data = NULL;
}

void mem_set_invalid_func(invalid_func_t func, void *ctx)
{
  invalid_func = func;
  invalid_ctx = ctx;
}

void mem_set_trace_mode(int on)
{
  mem_trace = on;
}

void mem_set_trace_func(trace_func_t func, void *ctx)
{
  trace_func = func;
  trace_ctx = ctx;
}

int mem_is_end(void)
{
  return is_end;
}

uint mem_reserve_special_range(uint num_pages)
{
  uint begin_page = special_page - num_pages;
  if(begin_page < ram_pages) {
    return 0;
  }
  special_page = begin_page;
  return begin_page << 16;
}

void mem_set_special_range_read_func(uint page_addr, uint width, read_func_t func, void *ctx)
{
  uint page = page_addr >> 16;
  r_func[page][width] = func;
  r_ctx[page][width] = ctx;
}

void mem_set_special_range_write_func(uint page_addr, uint width, write_func_t func, void *ctx)
{
  uint page = page_addr >> 16;
  w_func[page][width] = func;
  w_ctx[page][width] = ctx;
}
