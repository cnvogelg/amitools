import os
import uuid

from amitools.vamos.log import log_lock

from amitools.vamos.libstructs import FileLockStruct, DateStampStruct
from .DosProtection import DosProtection
from .AmiTime import *
from .Error import *


def _struct_field(struct, path):
    field = struct.get_path(path)
    if field is None:
        raise AttributeError(f"{type(struct).__name__} has no field path {path!r}")
    return field


def _struct_addr(struct, path):
    if hasattr(struct, "s_get_addr"):
        return struct.s_get_addr(path)
    return _struct_field(struct, path).addr


def _struct_read(struct, path):
    if hasattr(struct, "r_s"):
        return struct.r_s(path)
    field = _struct_field(struct, path)
    if hasattr(field, "val"):
        return field.val
    if hasattr(field, "aptr"):
        return field.aptr
    if hasattr(field, "bptr"):
        return field.bptr
    return field.get()


def _struct_write(struct, path, value):
    if hasattr(struct, "w_s"):
        struct.w_s(path, value)
        return
    field = _struct_field(struct, path)
    if hasattr(field, "val"):
        field.val = value
    elif hasattr(field, "aptr"):
        field.aptr = value
    elif hasattr(field, "bptr"):
        field.aptr = value
    else:
        field.set(value)


class Lock:
    """represent an AmigaOS Lock in vamos"""

    def __init__(self, name, ami_path, sys_path, exclusive=False):
        self.ami_path = ami_path
        self.sys_path = sys_path
        self.name = name
        self.exclusive = exclusive
        self.mem = None
        self.b_addr = 0
        self.vol_addr = 0
        self.key = 0
        self.dirent = None
        self.struct = None

    def __repr__(self):
        addr = 0
        if self.mem is not None:
            addr = self.mem.addr
        return "Lock['%s'(ami='%s',sys='%s',key=%s,ex=%d, vol=%d)@%06x=b@%06x]" % (
            self.name,
            self.ami_path,
            self.sys_path,
            self.key,
            self.exclusive,
            self.vol_addr,
            addr,
            self.b_addr,
        )

    def __str__(self):
        addr = 0
        if self.mem is not None:
            addr = self.mem.addr
        return "Lock['%s'@%06x=b@%06x]" % (
            self.name,
            addr,
            self.b_addr,
        )

    def alloc(self, alloc, vol_addr, key):
        name = "Lock: %s" % self
        self.key = key
        self.mem = alloc.alloc_struct(FileLockStruct, label=name)
        self.struct = FileLockStruct(alloc.get_mem(), self.mem.addr)
        self.struct.key.val = key
        self.struct.volume.aptr = vol_addr
        self.b_addr = self.mem.addr >> 2
        self.vol_addr = vol_addr

    def free(self, alloc):
        alloc.free_struct(self.mem)
        self.struct = None

    # --- lock ops ---

    def _examine_file(self, fib_mem, name, sys_path, key):
        # name
        name_addr = _struct_addr(fib_mem, "fib_FileName")
        # clear 32 name bytes
        mem = fib_mem.mem
        mem.clear_block(name_addr, 32, 0)
        mem.w_cstr(name_addr, name)
        # comment
        comment_addr = _struct_addr(fib_mem, "fib_Comment")
        mem.w_cstr(comment_addr, "")
        # create the "inode" information
        _struct_write(fib_mem, "fib_DiskKey", key)
        log_lock.debug("examine key: %08x", key)
        # type
        if os.path.isdir(sys_path):
            dirEntryType = 2
        else:
            dirEntryType = -3
        _struct_write(fib_mem, "fib_DirEntryType", dirEntryType)
        _struct_write(fib_mem, "fib_EntryType", dirEntryType)
        # protection
        try:
            os_stat = os.stat(sys_path)
            mode = os_stat.st_mode
            prot = DosProtection.from_host_mode(mode)
            log_lock.debug("examine lock: '%s' mode=%03o: prot=%s", name, mode, prot)
        except OSError:
            return ERROR_OBJECT_IN_USE
        _struct_write(fib_mem, "fib_Protection", prot.mask)
        # size
        if os.path.isfile(sys_path):
            size = os.path.getsize(sys_path)
            # limit to 32bit
            if size > 0xFFFFFFFF:
                size = 0xFFFFFFFF
            _struct_write(fib_mem, "fib_Size", size)
            blocks = (size + 511) // 512
            _struct_write(fib_mem, "fib_NumBlocks", blocks)
            log_lock.debug(
                "examine lock: '%s' size=%d, blocks=%d", sys_path, size, blocks
            )
        else:
            _struct_write(fib_mem, "fib_NumBlocks", 1)
            log_lock.debug("examine lock: '%s' no file", sys_path)
        # date (use mtime here)
        date_addr = _struct_addr(fib_mem, "fib_Date")
        date = DateStampStruct(fib_mem.mem, date_addr)
        t = os.path.getmtime(sys_path)
        at = sys_to_ami_time(t)
        date.ds_Days.val = at.tday
        date.ds_Minute.val = at.tmin
        date.ds_Tick.val = at.tick
        # fill in UID/GID
        _struct_write(fib_mem, "fib_OwnerUID", 0)
        _struct_write(fib_mem, "fib_OwnerGID", 0)
        return NO_ERROR

    def examine_lock(self, fib_mem):
        return self._examine_file(fib_mem, self.name, self.sys_path, self.key)

    def examine_next(self, fib_mem):
        # start scan
        if self.dirent is None:
            # scan real dir
            if os.path.isdir(self.sys_path):
                self.dirent = os.listdir(self.sys_path)
            else:
                self.dirent = []
            # assume that key stored in given FIB is my own one
            # (otherwise no Examine() on my lock was done before..., aka broken code!)
            self._check_disk_key(fib_mem)
            index = 0
        else:
            index = _struct_read(fib_mem, "fib_DiskKey")

        if index < len(self.dirent):
            entry = self.dirent[index]
            e_path = os.path.join(self.sys_path, entry)
            return self._examine_file(fib_mem, entry, e_path, index + 1)
        else:
            self.dirent = None
            return ERROR_NO_MORE_ENTRIES

    def _check_disk_key(self, fib_mem):
        # make sure its a dir entry
        dirEntryType = _struct_read(fib_mem, "fib_DirEntryType")
        if dirEntryType != 2:
            log_lock.warning("fib type is not dir on first ExNext()!")
        # make sure fib_key is mine
        fib_key = _struct_read(fib_mem, "fib_DiskKey")
        if fib_key != self.key:
            log_lock.warning(
                "first ExNext() does not start at Examine()d lock!"
                " Broken Code!! lock_key=%08x fib_key=%08x (%s)",
                self.key,
                fib_key,
                self.name,
            )
            return False
        else:
            return True

    def find_volume_node(self, dos_list):
        if self.struct is None:
            return 0
        return self.struct.volume.aptr
