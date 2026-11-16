"""Host file system handler: a handler backed by a host directory tree.

The handler is bound to one volume root (``root_path``). All paths it
receives are relative to that root and use AmigaDOS ``/`` separators. The
host file system is accessed through :class:`HostFileSystem` so all host
calls stay behind one boundary.
"""

import errno
import os
import stat

from amitools.vamos.log import log_handler
from amitools.vamos.path.syspath import HostFileSystem, follow_path_no_case
from amitools.vamos.path.amipath import collapse_parent_steps

from .base import (
    ERROR_BAD_NUMBER,
    ERROR_DIRECTORY_NOT_EMPTY,
    ERROR_NO_MORE_ENTRIES,
    ERROR_OBJECT_EXISTS,
    ERROR_OBJECT_IN_USE,
    ERROR_OBJECT_NOT_FOUND,
    ERROR_OBJECT_WRONG_TYPE,
    ERROR_READ_PROTECTED,
    ERROR_SEEK_ERROR,
    ERROR_WRITE_PROTECTED,
    Handler,
    HandlerError,
    HandlerFile,
    HandlerFileInfo,
    HandlerInfoData,
    HandlerLock,
    MODE_NEWFILE,
    MODE_OLDFILE,
    MODE_READWRITE,
)
from .protection import DosProtection


class HostFileSysLock(HandlerLock):
    """lock on an object in a host directory tree"""

    def __init__(self, sys_path, rel_path):
        super().__init__(key=rel_path.lower())
        self.sys_path = sys_path
        self.rel_path = rel_path
        self._entries = None

    def get_entries(self):
        return self._entries

    def set_entries(self, entries):
        self._entries = entries

    def reset_entries(self):
        self._entries = None


class HostFileSysFile(HandlerFile):
    """open file in a host directory tree"""

    def __init__(self, fobj, sys_path, rel_path):
        super().__init__(key=rel_path.lower())
        self.fobj = fobj
        self.sys_path = sys_path
        self.rel_path = rel_path


class HostFileSysHandler(Handler):
    """file system handler backed by a host directory tree"""

    def __init__(self, name, root_path, file_system=None):
        super().__init__(name)
        self.root_path = root_path
        self.fs = file_system or HostFileSystem()

    # ----- helpers -----

    def _sys_path(self, rel_path, fast=False):
        """map a volume-relative Amiga path to a host path"""
        rel = str(rel_path)
        if rel in ("", ":"):
            return self.root_path
        dirs = collapse_parent_steps(rel.split("/"))
        if dirs is None:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        return follow_path_no_case(self.fs, self.root_path, dirs, fast)

    def _rel_path(self, sys_path):
        """canonical volume-relative Amiga path of a host path"""
        rel = os.path.relpath(sys_path, self.root_path)
        if rel == os.curdir:
            return ""
        return rel.replace(os.sep, "/")

    def _make_lock(self, sys_path):
        lock = HostFileSysLock(sys_path, self._rel_path(sys_path))
        lock.handler = self
        return lock

    def _make_file(self, fobj, sys_path):
        fh = HostFileSysFile(fobj, sys_path, self._rel_path(sys_path))
        fh.handler = self
        return fh

    def _file_info(self, sys_path, name, key):
        try:
            st = self.fs.stat(sys_path)
        except OSError:
            raise HandlerError(ERROR_OBJECT_IN_USE)
        if stat.S_ISDIR(st.st_mode):
            entry_type = HandlerFileInfo.DIR
            size = 0
            blocks = 1
        else:
            entry_type = HandlerFileInfo.FILE
            size = st.st_size
            # limit to 32bit
            if size > 0xFFFFFFFF:
                size = 0xFFFFFFFF
            blocks = (size + 511) // 512
        prot = DosProtection.from_host_mode(st.st_mode)
        return HandlerFileInfo(
            name=name,
            entry_type=entry_type,
            protection=prot.mask,
            size=size,
            blocks=blocks,
            date=st.st_mtime,
            key=key,
        )

    def _info_data(self, sys_path):
        usage = self.fs.disk_usage(sys_path)
        if usage.read_only:
            disk_state = HandlerInfoData.DISK_STATE_WRITE_PROTECTED
        else:
            disk_state = HandlerInfoData.DISK_STATE_VALIDATED
        return HandlerInfoData(
            num_blocks=usage.total,
            num_blocks_used=usage.used,
            bytes_per_block=usage.block_size,
            disk_state=disk_state,
        )

    # ----- locks -----

    def locate_object(self, ami_path, exclusive=False):
        sys_path = self._sys_path(ami_path)
        if not self.fs.exists(sys_path):
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        log_handler.info("locate_object: '%s' -> '%s'", ami_path, sys_path)
        return self._make_lock(sys_path)

    def free_lock(self, lock):
        pass

    def copy_dir(self, lock):
        if not self.fs.is_dir(lock.sys_path):
            raise HandlerError(ERROR_OBJECT_WRONG_TYPE)
        return self._make_lock(lock.sys_path)

    def parent(self, lock):
        rel = lock.rel_path
        names = rel.split("/") if rel else []
        # the volume root has no parent
        if not names:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        parent_rel = "/".join(names[:-1])
        parent_sys_path = self._sys_path(parent_rel)
        return self._make_lock(parent_sys_path)

    def same_lock(self, a, b):
        return a.handler is b.handler and a.key == b.key

    def examine_object(self, lock):
        name = os.path.basename(lock.sys_path)
        if not name:
            name = self.name
        return self._file_info(lock.sys_path, name, 0)

    def examine_next(self, lock, key):
        entries = lock.get_entries()
        if entries is None:
            if not self.fs.is_dir(lock.sys_path):
                raise HandlerError(ERROR_OBJECT_WRONG_TYPE)
            try:
                entries = self.fs.list_dir(lock.sys_path)
            except OSError:
                raise HandlerError(ERROR_READ_PROTECTED)
            lock.set_entries(entries)
        if key < len(entries):
            name = entries[key]
            sys_path = self.fs.join_path(lock.sys_path, name)
            return self._file_info(sys_path, name, key + 1)
        lock.reset_entries()
        raise HandlerError(ERROR_NO_MORE_ENTRIES)

    def info(self, lock):
        return self._info_data(lock.sys_path)

    def disk_info(self, lock):
        return self._info_data(lock.sys_path)

    def fh_from_lock(self, lock, mode=MODE_OLDFILE):
        if self.fs.is_dir(lock.sys_path):
            raise HandlerError(ERROR_OBJECT_WRONG_TYPE)
        py_mode = "rb" if mode == MODE_OLDFILE else "rb+"
        try:
            fobj = self.fs.open(lock.sys_path, py_mode)
        except OSError:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        return self._make_file(fobj, lock.sys_path)

    def parent_fh(self, fh):
        return self.parent(fh)

    def copy_dir_fh(self, fh):
        return self.copy_dir(fh)

    # ----- files -----

    def find_input(self, ami_path):
        sys_path = self._sys_path(ami_path)
        if not self.fs.exists(sys_path):
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        try:
            fobj = self.fs.open(sys_path, "rb")
        except OSError:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        return self._make_file(fobj, sys_path)

    def find_output(self, ami_path, mode=MODE_NEWFILE):
        sys_path = self._sys_path(ami_path)
        exists = self.fs.exists(sys_path)
        if mode == MODE_NEWFILE:
            py_mode = "wb+"
        elif mode == MODE_READWRITE:
            if exists:
                py_mode = "rb+" if self.fs.access(sys_path, os.W_OK) else "rb"
            else:
                py_mode = "wb+"
        else:  # MODE_OLDFILE
            if not exists:
                raise HandlerError(ERROR_OBJECT_NOT_FOUND)
            py_mode = "rb+" if self.fs.access(sys_path, os.W_OK) else "rb"
        try:
            fobj = self.fs.open(sys_path, py_mode)
        except OSError:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        return self._make_file(fobj, sys_path)

    def find_update(self, ami_path):
        return self.find_output(ami_path, MODE_READWRITE)

    def read(self, fh, size):
        try:
            return fh.fobj.read(size)
        except OSError:
            raise HandlerError(ERROR_READ_PROTECTED)

    def write(self, fh, data):
        try:
            fh.fobj.write(data)
        except OSError:
            raise HandlerError(ERROR_WRITE_PROTECTED)
        return len(data)

    def seek(self, fh, offset, whence):
        try:
            return fh.fobj.seek(offset, whence)
        except OSError:
            raise HandlerError(ERROR_SEEK_ERROR)

    def set_file_size(self, fh, size, mode):
        fobj = fh.fobj
        try:
            if mode == -1:  # OFFSET_BEGINNING
                new_size = size
            elif mode == 0:  # OFFSET_CURRENT
                new_size = fobj.tell() + size
            elif mode == 1:  # OFFSET_END
                fobj.seek(0, 2)
                new_size = fobj.tell() + size
            else:
                raise HandlerError(ERROR_BAD_NUMBER)
            if new_size < 0:
                raise HandlerError(ERROR_OBJECT_WRONG_TYPE)
            fobj.truncate(new_size)
            return new_size
        except OSError:
            raise HandlerError(ERROR_OBJECT_WRONG_TYPE)

    def flush(self, fh):
        try:
            fh.fobj.flush()
        except OSError:
            raise HandlerError(ERROR_WRITE_PROTECTED)

    def end(self, fh):
        try:
            fh.fobj.close()
        except OSError:
            pass

    # ----- names -----

    def delete_object(self, ami_path):
        sys_path = self._sys_path(ami_path)
        if not self.fs.exists(sys_path):
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        try:
            if self.fs.is_dir(sys_path):
                self.fs.rmdir(sys_path)
            else:
                self.fs.remove(sys_path)
        except OSError as e:
            if e.errno == errno.ENOTEMPTY:
                raise HandlerError(ERROR_DIRECTORY_NOT_EMPTY)
            raise HandlerError(ERROR_OBJECT_IN_USE)

    def rename_object(self, old_path, new_path):
        old_sys_path = self._sys_path(old_path)
        new_sys_path = self._sys_path(new_path)
        if not self.fs.exists(old_sys_path):
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        try:
            self.fs.rename(old_sys_path, new_sys_path)
        except OSError:
            raise HandlerError(ERROR_OBJECT_IN_USE)

    def set_protect(self, ami_path, mask):
        sys_path = self._sys_path(ami_path)
        if not self.fs.exists(sys_path):
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        prot = DosProtection(mask)
        posix_mask = prot.to_host_mode() & ~self.fs.get_umask()
        log_handler.info(
            "set_protect: '%s' %s -> posix_mask=%03o",
            ami_path,
            prot,
            posix_mask,
        )
        try:
            self.fs.chmod(sys_path, posix_mask)
        except OSError:
            raise HandlerError(ERROR_OBJECT_WRONG_TYPE)

    def set_comment(self, ami_path, comment):
        # the typical host file system does not store Amiga comments
        log_handler.info("set_comment: '%s' ignored", ami_path)

    def set_date(self, ami_path, date):
        sys_path = self._sys_path(ami_path)
        if not self.fs.exists(sys_path):
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        self.fs.utime(sys_path, (date, date))

    def create_dir(self, ami_path):
        sys_path = self._sys_path(ami_path)
        try:
            self.fs.mkdir(sys_path)
        except OSError:
            raise HandlerError(ERROR_OBJECT_EXISTS)
