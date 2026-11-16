from amitools.vamos.handler import HandlerError
from amitools.vamos.log import log_lock

from amitools.vamos.libstructs import FileLockStruct, DateStampStruct
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
    """represent an AmigaOS Lock in vamos

    The lock is bound to the handler that created it and to an opaque
    handler lock. It never touches host paths itself; all metadata and
    directory scans go through the handler.
    """

    def __init__(
        self,
        name,
        ami_path,
        exclusive=False,
        handler=None,
        handler_lock=None,
    ):
        self.ami_path = ami_path
        self.name = name
        self.exclusive = exclusive
        self.handler = handler
        self.handler_lock = handler_lock
        self.mem = None
        self.b_addr = 0
        self.vol_addr = 0
        self.key = 0
        self.struct = None

    def __repr__(self):
        addr = 0
        if self.mem is not None:
            addr = self.mem.addr
        return "Lock['%s'(ami='%s',key=%s,ex=%d, vol=%d)@%06x=b@%06x]" % (
            self.name,
            self.ami_path,
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
        self.mem = self.struct = alloc.alloc_astruct(FileLockStruct, label=name)
        self.struct.key.val = key
        self.struct.volume.aptr = vol_addr
        self.b_addr = self.mem.addr >> 2
        self.vol_addr = vol_addr

    def free(self, alloc):
        self.struct.free()
        self.mem = None
        self.struct = None

    # --- lock ops ---

    def _fill_fib(self, fib_mem, info, name=None):
        """write a :class:`HandlerFileInfo` into a FileInfoBlock"""
        if name is None:
            name = info.name
        mem = fib_mem.mem
        # name (fib_FileName is a 108 byte field)
        name_addr = _struct_addr(fib_mem, "fib_FileName")
        mem.clear_block(name_addr, 108, 0)
        mem.w_cstr(name_addr, name)
        # comment (fib_Comment is a 80 byte field)
        comment_addr = _struct_addr(fib_mem, "fib_Comment")
        mem.clear_block(comment_addr, 80, 0)
        if info.comment:
            mem.w_cstr(comment_addr, info.comment)
        # key / "inode" information
        _struct_write(fib_mem, "fib_DiskKey", info.key)
        # type
        _struct_write(fib_mem, "fib_DirEntryType", info.entry_type)
        _struct_write(fib_mem, "fib_EntryType", info.entry_type)
        # protection
        _struct_write(fib_mem, "fib_Protection", info.protection)
        # size / blocks
        _struct_write(fib_mem, "fib_Size", info.size)
        _struct_write(fib_mem, "fib_NumBlocks", info.blocks)
        # date
        date_addr = _struct_addr(fib_mem, "fib_Date")
        date = DateStampStruct(fib_mem.mem, date_addr)
        at = sys_to_ami_time(info.date)
        date.ds_Days.val = at.tday
        date.ds_Minute.val = at.tmin
        date.ds_Tick.val = at.tick
        # owner
        _struct_write(fib_mem, "fib_OwnerUID", info.owner_uid)
        _struct_write(fib_mem, "fib_OwnerGID", info.owner_gid)
        log_lock.debug(
            "examine: '%s' type=%d prot=%03o size=%d blocks=%d key=%d",
            name,
            info.entry_type,
            info.protection,
            info.size,
            info.blocks,
            info.key,
        )

    def examine_lock(self, fib_mem):
        try:
            info = self.handler.examine_object(self.handler_lock)
        except HandlerError as e:
            return e.code
        # the DOS name of the examined object is the lock's own name; this
        # matters for the volume root, whose host basename is not the
        # volume name
        self._fill_fib(fib_mem, info, name=self.name)
        return NO_ERROR

    def examine_next(self, fib_mem):
        # fib_DiskKey holds the index of the next entry to return
        key = _struct_read(fib_mem, "fib_DiskKey")
        try:
            info = self.handler.examine_next(self.handler_lock, key)
        except HandlerError as e:
            return e.code
        self._fill_fib(fib_mem, info)
        return NO_ERROR

    def clone_for_scan(self):
        """return a fresh, unallocated lock on the same object

        Used by ExAll so its ExNext cursor is independent of the caller's
        lock. Raises HandlerError if the object can not be enumerated (e.g.
        it is not a directory).
        """
        handler_lock = self.handler.copy_dir(self.handler_lock)
        return Lock(
            self.name,
            self.ami_path,
            handler=self.handler,
            handler_lock=handler_lock,
        )

    def find_volume_node(self, dos_list):
        if self.struct is None:
            return 0
        return self.struct.volume.aptr
