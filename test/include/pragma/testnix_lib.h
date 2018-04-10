#ifndef _INCLUDE_PRAGMA_TESTNIX_LIB_H
#define _INCLUDE_PRAGMA_TESTNIX_LIB_H

#ifndef CLIB_TESTNIX_PROTOS_H
#include <clib/testnix_protos.h>
#endif

#if defined(AZTEC_C) || defined(__MAXON__) || defined(__STORM__)
#pragma amicall(TestNixBase,0x01e,Add(d0,d1))
#endif
#if defined(_DCC) || defined(__SASC)
#pragma  libcall TestNixBase Add                    01e 1002
#endif

#endif	/*  _INCLUDE_PRAGMA_TESTNIX_LIB_H  */
