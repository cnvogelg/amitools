#ifndef _PROTO_TESTNIX_H
#define _PROTO_TESTNIX_H

#ifndef EXEC_TYPES_H
#include <exec/types.h>
#endif
#if !defined(CLIB_TESTNIX_PROTOS_H) && !defined(__GNUC__)
#include <clib/testnix_protos.h>
#endif

#ifndef __NOLIBBASE__
extern struct Library *TestNixBase;
#endif

#ifdef __GNUC__
#ifdef __AROS__
#include <defines/testnix.h>
#else
#include <inline/testnix.h>
#endif
#elif defined(__VBCC__)
#include <inline/testnix_protos.h>
#else
#include <pragma/testnix_lib.h>
#endif

#endif	/*  _PROTO_TESTNIX_H  */
