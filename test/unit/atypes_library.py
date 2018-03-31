import pytest
from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.atypes import Library, CString


def atypes_library_base_test():
  mem = MockMemory()
  alloc = MemoryAlloc(mem)
  # alloc lib
  lib = Library.alloc(alloc)
  # alloc/set name
  name_txt = "my.library"
  name = CString.alloc(alloc, name_txt)
  lib.set_name(name)
  assert lib.get_name() == name_txt
  # allec/set id_string
  id_str_txt = "my.library 1.2"
  id_str = CString.alloc(alloc, id_str_txt)
  lib.set_id_string(id_str)
  assert lib.get_id_string() == id_str_txt
  # free all
  lib.free()
  name.free()
  id_str.free()
