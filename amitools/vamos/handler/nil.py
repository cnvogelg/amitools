"""NIL: device handler.

``NIL:`` is an AmigaDOS device, not a volume: every read returns EOF and
every write is discarded. The handler exposes a small in-memory stream so the
DOS layer can treat a ``NIL:`` file handle like any other, without touching a
host path.
"""

from .base import (
    ERROR_OBJECT_NOT_FOUND,
    MODE_NEWFILE,
    DeviceLock,
    Handler,
    HandlerError,
    HandlerFile,
)


class NilStream:
    """A file-like object that reads EOF and discards all writes."""

    def read(self, size=-1):
        return b""

    def read1(self, size=-1):
        return b""

    def write(self, data):
        return len(data)

    def flush(self):
        pass

    def close(self):
        pass

    def isatty(self):
        return False

    def tell(self):
        return 0

    def seek(self, pos, whence=0):
        return 0

    def fileno(self):
        raise OSError("NIL: has no file descriptor")


class NilFile(HandlerFile):
    """open ``NIL:`` handle: reads EOF, writes are discarded"""

    is_nil = True

    def __init__(self):
        super().__init__(key="nil")
        self.fobj = NilStream()


class NilHandler(Handler):
    """device handler for ``NIL:``"""

    def __init__(self, name):
        super().__init__(name, is_filesystem=False)

    # --- device root lock ---

    def locate_object(self, ami_path, exclusive=False):
        # only the device root exists; ``NIL:foo`` is still openable but has
        # no object to lock
        if ami_path:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        lock = DeviceLock(self.name)
        lock.handler = self
        return lock

    def free_lock(self, lock):
        pass

    def find_input(self, ami_path):
        return NilFile()

    def find_output(self, ami_path, mode=MODE_NEWFILE):
        return NilFile()

    def find_update(self, ami_path):
        return NilFile()

    def read(self, fh, size):
        return b""

    def write(self, fh, data):
        return len(data)

    def seek(self, fh, offset, whence):
        return 0

    def flush(self, fh):
        pass

    def end(self, fh):
        pass
