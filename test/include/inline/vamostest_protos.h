#ifndef _VBCCINLINE_VAMOSTEST_H
#define _VBCCINLINE_VAMOSTEST_H

#ifndef EXEC_TYPES_H
#include <exec/types.h>
#endif

VOID __PrintHello(__reg("a6") struct VamosTestBase *)="\tjsr\t-30(a6)";
#define PrintHello() __PrintHello(VamosTestBase)

VOID __PrintString(__reg("a6") struct VamosTestBase *, __reg("a0") STRPTR str)="\tjsr\t-36(a6)";
#define PrintString(str) __PrintString(VamosTestBase, (str))

ULONG __Add(__reg("a6") struct VamosTestBase *, __reg("d0") ULONG a, __reg("d1") ULONG b)="\tjsr\t-42(a6)";
#define Add(a, b) __Add(VamosTestBase, (a), (b))

ULONG __Swap(__reg("a6") struct VamosTestBase *, __reg("d0") ULONG a, __reg("d1") ULONG b)="\tjsr\t-48(a6)";
#define Swap(a, b) __Swap(VamosTestBase, (a), (b))

ULONG __Dummy(__reg("a6") struct VamosTestBase *, __reg("d0") ULONG a, __reg("d1") ULONG b)="\tjsr\t-54(a6)";
#define Dummy(a, b) __Dummy(VamosTestBase, (a), (b))

VOID __RaiseError(__reg("a6") struct VamosTestBase *, __reg("a0") STRPTR str)="\tjsr\t-60(a6)";
#define RaiseError(str) __RaiseError(VamosTestBase, (str))

ULONG __ExecutePy(__reg("a6") struct VamosTestBase *, __reg("d0") ULONG argc, __reg("a0") STRPTR * argv)="\tjsr\t-66(a6)";
#define ExecutePy(argc, argv) __ExecutePy(VamosTestBase, (argc), (argv))

ULONG __MyFindTagData(__reg("a6") struct VamosTestBase *, __reg("d0") ULONG tagVal, __reg("a0") CONST struct TagItem * tagList)="\tjsr\t-72(a6)";
#define MyFindTagData(tagVal, tagList) __MyFindTagData(VamosTestBase, (tagVal), (tagList))

#if !defined(NO_INLINE_STDARG) && (__STDC__ == 1L) && (__STDC_VERSION__ >= 199901L)
ULONG __MyFindTagDataTags(__reg("a6") struct VamosTestBase *, __reg("d0") ULONG tagVal, ULONG tagList, ...)="\tmove.l\ta0,-(a7)\n\tlea\t4(a7),a0\n\tjsr\t-72(a6)\n\tmovea.l\t(a7)+,a0";
#define MyFindTagDataTags(tagVal, ...) __MyFindTagDataTags(VamosTestBase, (tagVal), __VA_ARGS__)
#endif

#endif /*  _VBCCINLINE_VAMOSTEST_H  */
