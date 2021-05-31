from amitools.vamos.astructs import (
    AmigaStruct,
    AmigaStructDef,
    TypeDumper,
    WORD,
    UWORD,
    BPTR_VOID,
    LONG,
    ULONG,
    APTR,
    APTR_SELF,
    APTR_VOID,
    BitField,
    BitFieldType,
    Enum,
    EnumType,
)


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


def dump_type(type):
    result = []

    def print_func(txt):
        result.append(txt)

    dumper = TypeDumper(print_func=print_func)
    dumper.dump(type)
    return result


def dump_fields(*fields):
    result = []

    def print_func(txt):
        result.append(txt)

    dumper = TypeDumper(print_func=print_func)
    dumper.dump_fields(*fields)
    return result


def astructs_dump_type_simple_test():
    assert dump_type(ULONG) == ["     @0000         ULONG"]
    assert dump_type(APTR_VOID) == ["     @0000         APTR_VOID"]


def astructs_dump_type_struct_test():
    assert dump_type(MyStruct) == [
        "     @0000         My {",
        "#0000 0000 @0000/0000 +0002    WORD                 ms_Word             ",
        "#0001 0001 @0002/0002 +0002    UWORD                ms_Pad              ",
        "#0002 0002 @0004/0004 +0004    VOID#                ms_SegList          ",
        "#0003 0003 @0008/0008 +0004    LONG                 ms_StackSize        ",
        "     @0012 =0012   }",
    ]
    assert dump_type(SubStruct) == [
        "     @0000         Sub {",
        "     @0000          My ss_My {",
        "#0000 0000 @0000/0000 +0002     WORD                 ms_Word             ",
        "#0001 0001 @0002/0002 +0002     UWORD                ms_Pad              ",
        "#0002 0002 @0004/0004 +0004     VOID#                ms_SegList          ",
        "#0003 0003 @0008/0008 +0004     LONG                 ms_StackSize        ",
        "     @0012 =0012    }",
        "#0001 0004 @0012/000c +0004    My*                  ss_MyPtr            ",
        "#0002 0005 @0016/0010 +0004    Sub*                 ss_SubPtr           ",
        "     @0020 =0020   }",
    ]
    assert dump_type(SpecialStruct) == [
        "     @0000         Special {",
        "#0000 0000 @0000/0000 +0004    MyBitField           ss_MyBitField       ",
        "#0001 0001 @0004/0004 +0004    MyEnum               ss_MyEnum           ",
        "     @0008 =0008   }",
    ]


def astructs_dump_fields_test():
    assert dump_fields(SubStruct.sdef.ss_My, MyStruct.sdef.ms_Pad) == [
        "     @0000         Sub {",
        "     @0000          My ss_My {",
        "#0001 0000 @0002/0002 +0002     UWORD                ms_Pad              ",
        "     @0002 =0020    }",
        "     @0002 =0020   }",
    ]
