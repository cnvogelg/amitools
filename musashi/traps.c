/* a dispatcher for a-line opcodes to be used as traps in vamos
 *
 * written by Christian Vogelgsang <chris@vogelgsang.org>
 * under the GNU Public License V2
 */

#include "traps.h"
#include "m68k.h"
#include <string.h>

#define NUM_TRAPS  0x1000
#define TRAP_MASK  0x0fff

union entry {
  trap_func_t trap;
  union entry *next;
};
typedef union entry entry_t; 

static entry_t traps[NUM_TRAPS];
static entry_t *first_free;

static int trap_aline(uint opcode, uint pc)
{
  uint off = opcode & TRAP_MASK;
  trap_func_t f = traps[off].trap;
  f(opcode, pc);
  return 1; /* do not handle illegal opcode anymore */
}

void trap_init(void)
{
  /* setup free list */
  first_free = &traps[0];
  for(int i=0;i<(NUM_TRAPS-1);i++) {
    traps[i].next = &traps[i+1];
  }
  traps[NUM_TRAPS-1].next = NULL;
  
  /* setup my trap handler */
  m68k_set_aline_hook_callback(trap_aline);
}

int trap_setup(trap_func_t func)
{
  /* no more traps available? */
  if(first_free == NULL) {
    return -1;
  }
  
  int off = (int)(first_free - traps);
  
  /* new first free */
  first_free = traps[off].next;
  
  /* store trap function */
  traps[off].trap = func;

  return off;
}

void trap_free(int id)
{
  /* insert trap into free list */
  traps[id].next = first_free;
  first_free = &traps[id];
}
