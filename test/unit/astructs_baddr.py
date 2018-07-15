import pytest
from amitools.vamos.astructs import BAddr


def astructs_baddr_repr_test():
  assert repr(BAddr(0)) == "BAddr(0)"
  assert repr(BAddr(44)) == "BAddr(44)"


def astructs_baddr_str_test():
  assert str(BAddr(0)) == "BAddr(00000000,addr=00000000)"
  assert str(BAddr(0x40)) == "BAddr(00000040,addr=00000100)"


def astructs_baddr_eq_ne_test():
  assert BAddr(0) == BAddr(0)
  assert BAddr(0) != BAddr(1)
  assert BAddr(0x40) == 0x100
  assert BAddr(0x40) != 0x40


def astructs_baddr_int_test():
  assert int(BAddr(0)) == 0
  assert int(BAddr(0x40)) == 0x100


def astructs_baddr_from_addr_test():
  assert BAddr.from_addr(0x100) == BAddr(0x40)
  with pytest.raises(ValueError):
    BAddr.from_addr(0x102)


def astructs_baddr_get_test():
  assert BAddr(0).get_baddr() == 0
  assert BAddr(0).get_addr() == 0
  assert BAddr(0x40).get_baddr() == 0x40
  assert BAddr(0x40).get_addr() == 0x100

def astructs_baddr_rshift_test():
  assert BAddr(0x40) >> 2 == 0x40
