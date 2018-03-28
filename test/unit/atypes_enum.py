import pytest
from amitools.vamos.atypes import EnumType


def atype_enum_test():
  @EnumType
  class MyEnum:
    a = 3
    b = 4
  # to_str
  assert MyEnum.to_str(3) == "a"
  with pytest.raises(ValueError):
    MyEnum.to_str(5)
  assert MyEnum.to_str(5, check=False) == "5"
  # from_str
  assert MyEnum.from_str("a") == 3
  with pytest.raises(ValueError):
    MyEnum.from_str("bla")
