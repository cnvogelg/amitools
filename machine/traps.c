/* a dispatcher for a-line opcodes to be used as traps in vamos
 *
 * written by Christian Vogelgsang <chris@vogelgsang.org>
 * under the GNU Public License V2
 */

#include "traps.h"
#include "m68k.h"
#include <string.h>
#include <stdio.h>

#define NUM_TRAPS  0x1000
#define TRAP_MASK  0x0fff



struct entry {
  trap_func_t trap;
  struct entry *next;
  void *data;
  int flags;
};
typedef struct entry entry_t;

static entry_t traps[NUM_TRAPS];
static entry_t *first_free;

int trap_aline(uint opcode, uint pc)
{
  uint off = opcode & TRAP_MASK;
  trap_func_t func = traps[off].trap;
  void *data = traps[off].data;
  int flags = traps[off].flags;

  /* unbound trap? */
  if(func == NULL) {
    /* regular m68k ALINE exception */
    return M68K_ALINE_EXCEPT;
  }

  /* a one shot trap is removed before it is triggered
  ** otherwise, trap-functions used to capture "end-of-call"s
  ** of shell processes would never be released.
  */
  if(flags & TRAP_ONE_SHOT) {
    trap_free(off);
  }

  func(opcode, pc, data);

  if(flags & TRAP_AUTO_RTS) {
    return M68K_ALINE_RTS;
  } else {
    return M68K_ALINE_NONE;
  }
}

void trap_init(void)
{
  int i;

  /* setup free list */
  first_free = &traps[0];
  for(i=0;i<(NUM_TRAPS-1);i++) {
    traps[i].trap = NULL;
    traps[i].next = &traps[i+1];
    traps[i].flags = 0;
    traps[i].data = NULL;
  }
  traps[NUM_TRAPS-1].trap = NULL;
  traps[NUM_TRAPS-1].next = NULL;
  traps[NUM_TRAPS-1].flags = 0;
  traps[NUM_TRAPS-1].data = NULL;

  /* setup my trap handler */
  m68k_set_aline_hook_callback(trap_aline);
}

int trap_setup(trap_func_t func, int flags, void *data)
{
  int off;

  /* no more traps available? */
  if(first_free == NULL) {
    return -1;
  }

  off = (int)(first_free - traps);

  /* new first free */
  first_free = traps[off].next;

  /* store trap function */
  traps[off].trap = func;
  traps[off].data = data;
  traps[off].flags = flags;

  return off;
}

void trap_free(int id)
{
  /* insert trap into free list */
  traps[id].next = first_free;
  traps[id].trap = NULL;
  traps[id].flags = 0;
  traps[id].data = NULL;
  first_free = &traps[id];
}
