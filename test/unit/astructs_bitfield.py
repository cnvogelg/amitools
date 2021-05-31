import pytest
from amitools.vamos.astructs import BitFieldType, BitField, ULONG, UWORD, UBYTE
from amitools.vamos.machine import MockMemory


@BitFieldType
class MyBF(BitField, ULONG):
    a = 1
    b = 2
    c = 4


def astructs_bitfield_type_test():
    # to_strs
    assert MyBF.to_strs(1) == ["a"]
    assert MyBF.to_str(1) == "a"
    assert MyBF.to_strs(5) == ["a", "c"]
    assert MyBF.to_str(5) == "a|c"
    with pytest.raises(ValueError):
        MyBF.to_strs(9)
    assert MyBF.to_strs(9, check=False) == ["a", "8"]
    assert MyBF.to_str(9, check=False) == "a|8"
    # from_strs
    assert MyBF.from_strs("a") == 1
    assert MyBF.from_strs("a", "c") == 5
    assert MyBF.from_str("a") == 1
    assert MyBF.from_str("a|c") == 5
    with pytest.raises(ValueError):
        MyBF.from_strs("bla")
    # is_set
    assert MyBF.is_set("a", 1)
    assert MyBF.is_set(1, 1)
    assert not MyBF.is_set("a", 2)
    with pytest.raises(ValueError):
        MyBF.is_set("bla", 5)
    # is_clr
    assert MyBF.is_clr("a", 2)
    assert MyBF.is_clr(1, 2)
    assert not MyBF.is_clr("a", 1)
    with pytest.raises(ValueError):
        MyBF.is_clr("bla", 5)


def astructs_bitfield_inst_test():
    mem = MockMemory()
    mem.w32(4, 1)
    # instance
    bf = MyBF(mem=mem, addr=4)
    assert str(bf) == "a"
    assert repr(bf) == "MyBF('a')"
    assert int(bf) == MyBF.a
    assert bf.has_bits(MyBF.a)
    assert bf.has_bits("a")
    # set bit
    bf.set_bits(MyBF.c)
    assert str(bf) == "a|c"
    assert int(bf) == MyBF.c | MyBF.a
    assert bf.has_bits("c")
    assert bf.has_bits(MyBF.c)
    assert bf.has_bits("a")
    assert bf.has_bits(MyBF.a)
    assert mem.r32(4) == MyBF.c | MyBF.a
    # clr bit
    bf.clr_bits(MyBF.a)
    assert str(bf) == "c"
    assert int(bf) == MyBF.c
    assert bf.has_bits("c")
    assert bf.has_bits(MyBF.c)
    assert not bf.has_bits("a")
    assert not bf.has_bits(MyBF.a)
    assert mem.r32(4) == MyBF.c
    # set value
    bf.set(MyBF.a | MyBF.b)
    assert str(bf) == "a|b"
    assert int(bf) == MyBF.b | MyBF.a
    assert bf.has_bits("b")
    assert bf.has_bits(MyBF.b)
    assert bf.has_bits("a")
    assert bf.has_bits(MyBF.a)
    assert mem.r32(4) == MyBF.b | MyBF.a
