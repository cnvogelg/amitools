import pytest
from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.atypes import BString


def atypes_bstring_base_test():
  mem = MockMemory()
  alloc = MemoryAlloc(mem)
  # simple string
  txt = "hello, world!"
  bs = BString.alloc(alloc, txt)
  assert bs
  assert bs.get_baddr() << 2 == bs.get_addr()
  assert mem.r_bstr(bs.get_addr()) == txt
  assert bs.get_string() == txt
  assert bs == txt
  assert bs == bs.get_addr()
  assert bs == BString(mem, bs.get_addr())
  bs.free()
  assert alloc.is_all_free()


def atypes_bstring_empty_test():
  mem = MockMemory()
  alloc = MemoryAlloc(mem)
  # empty string
  txt = ""
  bs = BString.alloc(alloc, txt)
  assert bs
  assert bs.get_baddr() << 2 == bs.get_addr()
  assert mem.r_bstr(bs.get_addr()) == txt
  assert bs.get_string() == txt
  assert bs == txt
  assert bs == bs.get_addr()
  bs.free()
  assert alloc.is_all_free()


def atypes_bstring_null_test():
  mem = MockMemory()
  alloc = MemoryAlloc(mem)
  # no string
  bs = BString.alloc(alloc, None)
  assert bs
  assert bs.get_baddr() << 2 == bs.get_addr()
  assert bs.get_addr() == 0
  assert bs.get_string() is None
  bs.free()
  assert alloc.is_all_free()


def atypes_bstring_alloc_bstr_test():
  mem = MockMemory()
  alloc = MemoryAlloc(mem)
  # no string
  bs = BString.alloc(alloc, "bla")
  bs2 = BString.alloc(alloc, bs)
  assert bs
  assert bs.get_string() == "bla"
  assert bs2
  assert bs2.get_string() == "bla"
  bs.free()
  bs2.free()
  assert alloc.is_all_free()


def atypes_bstring_max_size_test():
  mem = MockMemory()
  alloc = MemoryAlloc(mem)
  bs = BString.alloc(alloc, "bla")
  assert bs.get_max_size() == 3
  bs.set_string("foo")
  assert bs == "foo"
  with pytest.raises(ValueError):
    bs.set_string("foo!")
