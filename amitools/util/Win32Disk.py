"""Windows physical disks, exposed as seekable binary streams.

No pywin32 dependency. Win32 is loaded only when a device is actually opened.
Mount sessions hold an exclusive physical-drive handle; temporary readers in
the same process borrow it, each with their own cursor. Ordinary files never
enter this path.
"""

import ctypes
import io
import os
import re
import struct
import sys
import threading


def physical_drive_number(path):
    # Python <= 3.11 treats this as a UNC root and appends a backslash.
    name = os.fspath(path).rstrip("\\")
    match = re.fullmatch(r"\\\\[.?]\\PhysicalDrive([0-9]+)", name, re.I)
    return int(match[1]) if match else None


def is_windows_disk(path):
    return sys.platform == "win32" and physical_drive_number(path) is not None


class _Win32:
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    GET_LENGTH = 0x7405C
    GET_GEOMETRY = 0x70000
    GET_EXTENTS = 0x560000
    LOCK_VOLUME = 0x90018
    DISMOUNT_VOLUME = 0x90020

    def __init__(self):
        self.dll = ctypes.WinDLL("kernel32", use_last_error=True)
        # Fixed-width Windows types (also makes the ABI testable on Unix).
        handle, dword, boolean = ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int32
        ptr = ctypes.c_void_p
        signatures = {
            "CreateFileW": (handle, [ctypes.c_wchar_p, dword, dword, ptr, dword, dword, handle]),
            "CloseHandle": (boolean, [handle]),
            "DeviceIoControl": (boolean, [handle, dword, ptr, dword, ptr, dword, ptr, ptr]),
            "SetFilePointerEx": (boolean, [handle, ctypes.c_int64, ptr, dword]),
            "ReadFile": (boolean, [handle, ptr, dword, ptr, ptr]),
            "WriteFile": (boolean, [handle, ptr, dword, ptr, ptr]),
            "FlushFileBuffers": (boolean, [handle]),
            "FindFirstVolumeW": (handle, [ptr, dword]),
            "FindNextVolumeW": (boolean, [handle, ptr, dword]),
            "FindVolumeClose": (boolean, [handle]),
        }
        for name, (result, args) in signatures.items():
            fn = getattr(self.dll, name)
            fn.restype, fn.argtypes = result, args

    @staticmethod
    def error(action):
        code = ctypes.get_last_error()
        hint = ""
        if code == 5:
            hint = "; run as Administrator and close applications using this disk"
        elif code in (32, 33):
            hint = "; disk or volume is already in use"
        exc = OSError("%s: %s%s" % (action, ctypes.FormatError(code).strip(), hint))
        exc.winerror = code
        return exc

    def open(self, path, access, share=3):
        handle = self.dll.CreateFileW(path, access, share, None, 3, 0, None)
        if handle == ctypes.c_void_p(-1).value:
            raise self.error("cannot open %s" % path)
        return handle

    def close(self, handle):
        if not self.dll.CloseHandle(handle):
            raise self.error("cannot close disk handle")

    def ioctl(self, handle, code, size=0):
        buf = ctypes.create_string_buffer(size) if size else None
        count = ctypes.c_uint32()
        if not self.dll.DeviceIoControl(handle, code, None, 0, buf, size,
                                        ctypes.byref(count), None):
            raise self.error("disk control 0x%x failed" % code)
        return buf.raw[:count.value] if buf is not None else b""

    def volumes(self):
        buf = ctypes.create_unicode_buffer(1024)
        search = self.dll.FindFirstVolumeW(buf, len(buf))
        if search == ctypes.c_void_p(-1).value:
            if ctypes.get_last_error() == 18:  # ERROR_NO_MORE_FILES
                return
            raise self.error("cannot enumerate Windows volumes")
        try:
            while True:
                yield buf.value.rstrip("\\")
                if not self.dll.FindNextVolumeW(search, buf, len(buf)):
                    if ctypes.get_last_error() == 18:
                        break
                    raise self.error("cannot enumerate Windows volumes")
        finally:
            self.dll.FindVolumeClose(search)

    def volume_disks(self, handle):
        size = 32
        while True:
            try:
                data = self.ioctl(handle, self.GET_EXTENTS, size)
                break
            except OSError as exc:
                if getattr(exc, "winerror", None) != 234:  # ERROR_MORE_DATA
                    raise
                size *= 2
                if size > 1024 * 1024:
                    raise IOError("volume extent list is too large") from exc
        # VOLUME_DISK_EXTENTS: DWORD count, padding, DISK_EXTENT[count].
        # Each extent is DWORD disk, padding, LARGE_INTEGER offset + length.
        if len(data) < 8:
            raise IOError("truncated volume extent header")
        count = struct.unpack_from("<I", data)[0]
        if len(data) < 8 + 24 * count:
            raise IOError("truncated volume extent list")
        return {struct.unpack_from("<I", data, 8 + 24 * i)[0] for i in range(count)}

    def read(self, handle, offset, size):
        self._seek(handle, offset)
        buf = ctypes.create_string_buffer(size)
        count = ctypes.c_uint32()
        if not self.dll.ReadFile(handle, buf, size, ctypes.byref(count), None):
            raise self.error("physical disk read failed")
        if count.value != size:
            raise IOError("short physical disk read: %d of %d bytes" % (count.value, size))
        return buf.raw

    def write(self, handle, offset, data):
        self._seek(handle, offset)
        buf = ctypes.create_string_buffer(data, len(data))
        count = ctypes.c_uint32()
        if not self.dll.WriteFile(handle, buf, len(data), ctypes.byref(count), None):
            raise self.error("physical disk write failed")
        if count.value != len(data):
            raise IOError("short physical disk write: %d of %d bytes" % (count.value, len(data)))

    def _seek(self, handle, offset):
        if not self.dll.SetFilePointerEx(handle, offset, None, 0):
            raise self.error("physical disk seek failed")

    def flush(self, handle):
        if not self.dll.FlushFileBuffers(handle):
            raise self.error("physical disk flush failed")


class _Disk:
    def __init__(self, path, read_only, exclusive):
        self.api = _Win32()
        self.read_only = read_only
        self.handle = None
        self.volume_handles = []
        self.lock = threading.RLock()
        self.refs = 0
        number = physical_drive_number(path)
        try:
            # Lock/dismount filesystems before obtaining the raw disk handle.
            # Keep their handles alive until all disk writes have been flushed.
            if not read_only:
                self._lock_volumes(number)
            access = self.api.GENERIC_READ
            if not read_only:
                access |= self.api.GENERIC_WRITE
            self.handle = self.api.open(r"\\.\PhysicalDrive%d" % number, access,
                                        share=0 if exclusive else 3)
            length = self.api.ioctl(self.handle, self.api.GET_LENGTH, 8)
            geometry = self.api.ioctl(self.handle, self.api.GET_GEOMETRY, 24)
            if len(length) != 8 or len(geometry) < 24:
                raise IOError("incomplete physical disk geometry")
            self.size = struct.unpack("<q", length)[0]
            self.sector_size = struct.unpack_from("<I", geometry, 20)[0]
            if (self.size <= 0 or self.sector_size < 512
                    or self.sector_size & (self.sector_size - 1)
                    or self.size % self.sector_size):
                raise IOError("invalid physical disk size or sector size")
        except BaseException:
            try:
                self.close(flush=False)
            except OSError:
                pass  # Preserve the opening error after attempting all cleanup.
            raise

    def _lock_volumes(self, number):
        # Finish enumeration first so its search handle is closed even when
        # opening or locking one of the volumes fails below.
        for volume in list(self.api.volumes()):
            query = None
            try:
                query = self.api.open(volume, 0)
                disks = self.api.volume_disks(query)
            except OSError as exc:
                # Optical drives/empty removable drives have no disk extents.
                if getattr(exc, "winerror", None) in (1, 21, 50):
                    continue
                raise
            finally:
                if query is not None:
                    self.api.close(query)
            if number not in disks:
                continue
            handle = self.api.open(volume, self.api.GENERIC_READ | self.api.GENERIC_WRITE)
            self.volume_handles.append(handle)
            try:
                self.api.ioctl(handle, self.api.LOCK_VOLUME)
                self.api.ioctl(handle, self.api.DISMOUNT_VOLUME)
            except OSError as exc:
                raise IOError("cannot lock Windows volume %s; close applications "
                              "using the disk: %s" % (volume, exc)) from exc

    def close(self, flush=True):
        error = None
        if self.handle is not None:
            try:
                if flush and not self.read_only:
                    self.api.flush(self.handle)
            except OSError as exc:
                error = exc
            try:
                self.api.close(self.handle)
            except OSError as exc:
                error = error or exc
            self.handle = None
        for handle in reversed(self.volume_handles):
            try:
                # Closing the handle also releases FSCTL_LOCK_VOLUME.
                self.api.close(handle)
            except OSError as exc:
                error = error or exc
        self.volume_handles.clear()
        if error is not None:
            raise error


_sessions = {}
_sessions_lock = threading.RLock()


class DiskStream(io.RawIOBase):
    """Independent cursor over a shared disk; I/O uses whole host sectors."""

    def __init__(self, disk, read_only):
        super().__init__()
        self.disk = disk
        self.read_only = read_only
        self.position = 0
        disk.refs += 1

    @property
    def size(self):
        return self.disk.size

    def readable(self):
        return True

    def writable(self):
        return not self.read_only

    def seekable(self):
        return True

    def tell(self):
        self._checkClosed()
        return self.position

    def seek(self, offset, whence=os.SEEK_SET):
        self._checkClosed()
        bases = {os.SEEK_SET: 0, os.SEEK_CUR: self.position, os.SEEK_END: self.size}
        if whence not in bases or bases[whence] + offset < 0:
            raise ValueError("invalid disk seek")
        self.position = bases[whence] + offset
        return self.position

    def _range(self, count):
        sector = self.disk.sector_size
        start = self.position // sector * sector
        end = (self.position + count + sector - 1) // sector * sector
        return start, end, self.position - start

    def read(self, size=-1):
        self._checkClosed()
        size = max(0, self.size - self.position) if size is None or size < 0 else min(
            size, max(0, self.size - self.position))
        if not size:
            return b""
        start, end, offset = self._range(size)
        with self.disk.lock:
            data = self.disk.api.read(self.disk.handle, start, end - start)
        self.position += size
        return data[offset:offset + size]

    def write(self, data):
        self._checkClosed()
        if self.read_only:
            raise PermissionError("physical disk is read-only")
        data = bytes(data)
        if self.position + len(data) > self.size:
            raise ValueError("write exceeds physical disk size")
        if not data:
            return 0
        start, end, offset = self._range(len(data))
        with self.disk.lock:
            if offset or end - start != len(data):
                # Amiga blocks can be smaller than a 4K host sector.
                original = self.disk.api.read(self.disk.handle, start, end - start)
                payload = original[:offset] + data + original[offset + len(data):]
            else:
                payload = data
            self.disk.api.write(self.disk.handle, start, payload)
        self.position += len(data)
        return len(data)

    def flush(self):
        self._checkClosed()
        if not self.read_only:
            with self.disk.lock:
                self.disk.api.flush(self.disk.handle)

    def close(self):
        if self.closed:
            return
        try:
            super().close()  # flushes before marking closed, even on failure
        finally:
            with _sessions_lock:
                self.disk.refs -= 1
                if not self.disk.refs:
                    self.disk.close()


def open_disk(path, read_only=True):
    """Open a disk or borrow the current mount's handle without weakening it."""
    number = physical_drive_number(path)
    if number is None:
        raise ValueError("expected a Windows PhysicalDrive path")
    with _sessions_lock:
        disk = _sessions.get(number)
        if disk is None:
            disk = _Disk(path, read_only, exclusive=not read_only)
        elif disk.read_only and not read_only:
            raise PermissionError("physical disk session is read-only")
        return DiskStream(disk, read_only)


class DiskLock:
    """An exclusive mount session, independent of the calling thread."""

    def __init__(self, path, read_only=True):
        self.number = physical_drive_number(path)
        self.stream = None
        with _sessions_lock:
            if self.number in _sessions:
                raise IOError("cannot exclusively lock disk: already mounted")
            disk = _Disk(path, read_only, exclusive=True)
            self.stream = DiskStream(disk, read_only)
            _sessions[self.number] = disk

    def close(self):
        with _sessions_lock:
            if self.stream is not None:
                stream, self.stream = self.stream, None
                del _sessions[self.number]
                stream.close()


def open_image(path):
    """Read-only stream for format probes, including within a locked session."""
    return open_disk(path) if is_windows_disk(path) else open(path, "rb")


def image_size(path):
    if is_windows_disk(path):
        with open_disk(path) as stream:
            return stream.size
    return os.path.getsize(path)
