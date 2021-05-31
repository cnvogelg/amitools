from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.libtypes import ExecLibrary


def libtypes_execlib_base_test():
    mem = MockMemory()
    el = ExecLibrary(mem, 0x100)
    el.new_lib()
    el.fill_funcs()


def libtypes_execlib_alloc_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    el = ExecLibrary.alloc(alloc, name="exec.library", id_string="bla", neg_size=20)
    assert el.name.str == "exec.library"
    assert el.id_string.str == "bla"
    assert el.neg_size.val == 20
    assert el.pos_size.val == ExecLibrary.get_size()
    el.new_lib()
    el.fill_funcs()
    el.free()
    assert alloc.is_all_free()
