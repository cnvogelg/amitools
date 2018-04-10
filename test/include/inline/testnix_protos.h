#ifndef _VBCCINLINE_TESTNIX_H
#define _VBCCINLINE_TESTNIX_H

#ifndef EXEC_TYPES_H
#include <exec/types.h>
#endif

ULONG __Add(__reg("a6") struct Library *, __reg("d0") ULONG a, __reg("d1") ULONG b)="\tjsr\t-30(a6)";
#define Add(a, b) __Add(TestNixBase, (a), (b))

#endif /*  _VBCCINLINE_TESTNIX_H  */
