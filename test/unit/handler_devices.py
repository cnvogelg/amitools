import sys

from amitools.vamos.handler import (
    MODE_NEWFILE,
    MODE_OLDFILE,
    MODE_READWRITE,
    ConsoleHandler,
    NilHandler,
)


def handler_nil_test():
    h = NilHandler("nil")
    assert h.is_filesystem is False
    assert h.name == "nil"
    for mode in (MODE_OLDFILE, MODE_NEWFILE, MODE_READWRITE):
        fh = h.find_output("", mode)
        assert fh.is_nil is True
        # reads give EOF, writes are discarded
        assert h.read(fh, 10) == b""
        assert h.write(fh, b"data") == 4
        assert h.seek(fh, 0, 0) == 0
        h.flush(fh)
        h.end(fh)
    fh = h.find_input("")
    assert fh.is_nil is True
    # the underlying stream behaves like a null device
    assert fh.fobj.read(10) == b""
    assert fh.fobj.read1(10) == b""
    assert fh.fobj.write(b"x") == 1
    assert fh.fobj.isatty() is False
    assert fh.fobj.tell() == 0


def handler_console_test():
    h = ConsoleHandler("console")
    assert h.is_filesystem is False
    fh = h.find_output("", MODE_NEWFILE)
    # the console wraps the host standard streams
    assert fh.fobj is sys.stdout.buffer
    assert fh.need_close is False
    assert fh.auto_flush is True
    # every console open yields the output stream (reads are redirected by DOS)
    fh = h.find_input("")
    assert fh.fobj is sys.stdout.buffer
    assert fh.need_close is False
    fh = h.find_update("")
    assert fh.fobj is sys.stdout.buffer
