from amitools.vamos.astructs import (
    AmigaStruct,
    AmigaStructDef,
    TypeDumper,
    BYTE,
    UBYTE,
    WORD,
    UWORD,
    LONG,
    ULONG,
    APTR,
    APTR_SELF,
    APTR_VOID,
    BPTR_VOID,
    CStringType,
    BStringType,
    CSTR,
    BSTR,
    ARRAY,
    BitField,
    BitFieldType,
    Enum,
    EnumType,
)
from amitools.vamos.machine.mock import MockMemory


@AmigaStructDef
class MyStruct(AmigaStruct):
    _format = [
        (WORD, "ms_Word"),
        (UWORD, "ms_Pad"),
        (BPTR_VOID, "ms_SegList"),
        (LONG, "ms_StackSize"),
    ]


@AmigaStructDef
class SubStruct(AmigaStruct):
    _format = [
        (MyStruct, "ss_My"),
        (APTR(MyStruct), "ss_MyPtr"),
        (APTR_SELF, "ss_SubPtr"),
    ]


@BitFieldType
class MyBitField(BitField, ULONG):
    foo = 1
    bar = 2
    baz = 4


@EnumType
class MyEnum(Enum, ULONG):
    a = 3
    b = 4
    c = 0xFFFFFFFF


@AmigaStructDef
class SpecialStruct(AmigaStruct):
    _format = [
        (MyBitField, "ss_MyBitField"),
        (MyEnum, "ss_MyEnum"),
    ]


@AmigaStructDef
class ArrayStruct(AmigaStruct):
    _format = [
        (ARRAY(UBYTE, 8), "as_ByteArray"),
        (ARRAY(MyBitField, 4), "as_BitArray"),
        (ARRAY(MyEnum, 2), "as_EnumArray"),
        (ARRAY(MyStruct, 3), "as_StructArray"),
    ]


def dump_type(type, **kw_args):
    result = []

    def print_func(txt):
        result.append(txt)

    dumper = TypeDumper(print_func=print_func)
    dumper.dump(type, **kw_args)
    return result


def dump_fields(*fields, **kw_args):
    result = []

    def print_func(txt):
        result.append(txt)

    dumper = TypeDumper(print_func=print_func)
    dumper.dump_fields(*fields, **kw_args)
    return result


def dump_obj(obj):
    result = []

    def print_func(txt):
        result.append(txt)

    dumper = TypeDumper(print_func=print_func)
    dumper.dump_obj(obj)
    return result


def calc_sizes(type):
    dumper = TypeDumper()
    return dumper.calc_sizes(type)


# ---- size calc ----


def astructs_dump_size_simple_test():
    res = calc_sizes(ULONG)
    assert res.type_size == len("ULONG") and res.field_size == 0 and res.max_depth == 0
    res = calc_sizes(APTR_VOID)
    assert res.type_size == len("VOID*") and res.field_size == 0 and res.max_depth == 0


def astructs_dump_size_array_test():
    BA = ARRAY(BYTE, 5)
    res = calc_sizes(BA)
    assert (
        res.type_size == len("  BYTE [0]")
        and res.field_size == 0
        and res.max_depth == 1
    )


def astructs_dump_size_struct_test():
    res = calc_sizes(MyStruct)
    assert (
        res.type_size == len("  VOID#")
        and res.field_size == len("ms_StackSize")
        and res.max_depth == 1
    )
    res = calc_sizes(SubStruct)
    assert (
        res.type_size == len("    VOID#")
        and res.field_size == len("ms_StackSize")
        and res.max_depth == 2
    )


# ----- type dump ----


def astructs_dump_type_simple_test():
    assert dump_type(ULONG) == ["@00000000  ULONG"]
    assert dump_type(APTR_VOID) == ["@00000000  VOID*"]


def astructs_dump_type_array_test():
    BA = ARRAY(BYTE, 5)
    assert dump_type(BA) == [
        "@00000000  BYTE[5] {",
        "@00000000    BYTE [0]",
        "@00000001    BYTE [1]",
        "@00000002    BYTE [2]",
        "@00000003    BYTE [3]",
        "@00000004    BYTE [4]",
        "@00000005  }",
    ]
    assert dump_type(BA, show_offsets=True) == [
        "@00000000         BYTE[5] {",
        "@00000000  +0000    BYTE [0]",
        "@00000001  +0001    BYTE [1]",
        "@00000002  +0002    BYTE [2]",
        "@00000003  +0003    BYTE [3]",
        "@00000004  +0004    BYTE [4]",
        "@00000005  =0005  }",
    ]


def astructs_dump_type_struct_simple_test():
    assert dump_type(MyStruct) == [
        "@00000000  My {",
        "@00000000    WORD   ms_Word",
        "@00000002    UWORD  ms_Pad",
        "@00000004    VOID#  ms_SegList",
        "@00000008    LONG   ms_StackSize",
        "@0000000c  }",
    ]
    assert dump_type(MyStruct, show_offsets=True) == [
        "@00000000         My {",
        "@00000000  +0000    WORD   ms_Word",
        "@00000002  +0002    UWORD  ms_Pad",
        "@00000004  +0004    VOID#  ms_SegList",
        "@00000008  +0008    LONG   ms_StackSize",
        "@0000000c  =000c  }",
    ]


def astructs_dump_type_struct_sub_test():
    assert dump_type(SubStruct) == [
        "@00000000  Sub {",
        "@00000000    My {     ss_My",
        "@00000000      WORD   ms_Word",
        "@00000002      UWORD  ms_Pad",
        "@00000004      VOID#  ms_SegList",
        "@00000008      LONG   ms_StackSize",
        "@0000000c    }",
        "@00000010    My*      ss_MyPtr",
        "@00000014    Sub*     ss_SubPtr",
        "@00000018  }",
    ]
    assert dump_type(SubStruct, show_offsets=True) == [
        "@00000000                Sub {",
        "@00000000  +0000           My {     ss_My",
        "@00000000  +0000  +0000      WORD   ms_Word",
        "@00000002  +0002  +0002      UWORD  ms_Pad",
        "@00000004  +0004  +0004      VOID#  ms_SegList",
        "@00000008  +0008  +0008      LONG   ms_StackSize",
        "@0000000c  +000c  =000c    }",
        "@00000010  +0010           My*      ss_MyPtr",
        "@00000014  +0014           Sub*     ss_SubPtr",
        "@00000018  =0018         }",
    ]


def astructs_dump_type_struct_special_test():
    assert dump_type(SpecialStruct) == [
        "@00000000  Special {",
        "@00000000    MyBitField  ss_MyBitField",
        "@00000004    MyEnum      ss_MyEnum",
        "@00000008  }",
    ]
    assert dump_type(SpecialStruct, show_offsets=True) == [
        "@00000000         Special {",
        "@00000000  +0000    MyBitField  ss_MyBitField",
        "@00000004  +0004    MyEnum      ss_MyEnum",
        "@00000008  =0008  }",
    ]


def astructs_dump_type_struct_array_test():
    assert dump_type(ArrayStruct) == [
        "@00000000  Array {",
        "@00000000    UBYTE[8] {        as_ByteArray",
        "@00000000      UBYTE [0]",
        "@00000001      UBYTE [1]",
        "@00000002      UBYTE [2]",
        "@00000003      UBYTE [3]",
        "@00000004      UBYTE [4]",
        "@00000005      UBYTE [5]",
        "@00000006      UBYTE [6]",
        "@00000007      UBYTE [7]",
        "@00000008    }",
        "@00000008    MyBitField[4] {   as_BitArray",
        "@00000008      MyBitField [0]",
        "@0000000c      MyBitField [1]",
        "@00000010      MyBitField [2]",
        "@00000014      MyBitField [3]",
        "@00000018    }",
        "@00000018    MyEnum[2] {       as_EnumArray",
        "@00000018      MyEnum [0]",
        "@0000001c      MyEnum [1]",
        "@00000020    }",
        "@00000020    My[3] {           as_StructArray",
        "@00000020      My [0] {",
        "@00000020        WORD          ms_Word",
        "@00000022        UWORD         ms_Pad",
        "@00000024        VOID#         ms_SegList",
        "@00000028        LONG          ms_StackSize",
        "@0000002c      }",
        "@00000030      My [1] {",
        "@00000030        WORD          ms_Word",
        "@00000032        UWORD         ms_Pad",
        "@00000034        VOID#         ms_SegList",
        "@00000038        LONG          ms_StackSize",
        "@0000003c      }",
        "@00000040      My [2] {",
        "@00000040        WORD          ms_Word",
        "@00000042        UWORD         ms_Pad",
        "@00000044        VOID#         ms_SegList",
        "@00000048        LONG          ms_StackSize",
        "@0000004c      }",
        "@00000050    }",
        "@00000050  }",
    ]
    assert dump_type(ArrayStruct, show_offsets=True) == [
        "@00000000                       Array {",
        "@00000000  +0000                  UBYTE[8] {        as_ByteArray",
        "@00000000  +0000  +0000             UBYTE [0]",
        "@00000001  +0001  +0001             UBYTE [1]",
        "@00000002  +0002  +0002             UBYTE [2]",
        "@00000003  +0003  +0003             UBYTE [3]",
        "@00000004  +0004  +0004             UBYTE [4]",
        "@00000005  +0005  +0005             UBYTE [5]",
        "@00000006  +0006  +0006             UBYTE [6]",
        "@00000007  +0007  +0007             UBYTE [7]",
        "@00000008  +0008  =0008           }",
        "@00000008  +0008                  MyBitField[4] {   as_BitArray",
        "@00000008  +0008  +0000             MyBitField [0]",
        "@0000000c  +000c  +0004             MyBitField [1]",
        "@00000010  +0010  +0008             MyBitField [2]",
        "@00000014  +0014  +000c             MyBitField [3]",
        "@00000018  +0018  =0010           }",
        "@00000018  +0018                  MyEnum[2] {       as_EnumArray",
        "@00000018  +0018  +0000             MyEnum [0]",
        "@0000001c  +001c  +0004             MyEnum [1]",
        "@00000020  +0020  =0008           }",
        "@00000020  +0020                  My[3] {           as_StructArray",
        "@00000020  +0020  +0000             My [0] {",
        "@00000020  +0020  +0000  +0000        WORD          ms_Word",
        "@00000022  +0022  +0002  +0002        UWORD         ms_Pad",
        "@00000024  +0024  +0004  +0004        VOID#         ms_SegList",
        "@00000028  +0028  +0008  +0008        LONG          ms_StackSize",
        "@0000002c  +002c  +000c  =000c      }",
        "@00000030  +0030  +0010             My [1] {",
        "@00000030  +0030  +0010  +0000        WORD          ms_Word",
        "@00000032  +0032  +0012  +0002        UWORD         ms_Pad",
        "@00000034  +0034  +0014  +0004        VOID#         ms_SegList",
        "@00000038  +0038  +0018  +0008        LONG          ms_StackSize",
        "@0000003c  +003c  +001c  =000c      }",
        "@00000040  +0040  +0020             My [2] {",
        "@00000040  +0040  +0020  +0000        WORD          ms_Word",
        "@00000042  +0042  +0022  +0002        UWORD         ms_Pad",
        "@00000044  +0044  +0024  +0004        VOID#         ms_SegList",
        "@00000048  +0048  +0028  +0008        LONG          ms_StackSize",
        "@0000004c  +004c  +002c  =000c      }",
        "@00000050  +0050  =0030           }",
        "@00000050  =0050                }",
    ]


def astructs_dump_type_fields_test():
    assert dump_fields(SubStruct.sdef.ss_My, MyStruct.sdef.ms_Pad) == [
        "@00000000  Sub {",
        "@00000000    My {     ss_My",
        "@00000002      UWORD  ms_Pad",
        "@0000000c    }",
        "@00000018  }",
    ]
    assert dump_fields(
        SubStruct.sdef.ss_My, MyStruct.sdef.ms_Pad, show_offsets=True
    ) == [
        "@00000000                Sub {",
        "@00000000  +0000           My {     ss_My",
        "@00000002  +0002  +0002      UWORD  ms_Pad",
        "@0000000c  +000c  =000c    }",
        "@00000018  =0018         }",
    ]


# ----- obj dump -----


def astructs_dump_obj_scalar_test():
    mem = MockMemory()
    # byte
    byte = BYTE(mem=mem, addr=1)
    byte.val = -12
    assert dump_obj(byte) == [
        "     @00000001         BYTE                  -12/f4",
    ]
    # ubyte
    ubyte = UBYTE(mem=mem, addr=2)
    ubyte.val = 0xFE
    assert dump_obj(ubyte) == [
        "     @00000002         UBYTE                 254/fe",
    ]
    # word
    word = WORD(mem=mem, addr=4)
    word.val = -1
    assert dump_obj(word) == [
        "     @00000004         WORD                  -1/ffff",
    ]
    # uword
    uword = UWORD(mem=mem, addr=6)
    uword.val = 0xDEAD
    assert dump_obj(uword) == [
        "     @00000006         UWORD                 57005/dead",
    ]
    # long
    long = LONG(mem=mem, addr=8)
    long.val = -1
    assert dump_obj(long) == [
        "     @00000008         LONG                  -1/ffffffff",
    ]
    # ulong
    ulong = ULONG(mem=mem, addr=0xC)
    ulong.val = 0x1234
    assert dump_obj(ulong) == [
        "     @0000000c         ULONG                 4660/00001234",
    ]


def astructs_dump_obj_pointer_test():
    mem = MockMemory()

    # aptr
    aptr_void = APTR_VOID(mem=mem, addr=0x10)
    aptr_void.aptr = 0xBABE
    assert dump_obj(aptr_void) == [
        "     @00000010         APTR_VOID             @(0000babe):VOID",
    ]
    aptr_null = APTR_VOID(mem=mem, addr=0x14)
    assert dump_obj(aptr_null) == [
        "     @00000014         APTR_VOID             @NULL",
    ]
    # bptr
    bptr_void = BPTR_VOID(mem=mem, addr=0x18)
    bptr_void.bptr = 4
    assert dump_obj(bptr_void) == [
        "     @00000018         BPTR_VOID             #(00000004/00000010):VOID",
    ]
    bptr_zero = BPTR_VOID(mem=mem, addr=0x1C)
    assert dump_obj(bptr_zero) == [
        "     @0000001c         BPTR_VOID             #ZERO",
    ]


def astructs_dump_obj_string_test():
    mem = MockMemory()

    # cstring
    cst = CStringType(mem=mem, addr=0x10)
    cst.set("hello, world!")
    assert dump_obj(cst) == [
        "     @00000010         CStringType           'hello, world!'(13)",
    ]
    cst_null = CStringType(mem=mem, addr=0x20)
    assert dump_obj(cst_null) == [
        "     @00000020         CStringType           NONE",
    ]
    # bstring
    bst = BStringType(mem=mem, addr=0x30)
    bst.set("hello, world!")
    assert dump_obj(bst) == [
        "     @00000030         BStringType           #'hello, world!'(13)",
    ]
    bst_zero = BStringType(mem=mem, addr=0x40)
    assert dump_obj(bst_zero) == [
        "     @00000040         BStringType           #NONE",
    ]
    # cstr
    cstr = CSTR(mem=mem, addr=0x50)
    cstr.aptr = 0x10
    assert dump_obj(cstr) == [
        "     @00000050         CSTR                  @(00000010):'hello, world!'(13)",
    ]
    cstr_null = CSTR(mem=mem, addr=0x54)
    assert dump_obj(cstr_null) == [
        "     @00000054         CSTR                  @NULL",
    ]
    # bstr
    bstr = BSTR(mem=mem, addr=0x58)
    bstr.aptr = 0x30
    assert dump_obj(bstr) == [
        "     @00000058         BSTR                  #(0000000c/00000030):#'hello, world!'(13)",
    ]
    bstr_zero = BSTR(mem=mem, addr=0x5C)
    assert dump_obj(bstr_zero) == [
        "     @0000005c         BSTR                  #ZERO",
    ]


def astructs_dump_obj_enum_test():
    mem = MockMemory()

    enum = MyEnum(mem=mem, addr=4)
    assert dump_obj(enum) == [
        "     @00000004         MyEnum                INVALID(0/0)",
    ]
    enum2 = MyEnum(mem=mem, addr=8)
    enum2.set(MyEnum.a)
    assert dump_obj(enum2) == [
        "     @00000008         MyEnum                a(3/3)",
    ]


def astructs_dump_obj_bitfield_test():
    mem = MockMemory()

    bf = MyBitField(mem=mem, addr=4)
    assert dump_obj(bf) == ["     @00000004         MyBitField             (0/b0)"]


def astructs_dump_obj_array_test():
    mem = MockMemory()

    BA = ARRAY(BYTE, 5)
    aba = BA(mem=mem, addr=4)
    for i in range(5):
        aba[i].val = 1 + i
    assert dump_obj(aba) == [
        "     @00000004        ARRAY[5]_BYTE  [",
        "     @00000004 [0]    BYTE                  1/01",
        "     @00000005 [1]    BYTE                  2/02",
        "     @00000006 [2]    BYTE                  3/03",
        "     @00000007 [3]    BYTE                  4/04",
        "     @00000008 [4]    BYTE                  5/05",
        "     @00000009 =0005  ]",
    ]


def astructs_dump_obj_struct_test():
    mem = MockMemory()

    ms = MyStruct(mem=mem, addr=0x10)
    assert dump_obj(ms) == [
        "     @00000010         My {",
        "     @00000010 +0000   .ms_Word (WORD)                          0/0000",
        "     @00000012 +0002   .ms_Pad (UWORD)                          0/0000",
        "     @00000014 +0004   .ms_SegList (VOID#)                      #ZERO",
        "     @00000018 +0008   .ms_StackSize (LONG)                     0/00000000",
        "     @0000001c =0012   }",
    ]
    ss = SubStruct(mem=mem, addr=0x100)
    assert dump_obj(ss) == []
