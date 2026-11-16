from amitools.vamos.handler import (
    MODE_NEWFILE,
    Handler,
    HandlerFile,
    NilHandler,
)
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


def dos_filehandle_handler_delegation_test():
    # a handler-backed handle delegates the packet ops to the handler
    h = NilHandler("nil")
    hf = h.find_output("", MODE_NEWFILE)
    fh = FileHandle(
        hf.fobj,
        "NIL:",
        "NIL:",
        handler=h,
        handler_file=hf,
        need_close=hf.need_close,
        is_nil=hf.is_nil,
    )
    assert fh.read(10) == b""
    assert fh.write(b"data") == 4
    assert fh.seek(0, 0) == 0
    fh.flush()
    fh.close()


def dos_filehandle_handler_unsupported_test():
    # a handler that does not implement an action maps it to the DOS failure
    # code instead of touching the raw stream
    class _Obj:
        def isatty(self):
            return False

        def close(self):
            pass

    hf = HandlerFile()
    hf.fobj = _Obj()
    fh = FileHandle(_Obj(), "X:", "X:", handler=Handler("dummy"), handler_file=hf)
    assert fh.read(1) == -1
    assert fh.write(b"x") == -1
    assert fh.seek(0, 0) == -1
    assert fh.set_mode(True) is False
    assert fh.wait_for_char(0) is None
    fh.flush()
    fh.close()
