#ifndef _INLINE_TESTNIX_H
#define _INLINE_TESTNIX_H

#ifndef CLIB_TESTNIX_PROTOS_H
#define CLIB_TESTNIX_PROTOS_H
#endif

#ifndef  EXEC_TYPES_H
#include <exec/types.h>
#endif

#ifndef TESTNIX_BASE_NAME
#define TESTNIX_BASE_NAME TestNixBase
#endif

#define Add(a, b) ({ \
  ULONG _Add_a = (a); \
  ULONG _Add_b = (b); \
  ({ \
  register char * _Add__bn __asm("a6") = (char *) (TESTNIX_BASE_NAME);\
  ((ULONG (*)(char * __asm("a6"), ULONG __asm("d0"), ULONG __asm("d1"))) \
  (_Add__bn - 30))(_Add__bn, _Add_a, _Add_b); \
});})

#endif /*  _INLINE_TESTNIX_H  */
