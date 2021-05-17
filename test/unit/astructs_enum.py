import pytest
from amitools.vamos.astructs import EnumType, Enum, ULONG
from amitools.vamos.machine import MockMemory


@EnumType
class MyEnum(Enum, ULONG):
    a = 3
    b = 4
    c = 0xFFFFFFFF


def astructs_enum_type_test():
    # to_str
    assert MyEnum.to_str(3) == "a"
    with pytest.raises(ValueError):
        MyEnum.to_str(5)
    assert MyEnum.to_str(5, check=False) == "5"
    # from_str
    assert MyEnum.from_str("a") == 3
    with pytest.raises(ValueError):
        MyEnum.from_str("bla")


def astructs_enum_inst_test():
    mem = MockMemory()
    mem.w32(4, 3)
    # instance
    me = MyEnum(mem=mem, addr=4)
    assert me.get() == MyEnum.a
    assert str(me) == "a"
    assert repr(me) == "MyEnum('a')"
    assert int(me) == MyEnum.a
    # change
    me.set(MyEnum.c)
    assert me.get() == MyEnum.c
    assert str(me) == "c"
    assert int(me) == MyEnum.c
    assert mem.r32(4) == MyEnum.c
    me.set("b")
    assert me.get() == MyEnum.b
    assert str(me) == "b"
    assert int(me) == MyEnum.b
    assert mem.r32(4) == MyEnum.b
