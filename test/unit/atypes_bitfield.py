import pytest
from amitools.vamos.atypes import BitFieldType


def atypes_bitfield_test():
  @BitFieldType
  class MyBF:
    a = 1
    b = 2
    c = 4
  # to_strs
  assert MyBF.to_strs(1) == ['a']
  assert MyBF.to_strs(5) == ['a', 'c']
  with pytest.raises(ValueError):
    MyBF.to_strs(9)
  assert MyBF.to_strs(9, check=False) == ['a', '8']
  # from_strs
  assert MyBF.from_strs('a') == 1
  assert MyBF.from_strs('a', 'c') == 5
  with pytest.raises(ValueError):
    MyBF.from_strs('bla')
  # is_set
  assert MyBF.is_set('a', 1)
  assert MyBF.is_set(1, 1)
  assert not MyBF.is_set('a', 2)
  with pytest.raises(ValueError):
    MyBF.is_set('bla', 5)
  # is_clr
  assert MyBF.is_clr('a', 2)
  assert MyBF.is_clr(1, 2)
  assert not MyBF.is_clr('a', 1)
  with pytest.raises(ValueError):
    MyBF.is_clr('bla', 5)
