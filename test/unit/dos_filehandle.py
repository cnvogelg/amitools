from amitools.vamos.handler import (
    MODE_NEWFILE,
    Handler,
    HandlerError,
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


# ----- set_file_size (ACTION_SET_FILE_SIZE) -----


def _handler_file(fobj):
    hf = HandlerFile()
    hf.fobj = fobj
    return hf


def dos_filehandle_set_file_size_handler_test():
    calls = []

    class _SizeHandler:
        def set_file_size(self, handler_file, size, mode):
            calls.append((handler_file, size, mode))
            return 42

    stream = io.BytesIO(b"x")
    hf = _handler_file(stream)
    fh = FileHandle(stream, "SYS:f", "f", handler=_SizeHandler(), handler_file=hf)

    assert fh.set_file_size(10, -1) == 42
    assert calls == [(hf, 10, -1)]


def dos_filehandle_set_file_size_handler_error_test():
    class _SizeHandler:
        def set_file_size(self, handler_file, size, mode):
            raise HandlerError(212)

    stream = io.BytesIO(b"x")
    hf = _handler_file(stream)
    fh = FileHandle(stream, "SYS:f", "f", handler=_SizeHandler(), handler_file=hf)

    assert fh.set_file_size(10, -1) == -1


def dos_filehandle_set_file_size_raw_test():
    with io.BytesIO(b"0123456789") as stream:
        fh = FileHandle(stream, "SYS:f", "f", need_close=False)
        # OFFSET_BEGINNING (-1): the new size is the offset
        assert fh.set_file_size(4, -1) == 4
        assert stream.getvalue() == b"0123"
        # OFFSET_END (1): the new size is the current size + offset
        assert fh.set_file_size(-1, 1) == 3
        assert stream.getvalue() == b"012"
        # OFFSET_CURRENT (0): the new size is the position + offset
        stream.seek(2)
        assert fh.set_file_size(1, 0) == 3
        assert stream.getvalue() == b"012"
        # a negative resulting size fails
        assert fh.set_file_size(-1, -1) == -1
        # an unknown mode fails without touching the stream
        assert fh.set_file_size(0, 7) == -1
        assert stream.getvalue() == b"012"
