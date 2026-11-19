"""CONSOLE: device handler.

``CONSOLE:`` (and its alias ``*``) is the AmigaDOS console device. In vamos
the console is the host's standard input/output. The handler owns the console
specific behavior: the tty (termios) handling and the ESC/CSI and Latin-1 to
UTF-8 conversions. The DOS layer only ever sees a plain byte stream.
"""

import sys

from .base import (
    ERROR_OBJECT_NOT_FOUND,
    MODE_NEWFILE,
    DeviceLock,
    Handler,
    HandlerError,
    HandlerFile,
)
from .terminal import Latin1ToUtf8Converter, Terminal


class ConsoleStream:
    """A file-like view of a host standard stream with console conversions.

    It wraps a raw binary stream (``sys.stdin.buffer`` / ``sys.stdout.buffer``)
    and applies the same conversions the old ``Terminal`` helper did: ESC/CSI
    handling on a tty and a Latin-1 to UTF-8 conversion when the host stdout
    uses UTF-8. The DOS layer wraps it as an ordinary file object.
    """

    def __init__(self, obj, direction):
        self.obj = obj
        self.direction = direction  # "in" or "out"
        self.interactive = obj.isatty()
        if self.interactive:
            self.terminal = Terminal(obj)
        else:
            self.terminal = None
            # convert Latin-1 to UTF-8 for non-tty stdout if the host uses it
            enc = sys.stdout.encoding
            is_utf8 = enc and enc.lower().replace("-", "") == "utf8"
            if direction == "out" and obj is sys.stdout.buffer and is_utf8:
                self.latin1_conv = Latin1ToUtf8Converter()
            else:
                self.latin1_conv = None

    # --- plain file protocol used by FileHandle ---

    def isatty(self):
        return self.interactive

    def fileno(self):
        return self.obj.fileno()

    def read(self, size=-1):
        if self.terminal:
            return self.terminal.read(size)
        return self.obj.read(size)

    def read1(self, size=-1):
        if self.terminal:
            return self.terminal.read(size)
        read = getattr(self.obj, "read1", None)
        if read is None:
            return self.obj.read(size)
        return read(size)

    def write(self, data):
        orig_len = len(data)
        if self.terminal:
            return self.terminal.write(data)
        if self.latin1_conv:
            data = self.latin1_conv.convert(data)
        self.obj.write(data)
        return orig_len

    def tell(self):
        return self.obj.tell()

    def seek(self, pos, whence=0):
        return self.obj.seek(pos, whence)

    def flush(self):
        return self.obj.flush()

    def close(self):
        # never close the shared host stream, only restore the tty state
        if self.terminal:
            self.terminal.close()

    # --- console specific operations ---

    def set_mode(self, cooked):
        if self.terminal:
            return self.terminal.set_mode(cooked)
        return False

    def wait_for_char(self, timeout):
        if self.terminal:
            return self.terminal.wait_for_char(timeout)
        return None


class ConsoleFile(HandlerFile):
    """open ``CONSOLE:`` handle backed by a host console stream"""

    need_close = False

    def __init__(self, stream, name, auto_flush=False):
        super().__init__(key=name.lower())
        self.fobj = stream
        self.name = name
        self.auto_flush = auto_flush


class ConsoleHandler(Handler):
    """device handler for ``CONSOLE:`` / ``*``"""

    def __init__(self, name):
        super().__init__(name, is_filesystem=False)
        # one stream per direction: all console opens share the tty state
        self._in = None
        self._out = None

    def _input_stream(self):
        if self._in is None:
            self._in = ConsoleStream(sys.stdin.buffer, "in")
        return self._in

    def _output_stream(self):
        if self._out is None:
            self._out = ConsoleStream(sys.stdout.buffer, "out")
        return self._out

    # --- device root lock ---

    def locate_object(self, ami_path, exclusive=False):
        # only the device root exists; ``CONSOLE:foo`` is still openable but
        # has no object to lock
        if ami_path:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        lock = DeviceLock(self.name)
        lock.handler = self
        return lock

    def free_lock(self, lock):
        pass

    def find_input(self, ami_path):
        return ConsoleFile(self._input_stream(), "<STDIN>")

    def find_output(self, ami_path, mode=MODE_NEWFILE):
        return ConsoleFile(self._output_stream(), "<STDOUT>", auto_flush=True)

    def find_update(self, ami_path):
        return ConsoleFile(self._output_stream(), "<STDOUT>", auto_flush=True)

    # ----- file ops (packet-backed) -----

    def read(self, fh, size):
        # read1 returns whatever is available without waiting to fill the
        # whole request, matching the console/pipe semantics
        return fh.fobj.read1(size)

    def write(self, fh, data):
        return fh.fobj.write(data)

    def flush(self, fh):
        fh.fobj.flush()

    def end(self, fh):
        # never close the shared host stream (ConsoleFile.need_close is False)
        pass

    def set_mode(self, fh, cooked):
        stream = fh.fobj if fh is not None else self._input_stream()
        return stream.set_mode(cooked)

    def wait_for_char(self, fh, timeout):
        stream = fh.fobj if fh is not None else self._input_stream()
        return stream.wait_for_char(timeout)

    def shutdown(self):
        for stream in (self._in, self._out):
            if stream is not None:
                stream.close()
        self._in = None
        self._out = None
