#ifndef _INLINE_VAMOSTEST_H
#define _INLINE_VAMOSTEST_H

#ifndef CLIB_VAMOSTEST_PROTOS_H
#define CLIB_VAMOSTEST_PROTOS_H
#endif

#ifndef  EXEC_TYPES_H
#include <exec/types.h>
#endif

#ifndef VAMOSTEST_BASE_NAME
#define VAMOSTEST_BASE_NAME VamosTestBase
#endif

#define PrintHello() ({ \
  register char * _PrintHello__bn __asm("a6") = (char *) (VAMOSTEST_BASE_NAME);\
  ((VOID (*)(char * __asm("a6"))) \
  (_PrintHello__bn - 30))(_PrintHello__bn); \
})

#define PrintString(str) ({ \
  STRPTR _PrintString_str = (str); \
  ({ \
  register char * _PrintString__bn __asm("a6") = (char *) (VAMOSTEST_BASE_NAME);\
  ((VOID (*)(char * __asm("a6"), STRPTR __asm("a0"))) \
  (_PrintString__bn - 36))(_PrintString__bn, _PrintString_str); \
});})

#define Add(a, b) ({ \
  ULONG _Add_a = (a); \
  ULONG _Add_b = (b); \
  ({ \
  register char * _Add__bn __asm("a6") = (char *) (VAMOSTEST_BASE_NAME);\
  ((ULONG (*)(char * __asm("a6"), ULONG __asm("d0"), ULONG __asm("d1"))) \
  (_Add__bn - 42))(_Add__bn, _Add_a, _Add_b); \
});})

#define Swap(a, b) ({ \
  ULONG _Swap_a = (a); \
  ULONG _Swap_b = (b); \
  ({ \
  register char * _Swap__bn __asm("a6") = (char *) (VAMOSTEST_BASE_NAME);\
  ((ULONG (*)(char * __asm("a6"), ULONG __asm("d0"), ULONG __asm("d1"))) \
  (_Swap__bn - 48))(_Swap__bn, _Swap_a, _Swap_b); \
});})

#define Dummy(a, b) ({ \
  ULONG _Dummy_a = (a); \
  ULONG _Dummy_b = (b); \
  ({ \
  register char * _Dummy__bn __asm("a6") = (char *) (VAMOSTEST_BASE_NAME);\
  ((ULONG (*)(char * __asm("a6"), ULONG __asm("d0"), ULONG __asm("d1"))) \
  (_Dummy__bn - 54))(_Dummy__bn, _Dummy_a, _Dummy_b); \
});})

#define RaiseError(str) ({ \
  STRPTR _RaiseError_str = (str); \
  ({ \
  register char * _RaiseError__bn __asm("a6") = (char *) (VAMOSTEST_BASE_NAME);\
  ((VOID (*)(char * __asm("a6"), STRPTR __asm("a0"))) \
  (_RaiseError__bn - 60))(_RaiseError__bn, _RaiseError_str); \
});})

#define ExecutePy(argc, argv) ({ \
  ULONG _ExecutePy_argc = (argc); \
  STRPTR * _ExecutePy_argv = (argv); \
  ({ \
  register char * _ExecutePy__bn __asm("a6") = (char *) (VAMOSTEST_BASE_NAME);\
  ((ULONG (*)(char * __asm("a6"), ULONG __asm("d0"), STRPTR * __asm("a0"))) \
  (_ExecutePy__bn - 66))(_ExecutePy__bn, _ExecutePy_argc, _ExecutePy_argv); \
});})

#endif /*  _INLINE_VAMOSTEST_H  */
