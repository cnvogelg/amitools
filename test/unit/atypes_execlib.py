from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.atypes import ExecLibrary


def atypes_execlib_base_test():
  mem = MockMemory()
  el = ExecLibrary(mem, 0x100)
  el.setup()


def atypes_execlib_alloc_test():
  mem = MockMemory()
  alloc = MemoryAlloc(mem)
  el = ExecLibrary.alloc(alloc, "exec.library", "bla", 20)
  el.setup()
  el.free()
  assert alloc.is_all_free()

