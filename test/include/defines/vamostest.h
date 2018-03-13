/* Automatically generated header! Do not edit! */

#ifndef _INLINE_VAMOSTEST_H
#define _INLINE_VAMOSTEST_H

#ifndef AROS_LIBCALL_H
#include <aros/libcall.h>
#endif /* !AROS_LIBCALL_H */

#ifndef VAMOSTEST_BASE_NAME
#define VAMOSTEST_BASE_NAME VamosTestBase
#endif /* !VAMOSTEST_BASE_NAME */

#define Add(___a, ___b) \
	AROS_LC2(ULONG, Add, \
	AROS_LCA(ULONG, (___a), D0), \
	AROS_LCA(ULONG, (___b), D1), \
	struct Library *, VAMOSTEST_BASE_NAME, 7, /* s */)

#define Dummy(___a, ___b) \
	AROS_LC2(ULONG, Dummy, \
	AROS_LCA(ULONG, (___a), D0), \
	AROS_LCA(ULONG, (___b), D1), \
	struct Library *, VAMOSTEST_BASE_NAME, 9, /* s */)

#define PrintHello() \
	AROS_LC0(void, PrintHello, \
	struct Library *, VAMOSTEST_BASE_NAME, 5, /* s */)

#define PrintString(___str) \
	AROS_LC1(void, PrintString, \
	AROS_LCA(STRPTR, (___str), A0), \
	struct Library *, VAMOSTEST_BASE_NAME, 6, /* s */)

#define RaiseError(___str) \
	AROS_LC1(void, RaiseError, \
	AROS_LCA(STRPTR, (___str), A0), \
	struct Library *, VAMOSTEST_BASE_NAME, 10, /* s */)

#define Swap(___a, ___b) \
	AROS_LC2(ULONG, Swap, \
	AROS_LCA(ULONG, (___a), D0), \
	AROS_LCA(ULONG, (___b), D1), \
	struct Library *, VAMOSTEST_BASE_NAME, 8, /* s */)

#endif /* !_INLINE_VAMOSTEST_H */
