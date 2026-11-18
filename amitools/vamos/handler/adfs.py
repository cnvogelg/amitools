"""ADFS handler: an AmigaDOS file system on a real block device.

The handler wraps :mod:`amitools.fs` so an OFS/FFS volume (a DD/HD floppy
image, a hardfile or one RDB partition) is usable through the handler API.
It is *block* based: the source of blocks is an
:class:`amitools.fs.blkdev.BlockDevice`, so the handler never touches the
host file system.

All paths it receives are volume-relative and use AmigaDOS ``/`` separators.
Resolution is case-insensitive and collapses AmigaDOS parent steps.
"""

from amitools.fs import DosType
from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.FSError import (
    DELETE_NOT_ALLOWED,
    FILE_NOT_FOUND,
    INVALID_COMMENT,
    INVALID_FILE_NAME,
    INVALID_PARENT_DIRECTORY,
    INVALID_VOLUME_NAME,
    NAME_ALREADY_EXISTS,
    NO_FREE_BLOCKS,
)
from amitools.fs.FSString import FSString
from amitools.fs.TimeStamp import TimeStamp, amiga_epoch
from amitools.fs.blkdev.BlkDevFactory import BlkDevFactory
from amitools.vamos.log import log_handler
from amitools.vamos.path.amipath import collapse_parent_steps

from .base import (
    ERROR_BAD_NUMBER,
    ERROR_DIRECTORY_NOT_EMPTY,
    ERROR_DISK_FULL,
    ERROR_INVALID_COMPONENT_NAME,
    ERROR_NO_MORE_ENTRIES,
    ERROR_NOT_IMPLEMENTED,
    ERROR_OBJECT_EXISTS,
    ERROR_OBJECT_NOT_FOUND,
    ERROR_OBJECT_WRONG_TYPE,
    ERROR_SEEK_ERROR,
    ERROR_WRITE_PROTECTED,
    MODE_NEWFILE,
    MODE_OLDFILE,
    MODE_READWRITE,
    FileSystemHandler,
    HandlerError,
    HandlerFile,
    HandlerFileInfo,
    HandlerInfoData,
    HandlerLock,
)

# map an ``amitools.fs`` error code to a DOS-compatible one
_ADFS_ERROR_MAP = {
    FILE_NOT_FOUND: ERROR_OBJECT_NOT_FOUND,
    INVALID_PARENT_DIRECTORY: ERROR_OBJECT_NOT_FOUND,
    NAME_ALREADY_EXISTS: ERROR_OBJECT_EXISTS,
    NO_FREE_BLOCKS: ERROR_DISK_FULL,
    INVALID_FILE_NAME: ERROR_INVALID_COMPONENT_NAME,
    INVALID_VOLUME_NAME: ERROR_INVALID_COMPONENT_NAME,
    DELETE_NOT_ALLOWED: ERROR_DIRECTORY_NOT_EMPTY,
    INVALID_COMMENT: ERROR_BAD_NUMBER,
}


def _adfs_error(code):
    """translate an ``amitools.fs`` error code to a DOS error code"""
    return _ADFS_ERROR_MAP.get(code, ERROR_NOT_IMPLEMENTED)


class AdfsLock(HandlerLock):
    """lock on an object in an ADFS volume"""

    def __init__(self, node, rel_path):
        # the block number identifies the object within the volume
        super().__init__(key=node.block.blk_num)
        self.node = node
        self.rel_path = rel_path
        self._entries = None

    def get_entries(self):
        return self._entries

    def set_entries(self, entries):
        self._entries = entries

    def reset_entries(self):
        self._entries = None


class AdfsFile(HandlerFile):
    """open file in an ADFS volume

    ADFS keeps a whole file's bytes in memory, so the handle buffers them in
    a ``bytearray`` and patches it on write. The data is written back to the
    volume when the handle is flushed or closed, if it is dirty or a new file
    still has to be created.
    """

    def __init__(self, node, data, rel_path, mode, need_create=False):
        super().__init__(key=rel_path.lower())
        self.node = node
        self.data = bytearray(data)
        self.rel_path = rel_path
        self.mode = mode
        self.need_create = need_create
        self.dirty = False
        self.pos = 0
        # ``end`` is overridden, but keep ``fobj`` pointing at the buffer
        # owner so code that only knows the base handler does not trip
        self.fobj = self

    def read(self, size=-1):
        data = self.data
        if size is None or size < 0:
            chunk = bytes(data[self.pos :])
        else:
            chunk = bytes(data[self.pos : self.pos + size])
        self.pos += len(chunk)
        return chunk

    def write(self, data):
        buf = self.data
        if self.pos > len(buf):
            buf.extend(b"\x00" * (self.pos - len(buf)))
        end = self.pos + len(data)
        buf[self.pos : end] = data
        self.pos = end
        return len(data)

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        if whence == 0:
            new_pos = offset
        elif whence == 1:
            new_pos = self.pos + offset
        elif whence == 2:
            new_pos = len(self.data) + offset
        else:
            raise ValueError("invalid whence: %r" % whence)
        if new_pos < 0:
            raise OSError("negative seek position")
        self.pos = new_pos
        return new_pos

    def truncate(self, size):
        buf = self.data
        if size < len(buf):
            del buf[size:]
        else:
            buf.extend(b"\x00" * (size - len(buf)))
        return size

    def get_size(self):
        return len(self.data)

    def flush(self):
        pass

    def close(self):
        pass

    def isatty(self):
        return False

    def fileno(self):
        raise OSError("ADFS: has no file descriptor")


class AdfsHandler(FileSystemHandler):
    """file system handler backed by an :class:`ADFSVolume`"""

    def __init__(self, name, blkdev, read_only=False):
        super().__init__(name)
        self.blkdev = blkdev
        self.read_only = bool(read_only or getattr(blkdev, "read_only", False))
        self.volume = ADFSVolume(blkdev)
        try:
            self.volume.open()
        except Exception as e:
            raise HandlerError(ERROR_NOT_IMPLEMENTED, str(e)) from None

    def shutdown(self):
        if self.volume is not None:
            self.volume.close()
            self.volume = None
        if self.blkdev is not None:
            self.blkdev.close()
            self.blkdev = None

    # ----- helpers -----

    def _rel(self, ami_path):
        """collapse AmigaDOS parent steps in a volume-relative path"""
        rel = str(ami_path)
        if rel in ("", ":"):
            return ""
        dirs = collapse_parent_steps(rel.split("/"))
        if dirs is None:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        return "/".join(dirs)

    def _make_lock(self, node, rel_path):
        lock = AdfsLock(node, rel_path)
        lock.handler = self
        return lock

    def _make_file(self, node, data, rel_path, mode, need_create=False):
        fh = AdfsFile(node, data, rel_path, mode, need_create)
        fh.handler = self
        return fh

    def _check_writable(self):
        if self.read_only:
            raise HandlerError(ERROR_WRITE_PROTECTED)

    def _node(self, ami_path):
        """resolve an existing node, or raise ``ERROR_OBJECT_NOT_FOUND``"""
        rel = self._rel(ami_path)
        try:
            node = self.volume.get_path_name(FSString(rel))
        except Exception as e:
            raise HandlerError(_adfs_error(getattr(e, "code", None))) from None
        if node is None:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        return node, rel

    def _file_node(self, ami_path):
        """resolve an existing file node, or raise ``ERROR_OBJECT_NOT_FOUND``"""
        rel = self._rel(ami_path)
        try:
            node = self.volume.get_file_path_name(FSString(rel))
        except Exception as e:
            raise HandlerError(_adfs_error(getattr(e, "code", None))) from None
        if node is None:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        return node, rel

    def _existing_node(self, rel):
        try:
            return self.volume.get_path_name(FSString(rel))
        except Exception as e:
            raise HandlerError(_adfs_error(getattr(e, "code", None))) from None

    def _open_existing(self, node, rel, mode):
        try:
            data = node.get_file_data()
        except Exception as e:
            raise HandlerError(_adfs_error(getattr(e, "code", None))) from None
        if data is None:
            data = b""
        return self._make_file(node, data, rel, mode)

    def _file_info(self, node, key):
        if node.is_dir():
            entry_type = HandlerFileInfo.DIR
            size = 0
        else:
            entry_type = HandlerFileInfo.FILE
            size = node.get_size()
        mi = node.meta_info
        protect = mi.get_protect()
        if protect is None:
            protect = 0
        date = 0
        mod_ts = mi.get_mod_ts()
        if mod_ts is not None:
            date = mod_ts.get_secs() + amiga_epoch
        blocks = sum(node.get_block_usage(all=True))
        return HandlerFileInfo(
            name=node.name.get_unicode_name(),
            entry_type=entry_type,
            protection=protect,
            size=size,
            blocks=blocks,
            date=date,
            key=key,
            comment=mi.get_comment_unicode_str(),
        )

    def _info_data(self):
        if self.read_only:
            disk_state = HandlerInfoData.DISK_STATE_WRITE_PROTECTED
        else:
            disk_state = HandlerInfoData.DISK_STATE_VALIDATED
        return HandlerInfoData(
            num_blocks=self.volume.get_total_blocks(),
            num_blocks_used=self.volume.get_used_blocks(),
            bytes_per_block=self.blkdev.block_bytes,
            disk_state=disk_state,
        )

    def _write_back(self, fh):
        """materialize a dirty or new file onto the volume"""
        if not (fh.dirty or fh.need_create):
            return
        self._check_writable()
        self._store_file(fh.rel_path, bytes(fh.data))
        fh.dirty = False
        fh.need_create = False

    def _store_file(self, rel, data):
        # replace an existing file, then write the new content
        node = self._existing_node(rel)
        if node is not None:
            if node.is_dir():
                raise HandlerError(ERROR_OBJECT_EXISTS)
            try:
                node.delete()
            except Exception as e:
                raise HandlerError(_adfs_error(getattr(e, "code", None))) from None
        try:
            self.volume.write_file(data, FSString(rel))
        except Exception as e:
            raise HandlerError(_adfs_error(getattr(e, "code", None))) from None

    # ----- locks -----

    def locate_object(self, ami_path, exclusive=False):
        node, rel = self._node(ami_path)
        log_handler.info("locate_object: '%s' -> %s", ami_path, node)
        return self._make_lock(node, rel)

    def free_lock(self, lock):
        pass

    def copy_dir(self, lock):
        # ACTION_COPY_DIR replicates any lock (it is LOCATE_OBJECT with an
        # empty name), so it must not require a directory here
        return self._make_lock(lock.node, lock.rel_path)

    def parent(self, lock):
        parent = lock.node.parent
        if parent is None:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        rel = lock.rel_path.rsplit("/", 1)[0] if "/" in lock.rel_path else ""
        return self._make_lock(parent, rel)

    def same_lock(self, a, b):
        return a.handler is b.handler and a.key == b.key

    def examine_object(self, lock):
        return self._file_info(lock.node, 0)

    def examine_next(self, lock, key):
        if not lock.node.is_dir():
            raise HandlerError(ERROR_OBJECT_WRONG_TYPE)
        entries = lock.get_entries()
        if entries is None:
            entries = lock.node.get_entries_sorted_by_name()
            lock.set_entries(entries)
        if key < len(entries):
            return self._file_info(entries[key], key + 1)
        lock.reset_entries()
        raise HandlerError(ERROR_NO_MORE_ENTRIES)

    def info(self, lock):
        return self._info_data()

    def disk_info(self, lock):
        return self._info_data()

    def fh_from_lock(self, lock, mode=MODE_OLDFILE):
        if lock.node.is_dir():
            raise HandlerError(ERROR_OBJECT_WRONG_TYPE)
        return self._open_existing(lock.node, lock.rel_path, mode)

    def parent_fh(self, fh):
        parent = fh.node.parent
        if parent is None:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        rel = fh.rel_path.rsplit("/", 1)[0] if "/" in fh.rel_path else ""
        return self._make_lock(parent, rel)

    def copy_dir_fh(self, fh):
        # ACTION_COPY_DIR_FH locks the file opened by the handle
        return self._make_lock(fh.node, fh.rel_path)

    # ----- files -----

    def find_input(self, ami_path):
        node, rel = self._file_node(ami_path)
        return self._open_existing(node, rel, MODE_OLDFILE)

    def find_output(self, ami_path, mode=MODE_NEWFILE):
        self._check_writable()
        rel = self._rel(ami_path)
        existing = self._existing_node(rel)
        if existing is not None and existing.is_dir():
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        if mode == MODE_OLDFILE:
            if existing is None:
                raise HandlerError(ERROR_OBJECT_NOT_FOUND)
            return self._open_existing(existing, rel, mode)
        if existing is not None:
            need_create = mode == MODE_NEWFILE
            if need_create:
                return self._make_file(existing, b"", rel, mode, need_create=True)
            return self._open_existing(existing, rel, mode)
        # a new file: the parent must exist
        try:
            parent, name = self.volume.get_create_path_name(FSString(rel))
        except Exception as e:
            raise HandlerError(_adfs_error(getattr(e, "code", None))) from None
        if parent is None or name is None:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        return self._make_file(None, b"", rel, mode, need_create=True)

    def find_update(self, ami_path):
        return self.find_output(ami_path, MODE_READWRITE)

    def read(self, fh, size):
        return fh.read(size)

    def write(self, fh, data):
        self._check_writable()
        count = fh.write(data)
        fh.dirty = True
        return count

    def seek(self, fh, offset, whence):
        try:
            new_pos = fh.seek(offset, whence)
        except (OSError, ValueError):
            raise HandlerError(ERROR_SEEK_ERROR)
        file_size = len(fh.data)
        if new_pos > file_size:
            fh.pos = file_size
            return -2
        return new_pos

    def set_file_size(self, fh, size, mode):
        self._check_writable()
        if mode == -1:  # OFFSET_BEGINNING
            new_size = size
        elif mode == 0:  # OFFSET_CURRENT
            new_size = fh.pos + size
        elif mode == 1:  # OFFSET_END
            new_size = len(fh.data) + size
        else:
            raise HandlerError(ERROR_BAD_NUMBER)
        if new_size < 0:
            raise HandlerError(ERROR_OBJECT_WRONG_TYPE)
        fh.truncate(new_size)
        fh.dirty = True
        return new_size

    def flush(self, fh):
        self._write_back(fh)

    def end(self, fh):
        self._write_back(fh)

    # ----- names -----

    def delete_object(self, ami_path):
        self._check_writable()
        rel = self._rel(ami_path)
        try:
            self.volume.delete(FSString(rel))
        except Exception as e:
            raise HandlerError(_adfs_error(getattr(e, "code", None))) from None

    def rename_object(self, old_path, new_path):
        self._check_writable()
        old_rel = self._rel(old_path)
        new_rel = self._rel(new_path)
        try:
            self.volume.rename(FSString(old_rel), FSString(new_rel))
        except Exception as e:
            raise HandlerError(_adfs_error(getattr(e, "code", None))) from None

    def set_protect(self, ami_path, mask):
        self._check_writable()
        node, _ = self._node(ami_path)
        try:
            node.change_protect(mask)
        except Exception as e:
            raise HandlerError(_adfs_error(getattr(e, "code", None))) from None

    def set_comment(self, ami_path, comment):
        self._check_writable()
        node, _ = self._node(ami_path)
        try:
            node.change_comment(FSString(comment))
        except Exception as e:
            raise HandlerError(_adfs_error(getattr(e, "code", None))) from None

    def set_date(self, ami_path, date):
        self._check_writable()
        node, _ = self._node(ami_path)
        ts = TimeStamp()
        ts.from_secs(date)
        try:
            node.change_mod_ts(ts)
        except Exception as e:
            raise HandlerError(_adfs_error(getattr(e, "code", None))) from None

    def create_dir(self, ami_path):
        self._check_writable()
        rel = self._rel(ami_path)
        try:
            self.volume.create_dir(FSString(rel))
        except Exception as e:
            raise HandlerError(_adfs_error(getattr(e, "code", None))) from None

    # ----- volume maintenance -----

    def rename_disk(self, new_name):
        self._check_writable()
        try:
            self.volume.relabel(FSString(new_name))
        except Exception as e:
            raise HandlerError(_adfs_error(getattr(e, "code", None))) from None
        self.name = new_name

    def format(self, vol_name, dos_type):
        self._check_writable()
        if not dos_type:
            dos_type = DosType.DOS0
        try:
            self.volume.create(FSString(vol_name), dos_type=dos_type)
        except Exception as e:
            raise HandlerError(_adfs_error(getattr(e, "code", None))) from None
        self.name = vol_name

    def write_protect(self, enable):
        # a write protected ADFS volume refuses all write access
        super().write_protect(enable)
        self.read_only = bool(enable)

    # ----- objects / metadata -----

    def examine_fh(self, fh):
        return self._file_info(fh.node, 0)


def open_adfs_blkdev(image, *, img=None, part=None, read_only=False):
    """open a block device for an ADFS image file

    ``img`` overrides the type detection; the umbrella value ``xdf`` means
    "raw image" and is passed as no type so the factory auto-detects from the
    contents (``RDSK``) first, then the file extension/size (``.adf`` /
    ``.hdf`` / ``.rdb``). For an RDB image ``part`` selects the partition by
    number or drive name.
    """
    options = {}
    if img is not None and img != "xdf":
        options["type"] = img
    if part is not None:
        options["part"] = part
    return BlkDevFactory().open(image, read_only=read_only, options=options)
