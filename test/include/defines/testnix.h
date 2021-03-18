/* Automatically generated header (sfdc 1.11)! Do not edit! */

#ifndef _INLINE_TESTNIX_H
#define _INLINE_TESTNIX_H

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

#ifndef TESTNIX_BASE_NAME
#define TESTNIX_BASE_NAME TestNixBase
#endif /* !TESTNIX_BASE_NAME */

#define Add(___a, ___b) \
      AROS_LC2(ULONG, Add, \
 AROS_LCA(ULONG, (___a), D0), \
 AROS_LCA(ULONG, (___b), D1), \
     struct Library *, TESTNIX_BASE_NAME, 5, Testnix)

#endif /* !_INLINE_TESTNIX_H */
