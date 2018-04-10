/* testsc.c - SAS/C style lib creation */
#include <exec/types.h>

__asm __saveds ULONG LIBAdd(register __d0 ULONG a, register __d1 ULONG b)
{
  return a + b;
}
