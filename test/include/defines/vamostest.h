/* Automatically generated header (sfdc 1.12)! Do not edit! */

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

#define MyFindTagData(___tagVal, ___tagList) \
      AROS_LC2(ULONG, MyFindTagData, \
 AROS_LCA(ULONG, (___tagVal), D0), \
 AROS_LCA(CONST struct TagItem *, (___tagList), A0), \
     struct VamosTestBase *, VAMOSTEST_BASE_NAME, 12, Vamostest)

#ifndef NO_INLINE_STDARG
#define MyFindTagDataTags(___tagVal, ___tagList, ...) \
    ({_sfdc_vararg _tags[] = { ___tagList, __VA_ARGS__ }; MyFindTagData((___tagVal), (CONST struct TagItem *) _tags); })
#endif /* !NO_INLINE_STDARG */

#endif /* !_INLINE_VAMOSTEST_H */
