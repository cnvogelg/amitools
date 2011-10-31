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
typedef unsigned int uint;

typedef uint (*read_func_t)(uint addr);
typedef void (*write_func_t)(uint addr, uint value);

typedef void (*invalid_func_t)(int mode, int width, uint addr);
typedef void (*trace_func_t)(int mode, int width, uint addr, uint val);

/* ----- API ----- */
extern int  mem_init(uint ram_size_kib);
extern void mem_free(void);

extern void mem_set_invalid_func(invalid_func_t func);
extern int  mem_is_end(void);

extern void mem_set_trace_mode(int on);
extern void mem_set_trace_func(trace_func_t func);

extern uint mem_reserve_special_range(uint num_pages);
extern void mem_set_special_range_read_func(uint page_addr, uint width, read_func_t func);
extern void mem_set_special_range_write_func(uint page_addr, uint width, write_func_t func);

extern uint mem_ram_read(int mode, uint addr);
extern void mem_ran_write(int mode, uint addr, uint value);
extern void mem_ram_read_block(uint addr, uint size, char *data);
extern void mem_ram_write_block(uint addr, uint size, const char *data);

#endif
