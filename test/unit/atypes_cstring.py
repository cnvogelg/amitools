import pytest
from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.atypes import CString


def atypes_cstring_base_test():
  mem = MockMemory()
  alloc = MemoryAlloc(mem)
  # simple string
  txt = "hello, world!"
  cs = CString.alloc(alloc, txt)
  assert cs
  assert mem.r_cstr(cs.get_addr()) == txt
  assert cs.get_string() == txt
  assert cs == txt
  assert cs == cs.get_addr()
  assert cs == CString(mem, cs.get_addr())
  cs.free()
  assert alloc.is_all_free()


def atypes_cstring_empty_test():
  mem = MockMemory()
  alloc = MemoryAlloc(mem)
  # empty string
  txt = ""
  cs = CString.alloc(alloc, txt)
  assert cs
  assert mem.r_cstr(cs.get_addr()) == txt
  assert cs.get_string() == txt
  assert cs == txt
  assert cs == cs.get_addr()
  cs.free()
  assert alloc.is_all_free()


def atypes_cstring_null_test():
  mem = MockMemory()
  alloc = MemoryAlloc(mem)
  # no string
  cs = CString.alloc(alloc, None)
  assert cs
  assert cs.get_addr() == 0
  assert cs.get_string() is None
  cs.free()
  assert alloc.is_all_free()


def atypes_cstring_alloc_cstr_test():
  mem = MockMemory()
  alloc = MemoryAlloc(mem)
  # no string
  cs = CString.alloc(alloc, "bla")
  cs2 = CString.alloc(alloc, cs)
  assert cs
  assert cs.get_string() == "bla"
  assert cs2
  assert cs2.get_string() == "bla"
  cs.free()
  cs2.free()
  assert alloc.is_all_free()


def atypes_cstring_max_size_test():
  mem = MockMemory()
  alloc = MemoryAlloc(mem)
  cs = CString.alloc(alloc, "bla")
  assert cs.get_max_size() == 3
  cs.set_string("foo")
  assert cs == "foo"
  with pytest.raises(ValueError):
    cs.set_string("foo!")
