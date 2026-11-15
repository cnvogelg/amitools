import io
import os
import tempfile
import threading
from types import SimpleNamespace

import pytest

from amitools.vamos.lib.dos.FileHandle import FileHandle


@pytest.mark.parametrize("buffering", [-1, 0])
def dos_filehandle_read_file_test(buffering):
    with tempfile.TemporaryFile(mode="w+b", buffering=buffering) as stream:
        stream.write(b"abcdef")
        stream.seek(0)
        handle = FileHandle(stream, "SYS:test", "/tmp/test", need_close=False)
        assert handle.read(0) == b""
        assert handle.read(3) == b"abc"
        assert handle.read(99) == b"def"
        assert handle.read(1) == b""


@pytest.mark.parametrize("buffering", [-1, 0])
def dos_filehandle_read_write_only_error_test(tmp_path, buffering):
    with open(tmp_path / "write_only", "wb", buffering=buffering) as stream:
        handle = FileHandle(stream, "SYS:test", "/tmp/test", need_close=False)
        assert handle.read(1) == -1


def dos_filehandle_read_terminal_test():
    with io.BytesIO(b"file input") as stream:
        handle = FileHandle(stream, "SYS:test", "/tmp/test", need_close=False)
        calls = []

        def read(size):
            calls.append(size)
            return b"terminal input"

        handle.terminal = SimpleNamespace(read=read)
        assert handle.read(42) == b"terminal input"
        assert calls == [42]
        assert stream.tell() == 0


@pytest.mark.parametrize("buffering", [-1, 0])
def dos_filehandle_read_pipe_short_test(buffering):
    read_fd, write_fd = os.pipe()
    stream = os.fdopen(read_fd, "rb", buffering=buffering)
    handle = FileHandle(stream, "<STDIN>", "/dev/stdin", need_close=False)
    results = []
    errors = []
    finished = threading.Event()

    def read():
        try:
            results.append(handle.read(128))
        except Exception as error:
            errors.append(error)
        finally:
            finished.set()

    reader = threading.Thread(target=read, daemon=True)
    try:
        assert os.write(write_fd, b"available") == 9
        reader.start()
        # Leave the writer open: read() on a buffered pipe would wait to
        # fill the request, whereas read1() must return the available bytes.
        returned_before_eof = finished.wait(timeout=2)
    finally:
        os.close(write_fd)
        reader.join(timeout=2)
        stream.close()
    assert not reader.is_alive()
    assert returned_before_eof, "read waited for EOF despite available data"
    assert not errors, errors
    assert results == [b"available"]
