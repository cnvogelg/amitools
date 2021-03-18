/* Automatically generated header (sfdc 1.11)! Do not edit! */

#ifndef _INLINE_VAMOSTEST_H
#define _INLINE_VAMOSTEST_H

#ifndef _SFDC_VARARG_DEFINED
#define _SFDC_VARARG_DEFINED
#ifdef __HAVE_IPTR_ATTR__
typedef APTR _sfdc_vararg __attribute__((iptr));
#else
typedef ULONG _sfdc_vararg;
#endif /* __HAVE_IPTR_ATTR__ */
#endif /* _SFDC_VARARG_DEFINED */

#ifndef AROS_LIBCALL_H
#include <aros/libcall.h>
#endif /* !AROS_LIBCALL_H */

#ifndef VAMOSTEST_BASE_NAME
#define VAMOSTEST_BASE_NAME VamosTestBase
#endif /* !VAMOSTEST_BASE_NAME */

#define PrintHello() \
      AROS_LC0(VOID, PrintHello, \
     struct VamosTestBase *, VAMOSTEST_BASE_NAME, 5, Vamostest)

#define PrintString(___str) \
      AROS_LC1(VOID, PrintString, \
 AROS_LCA(STRPTR, (___str), A0), \
     struct VamosTestBase *, VAMOSTEST_BASE_NAME, 6, Vamostest)

#define Add(___a, ___b) \
      AROS_LC2(ULONG, Add, \
 AROS_LCA(ULONG, (___a), D0), \
 AROS_LCA(ULONG, (___b), D1), \
     struct VamosTestBase *, VAMOSTEST_BASE_NAME, 7, Vamostest)

#define Swap(___a, ___b) \
      AROS_LC2(ULONG, Swap, \
 AROS_LCA(ULONG, (___a), D0), \
 AROS_LCA(ULONG, (___b), D1), \
     struct VamosTestBase *, VAMOSTEST_BASE_NAME, 8, Vamostest)

#define Dummy(___a, ___b) \
      AROS_LC2(ULONG, Dummy, \
 AROS_LCA(ULONG, (___a), D0), \
 AROS_LCA(ULONG, (___b), D1), \
     struct VamosTestBase *, VAMOSTEST_BASE_NAME, 9, Vamostest)

#define RaiseError(___str) \
      AROS_LC1(VOID, RaiseError, \
 AROS_LCA(STRPTR, (___str), A0), \
     struct VamosTestBase *, VAMOSTEST_BASE_NAME, 10, Vamostest)

#define ExecutePy(___argc, ___argv) \
      AROS_LC2(ULONG, ExecutePy, \
 AROS_LCA(ULONG, (___argc), D0), \
 AROS_LCA(STRPTR *, (___argv), A0), \
     struct VamosTestBase *, VAMOSTEST_BASE_NAME, 11, Vamostest)

#endif /* !_INLINE_VAMOSTEST_H */
