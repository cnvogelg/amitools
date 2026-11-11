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
import io
import os



def dos_filehandle_tell_pipe_test():
    read_fd, write_fd = os.pipe()
    os.close(write_fd)
    with os.fdopen(read_fd, "rb") as stream:
        fh = FileHandle(stream, "<STDIN>", "/dev/stdin", need_close=False)
        assert fh.tell() == -1
        assert fh.seek(0, 1) == -1


def dos_filehandle_tell_position_test():
    with io.BytesIO(b"abcdef") as stream:
        stream.seek(3)
        fh = FileHandle(stream, "SYS:test", "/tmp/test", need_close=False)
        assert fh.tell() == 3
