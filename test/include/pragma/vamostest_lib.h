#ifndef _INCLUDE_PRAGMA_VAMOSTEST_LIB_H
#define _INCLUDE_PRAGMA_VAMOSTEST_LIB_H

#ifndef CLIB_VAMOSTEST_PROTOS_H
#include <clib/vamostest_protos.h>
#endif

#if defined(AZTEC_C) || defined(__MAXON__) || defined(__STORM__)
#pragma amicall(VamosTestBase,0x01e,PrintHello())
#pragma amicall(VamosTestBase,0x024,PrintString(a0))
#pragma amicall(VamosTestBase,0x02a,Add(d0,d1))
#pragma amicall(VamosTestBase,0x030,Swap(d0,d1))
#pragma amicall(VamosTestBase,0x036,Dummy(d0,d1))
#pragma amicall(VamosTestBase,0x03c,RaiseError(a0))
#pragma amicall(VamosTestBase,0x042,ExecutePy(d0,a0))
#endif
#if defined(_DCC) || defined(__SASC)
#pragma  libcall VamosTestBase PrintHello             01e 00
#pragma  libcall VamosTestBase PrintString            024 801
#pragma  libcall VamosTestBase Add                    02a 1002
#pragma  libcall VamosTestBase Swap                   030 1002
#pragma  libcall VamosTestBase Dummy                  036 1002
#pragma  libcall VamosTestBase RaiseError             03c 801
#pragma  libcall VamosTestBase ExecutePy              042 8002
#endif

#endif	/*  _INCLUDE_PRAGMA_VAMOSTEST_LIB_H  */
