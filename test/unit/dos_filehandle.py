from amitools.vamos.lib.dos.FileHandle import FileHandle
from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc


class _DummyFile:
    def isatty(self):
        return False

    def close(self):
        pass


def dos_filehandle_alloc_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    fh = FileHandle(_DummyFile(), "SYS:test", "/tmp/test", need_close=False)

    assert fh.alloc_fh(alloc, 0x1234) == fh.b_addr
    assert fh.struct.fh_Args.val == fh.b_addr
    assert fh.struct.fh_Type.aptr == 0x1234
    assert fh.struct.fh_End.val == 1

    fh.free_fh(alloc)
    assert alloc.is_all_free()
