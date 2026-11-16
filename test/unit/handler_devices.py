import io
import sys

from amitools.vamos.handler import (
    MODE_NEWFILE,
    MODE_OLDFILE,
    MODE_READWRITE,
    ConsoleHandler,
    NilHandler,
)
from amitools.vamos.handler.console import ConsoleStream
from amitools.vamos.handler.terminal import Latin1ToUtf8Converter


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
    # output opens wrap the standard output stream and auto-flush
    out = h.find_output("", MODE_NEWFILE)
    assert out.fobj.obj is sys.stdout.buffer
    assert out.fobj.direction == "out"
    assert out.need_close is False
    assert out.auto_flush is True
    # input opens wrap the standard input stream
    inp = h.find_input("")
    assert inp.fobj.obj is sys.stdin.buffer
    assert inp.fobj.direction == "in"
    assert inp.need_close is False
    # find_update is an output open too
    upd = h.find_update("")
    assert upd.fobj.obj is sys.stdout.buffer
    # all opens share one stream per direction
    assert h.find_output("").fobj is out.fobj
    assert h.find_input("").fobj is inp.fobj
    # shutdown restores the tty state and drops the streams
    h.shutdown()
    assert h._in is None and h._out is None


def handler_console_file_ops_test():
    from amitools.vamos.handler.console import ConsoleFile

    h = ConsoleHandler("console")
    # input: read via the stream's read1 (short reads, no blocking)
    in_buf = io.BytesIO(b"hello")
    in_file = ConsoleFile(ConsoleStream(in_buf, "in"), "<TEST>")
    assert h.read(in_file, 3) == b"hel"
    assert h.read(in_file, 10) == b"lo"
    # end never closes the shared host stream
    h.end(in_file)
    assert in_buf.closed is False
    # output: write/flush go to the stream
    out_buf = io.BytesIO()
    out_file = ConsoleFile(ConsoleStream(out_buf, "out"), "<TEST>", auto_flush=True)
    assert h.write(out_file, b"abc") == 3
    h.flush(out_file)
    assert out_buf.getvalue() == b"abc"
    # mode switching and waiting are delegated to the stream; on a plain
    # (non-tty) stream they report "unsupported"
    assert h.set_mode(in_file, True) is False
    assert h.wait_for_char(in_file, 0) is None


def handler_console_stream_test():
    # non-interactive stream: plain byte pass-through
    buf = io.BytesIO(b"hello")
    stream = ConsoleStream(buf, "in")
    assert stream.isatty() is False
    assert stream.read(5) == b"hello"
    buf = io.BytesIO(b"hello")
    stream = ConsoleStream(buf, "out")
    assert stream.read1(5) == b"hello"
    assert stream.write(b"world") == 5
    assert buf.getvalue() == b"helloworld"
    assert stream.tell() == 10
    assert stream.seek(0) == 0
    stream.flush()
    # tty operations are unavailable on a plain stream
    assert stream.set_mode(True) is False
    assert stream.wait_for_char(0) is None
    # closing never closes the shared host stream
    stream.close()
    assert buf.closed is False


def handler_console_latin1_test():
    # the console handler converts Latin-1 output to UTF-8 when the host
    # stdout uses UTF-8; check the conversion itself on a plain stream
    buf = io.BytesIO()
    stream = ConsoleStream(buf, "out")
    stream.latin1_conv = Latin1ToUtf8Converter()
    assert stream.write("ä".encode("latin-1")) == 1
    assert buf.getvalue() == b"\xc3\xa4"
