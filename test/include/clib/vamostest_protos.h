#ifndef  CLIB_VAMOSTEST_PROTOS_H
#define  CLIB_VAMOSTEST_PROTOS_H

#ifdef __cplusplus
extern "C" {
#endif /* __cplusplus */

#ifndef  EXEC_TYPES_H
#include <exec/types.h>
#endif

VOID PrintHello(VOID);
VOID PrintString(STRPTR txt);
ULONG Add(ULONG a, ULONG b);
ULONG Swap(ULONG a, ULONG b);
ULONG Dummy(ULONG a, ULONG b);
VOID RaiseError(STRPTR error);
ULONG ExecutePy(ULONG argc, STRPTR *argv);

#ifdef __cplusplus
}
#endif /* __cplusplus */

#endif   /* CLIB_VAMOSTEST_PROTOS_H */
