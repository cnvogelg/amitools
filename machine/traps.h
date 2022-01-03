/* a dispatcher for a-line opcodes to be used as traps in vamos
 *
 * written by Christian Vogelgsang <chris@vogelgsang.org>
 * under the GNU Public License V2
 */

#ifndef _TRAPS_H
#define _TRAPS_H

#include "m68k.h"
#include <stdint.h>

#define TRAP_DEFAULT    0
#define TRAP_ONE_SHOT   1
#define TRAP_AUTO_RTS   2

/* ------ Types ----- */
#ifndef UINT_TYPE
#define UINT_TYPE
typedef unsigned int uint;
#endif

typedef void (*trap_func_t)(uint opcode, uint pc, void *data);

/* ----- API ----- */
extern void trap_init(void);
extern int trap_aline(uint opcode, uint pc);

extern int  trap_setup(trap_func_t func, int flags, void *data);
extern void trap_free(int id);

#endif
