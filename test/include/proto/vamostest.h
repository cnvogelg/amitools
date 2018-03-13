#ifndef _PROTO_VAMOSTEST_H
#define _PROTO_VAMOSTEST_H

#ifndef EXEC_TYPES_H
#include <exec/types.h>
#endif
#if !defined(CLIB_VAMOSTEST_PROTOS_H) && !defined(__GNUC__)
#include <clib/vamostest_protos.h>
#endif

#ifndef __NOLIBBASE__
extern struct VamosTestBase *VamosTestBase;
#endif

#ifdef __GNUC__
#ifdef __AROS__
#include <defines/vamostest.h>
#else
#include <inline/vamostest.h>
#endif
#elif defined(__VBCC__)
#include <inline/vamostest_protos.h>
#else
#include <pragma/vamostest_lib.h>
#endif

#endif	/*  _PROTO_VAMOSTEST_H  */
