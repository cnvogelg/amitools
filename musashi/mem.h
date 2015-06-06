/* MusashiCPU <-> vamos memory interface
 *
 * written by Christian Vogelgsang <chris@vogelgsang.org>
 * under the GNU Public License V2
 */

#ifndef _MEM_H
#define _MEM_H

#include "m68k.h"
#include <stdint.h>

/* ------ Types ----- */
#ifndef UINT_TYPE
#define UINT_TYPE
typedef unsigned int uint;
#endif

typedef uint (*read_func_t)(uint addr, void *ctx);
typedef void (*write_func_t)(uint addr, uint value, void *ctx);

typedef void (*invalid_func_t)(int mode, int width, uint addr, void *ctx);
typedef int (*trace_func_t)(int mode, int width, uint addr, uint val, void *ctx);

/* ----- API ----- */
extern int  mem_init(uint ram_size_kib);
extern void mem_free(void);

extern void mem_set_invalid_func(invalid_func_t func, void *ctx);
extern void mem_set_all_to_end(void);
extern int  mem_is_end(void);

extern void mem_set_trace_mode(int on);
extern void mem_set_trace_func(trace_func_t func, void *ctx);

extern uint mem_reserve_special_range(uint num_pages);
extern void mem_set_special_range_read_func(uint page_addr, uint width, read_func_t func, void *ctx);
extern void mem_set_special_range_write_func(uint page_addr, uint width, write_func_t func, void *ctx);

extern uint8_t *mem_raw_ptr(void);
extern uint mem_raw_size(void);

extern unsigned int m68k_read_memory_8(unsigned int address);
extern unsigned int m68k_read_memory_16(unsigned int address);
extern unsigned int m68k_read_memory_32(unsigned int address);

extern void m68k_write_memory_8(unsigned int address, unsigned int value);
extern void m68k_write_memory_16(unsigned int address, unsigned int value);
extern void m68k_write_memory_32(unsigned int address, unsigned int value);

#endif
