/* Automatically generated header! Do not edit! */

#ifndef _INLINE_TESTNIX_H
#define _INLINE_TESTNIX_H

#ifndef AROS_LIBCALL_H
#include <aros/libcall.h>
#endif /* !AROS_LIBCALL_H */

#ifndef TESTNIX_BASE_NAME
#define TESTNIX_BASE_NAME TestNixBase
#endif /* !TESTNIX_BASE_NAME */

#define Add(___a, ___b) \
	AROS_LC2(ULONG, Add, \
	AROS_LCA(ULONG, (___a), D0), \
	AROS_LCA(ULONG, (___b), D1), \
	struct Library *, TESTNIX_BASE_NAME, 5, /* s */)

#endif /* !_INLINE_TESTNIX_H */
