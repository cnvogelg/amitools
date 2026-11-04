from types import SimpleNamespace

from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.lib.dos.FileHandle import FileHandle
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.machine.regs import REG_D1, REG_D2, REG_D3, REG_D4
from amitools.vamos.mem import MemoryAlloc


class _DummyFile:
    def __init__(self):
        self.data = bytearray()
        self.flush_count = 0

    def isatty(self):
        return False

    def write(self, data):
        self.data.extend(data)

    def flush(self):
        self.flush_count += 1


def dos_filehandle_setvbuf_test():
    cpu = MockCPU()
    ctx = SimpleNamespace(cpu=cpu)
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    file_obj = _DummyFile()
    fh = FileHandle(file_obj, "SYS:test", "/tmp/test")
    fh_b_addr = fh.alloc_fh(alloc, 0x1234)
    lib = DosLibrary()
    lib.file_mgr = SimpleNamespace(get_by_b_addr=lambda b_addr, for_writing=None: fh)

    cpu.w_reg(REG_D1, fh_b_addr)
    cpu.w_reg(REG_D2, 0x5678)
    cpu.w_reg(REG_D3, 1)
    cpu.w_reg(REG_D4, 0x1000)

    assert lib.SetVBuf(ctx) == 0
    assert fh.struct.fh_Buf.val == 0x5678
    assert fh.buf_type == 1
    assert fh.buf_size == 0x1000

    assert fh.write(b"line\n") == 5
    assert file_obj.data == b"line\n"
    assert file_obj.flush_count == 1

    fh.free_fh(alloc)


def dos_filehandle_setvbuf_full_buffer_test():
    file_obj = _DummyFile()
    fh = FileHandle(file_obj, "SYS:test", "/tmp/test")
    fh.setvbuf(0, 0, 0x1000)

    assert fh.write(b"data") == 4
    assert file_obj.flush_count == 0
