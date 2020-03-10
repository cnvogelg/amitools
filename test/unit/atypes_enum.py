import pytest
from amitools.vamos.atypes import EnumType


def atype_enum_test():
    @EnumType
    class MyEnum:
        a = 3
        b = 4
        c = 0xFFFFFFFF

    # to_str
    assert MyEnum.to_str(3) == "a"
    with pytest.raises(ValueError):
        MyEnum.to_str(5)
    assert MyEnum.to_str(5, check=False) == "5"
    # from_str
    assert MyEnum.from_str("a") == 3
    with pytest.raises(ValueError):
        MyEnum.from_str("bla")
    # instance
    a = MyEnum("a")
    assert a.get_value() == 3
    assert str(a) == "a"
    assert repr(a) == "MyEnum('a')"
    assert int(a) == 3
    assert a == 3
    assert a == MyEnum(3)
    c = MyEnum("c")
    assert c.get_value() == 0xFFFFFFFF
    assert str(c) == "c"
    assert int(c) == 0xFFFFFFFF
    assert c == 0xFFFFFFFF
