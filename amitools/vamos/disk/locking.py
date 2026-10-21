"""Native, session-owned locks for independent regions of a disk image."""

import ctypes
import os
from pathlib import Path
import stat
import sys


class PartitionFileLock:
    """Exclude raw sessions while sharing nonoverlapping image partitions.

    Acquire the guard before reading partition metadata, then lock_range()
    before exposing data to a handler. Offsets are absolute image bytes.
    Locks live beyond EOF so Windows data handles can still access the image.
    The image must not be resized while any cooperating session holds a lock.
    """

    def __init__(self, image, *, read_only=True):
        self.image = Path(image)
        self.read_only = read_only
        self._file = None
        self._range = None
        self._size = 0

    @property
    def is_locked(self):
        return self._file is not None

    def acquire(self):
        if self.is_locked:
            return
        stream = open(self.image, "rb" if self.read_only else "r+b", buffering=0)
        try:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise OSError("partition locks require a regular image file")
            self._file = stream
            self._size = info.st_size
            if sys.platform.startswith("linux"):
                # Linux flock and OFD locks are independent. Retain the
                # flock guard for compatibility with whole-image sessions.
                import fcntl

                fcntl.flock(stream, fcntl.LOCK_SH | fcntl.LOCK_NB)
            else:
                # Darwin flock also conflicts with OFD locks. On Windows
                # this byte is the existing HostFileLock exclusion point.
                self._lock(self._size, 1, shared=True)
        except BaseException:
            self.release()
            stream.close()
            raise

    def lock_range(self, offset, length):
        if not self.is_locked:
            raise RuntimeError("partition guard is not held")
        if self._range is not None:
            raise RuntimeError("partition range is already locked")
        start = self._size + 1 + offset
        if offset < 0 or length <= 0 or start + length > (1 << 63) - 1:
            raise ValueError("invalid partition byte range")
        try:
            self._lock(start, length, shared=self.read_only)
        except OSError as exc:
            raise OSError("cannot lock partition in %s: %s" % (self.image, exc)) from exc
        self._range = (offset, length)

    def _lock(self, start, length, *, shared):
        if sys.platform == "win32":
            self._lock_windows(start, length, shared)
            return
        import fcntl

        if sys.platform == "darwin":
            class Flock(ctypes.Structure):
                _fields_ = [("start", ctypes.c_int64), ("length", ctypes.c_int64),
                            ("pid", ctypes.c_int), ("type", ctypes.c_short),
                            ("whence", ctypes.c_short)]
            command = getattr(fcntl, "F_OFD_SETLK", 90)
        elif sys.platform.startswith("linux") and ctypes.sizeof(ctypes.c_void_p) == 8:
            class Flock(ctypes.Structure):
                _fields_ = [("type", ctypes.c_short), ("whence", ctypes.c_short),
                            ("start", ctypes.c_int64), ("length", ctypes.c_int64),
                            ("pid", ctypes.c_int)]
            command = getattr(fcntl, "F_OFD_SETLK", 37)
        else:
            raise OSError("session-owned partition locks unavailable on this platform")
        lock = Flock()
        lock.start, lock.length = start, length
        lock.type = fcntl.F_RDLCK if shared else fcntl.F_WRLCK
        lock.whence = os.SEEK_SET
        # OFD ownership survives closing the separate RDB/data handles and
        # distinguishes two sessions even when they run in the same process.
        fcntl.fcntl(self._file.fileno(), command, bytes(lock))

    def _lock_windows(self, start, length, shared):
        import msvcrt
        from ctypes import wintypes

        class Overlapped(ctypes.Structure):
            _fields_ = [("internal", ctypes.c_size_t),
                        ("internal_high", ctypes.c_size_t),
                        ("offset", wintypes.DWORD),
                        ("offset_high", wintypes.DWORD),
                        ("event", wintypes.HANDLE)]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        lock_file = kernel.LockFileEx
        lock_file.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                             wintypes.DWORD, wintypes.DWORD,
                             ctypes.POINTER(Overlapped)]
        lock_file.restype = wintypes.BOOL
        overlapped = Overlapped()
        overlapped.offset = start & 0xffffffff
        overlapped.offset_high = start >> 32
        flags = 1 if shared else 3  # FAIL_IMMEDIATELY, optionally EXCLUSIVE
        handle = msvcrt.get_osfhandle(self._file.fileno())
        if not lock_file(handle, flags, 0, length & 0xffffffff,
                         length >> 32, ctypes.byref(overlapped)):
            raise ctypes.WinError(ctypes.get_last_error())

    def release(self):
        stream = self._file
        self._file = None
        self._range = None
        if stream is not None:
            # All three native APIs release their locks on handle close,
            # including when a process exits without explicit cleanup.
            stream.close()
