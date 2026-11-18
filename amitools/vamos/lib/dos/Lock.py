from amitools.vamos.astructs import CSTR, LONG
from amitools.vamos.handler import HandlerError, MODE_OLDFILE
from amitools.vamos.log import log_lock, log_dos
from amitools.vamos.machine import Code
from amitools.vamos.machine.regs import REG_A0, REG_A1, REG_A2, REG_D0
from amitools.vamos.error import UnsupportedFeatureError

from amitools.vamos.libstructs import (
    FileLockStruct,
    DateStampStruct,
    FileInfoBlockStruct,
    InfoDataStruct,
    ExAllControlStruct,
    ExAllDataStruct,
)
from .AmiTime import *
from .Error import *
from .PatternMatch import Pattern, pattern_match


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


def fill_fib(fib_mem, info, name=None):
    """write a :class:`HandlerFileInfo` into a FileInfoBlock

    Shared by ``Lock.examine_lock``/``examine_next`` and
    ``DosLibrary.ExamineFH`` (ACTION_EXAMINE_FH).
    """
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

    def examine_lock(self, fib_mem):
        try:
            info = self.handler.examine_object(self.handler_lock)
        except HandlerError as e:
            return e.code
        # the DOS name of the examined object is the lock's own name; this
        # matters for the volume root, whose host basename is not the
        # volume name
        fill_fib(fib_mem, info, name=self.name)
        return NO_ERROR

    def examine_next(self, fib_mem):
        # fib_DiskKey holds the index of the next entry to return
        key = _struct_read(fib_mem, "fib_DiskKey")
        try:
            info = self.handler.examine_next(self.handler_lock, key)
        except HandlerError as e:
            return e.code
        fill_fib(fib_mem, info)
        return NO_ERROR

    def clone_for_scan(self):
        """return a fresh, unallocated lock on the same object

        Used by ExAll so its ExNext cursor is independent of the caller's
        lock. Raises HandlerError if the object can not be enumerated (e.g.
        it is not a directory).
        """
        # ACTION_COPY_DIR replicates any object, so the "must be a directory"
        # check that used to live there is done explicitly here
        info = self.handler.examine_object(self.handler_lock)
        if not info.is_dir:
            raise HandlerError(ERROR_OBJECT_WRONG_TYPE)
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


# ----- fd functions (RKRM AmigaDOS 3, "Locks" and "Examining") -----


def lock(dos, ctx, name, mode):
    if mode == 0xFFFFFFFF:
        lock_exclusive = True
    elif mode == 0xFFFFFFFE:
        lock_exclusive = False
    else:
        raise UnsupportedFeatureError("Lock: mode=%x" % mode)

    cur_dir = dos.get_current_dir(ctx)
    home_dir = dos.get_home_dir(ctx)
    l = dos.lock_mgr.create_lock(cur_dir, name, lock_exclusive, home_dir=home_dir)
    log_dos.info(
        "Lock: (curdir=%s, homedir=%s) '%s' exc=%s -> %s",
        cur_dir,
        home_dir,
        name,
        lock_exclusive,
        l,
    )
    if l is None:
        dos.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
        return 0
    return l.b_addr


def unlock(dos, ctx, lock_b_addr):
    if lock_b_addr == 0:
        log_dos.info("UnLock: NULL")
    else:
        l = dos.lock_mgr.get_by_b_addr(lock_b_addr)
        log_dos.info("UnLock: %s", l)
        dos.lock_mgr.release_lock(l)


def dup_lock(dos, ctx, lock_b_addr):
    l = dos.lock_mgr.get_by_b_addr(lock_b_addr)
    dup = dos.lock_mgr.dup_lock(l)
    log_dos.info("DupLock: %s -> %s", l, dup)
    if dup is None:
        dos.setioerr(ctx, ERROR_INVALID_LOCK)
        return 0
    dos.setioerr(ctx, NO_ERROR)
    return dup.b_addr


def same_lock(dos, ctx, lock1_b_addr, lock2_b_addr):
    lock1 = dos.lock_mgr.get_by_b_addr(lock1_b_addr)
    lock2 = dos.lock_mgr.get_by_b_addr(lock2_b_addr)
    if lock1 is None or lock2 is None:
        return DOSFALSE
    if lock1 is lock2:
        return DOSTRUE
    # two locks on the same handler are compared by the handler; locks
    # from different handlers are never the same object
    if (
        lock1.handler is not None
        and lock1.handler is lock2.handler
        and lock1.handler_lock is not None
        and lock2.handler_lock is not None
    ):
        same = lock1.handler.same_lock(lock1.handler_lock, lock2.handler_lock)
        return DOSTRUE if same else DOSFALSE
    if lock1.handler is None and lock2.handler is None:
        return DOSTRUE if lock1.key == lock2.key else DOSFALSE
    return DOSFALSE


def open_from_lock(dos, ctx, lock_b_addr):
    l = dos.lock_mgr.get_by_b_addr(lock_b_addr)
    if l is None:
        dos.setioerr(ctx, ERROR_INVALID_LOCK)
        return 0
    try:
        fh = dos.file_mgr.open_from_lock(l, MODE_OLDFILE)
    except HandlerError as e:
        dos.setioerr(ctx, e.code)
        return 0
    # the handle absorbs the lock
    dos.lock_mgr.release_lock(l)
    log_dos.info("OpenFromLock: %s -> %s", l, fh)
    dos.setioerr(ctx, NO_ERROR)
    return fh.b_addr


def dup_lock_from_fh(dos, ctx, fh_b_addr):
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr)
    if fh is None or fh.handler is None or fh.handler_file is None:
        dos.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
        return 0
    try:
        handler_lock = fh.handler.copy_dir_fh(fh.handler_file)
    except HandlerError as e:
        dos.setioerr(ctx, e.code)
        return 0
    l = dos.lock_mgr.register_handler_lock(
        fh.handler, handler_lock, fh.ami_path, name=fh.name
    )
    log_dos.info("DupLockFromFH: %s -> %s", fh, l)
    dos.setioerr(ctx, NO_ERROR)
    return l.b_addr


def parent_of_fh(dos, ctx, fh_b_addr):
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr)
    if fh is None or fh.handler is None or fh.handler_file is None:
        dos.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
        return 0
    try:
        handler_lock = fh.handler.parent_fh(fh.handler_file)
    except HandlerError as e:
        dos.setioerr(ctx, e.code)
        return 0
    ami_parent_path = dos.path_mgr.ami_abs_parent_path(fh.ami_path)
    name = dos.path_mgr.ami_name_of_path(None, ami_parent_path)
    l = dos.lock_mgr.register_handler_lock(
        fh.handler, handler_lock, ami_parent_path, name=name
    )
    log_dos.info("ParentOfFH: %s -> %s", fh, l)
    dos.setioerr(ctx, NO_ERROR)
    return l.b_addr


def examine(dos, ctx, lock_b_addr, fib_ptr):
    l = dos.lock_mgr.get_by_b_addr(lock_b_addr)
    fib = FileInfoBlockStruct(ctx.mem, fib_ptr)
    err = l.examine_lock(fib)
    name = ctx.mem.r_cstr(fib.fib_FileName.addr)
    log_dos.info("Examine: %s fib=%06x(%s) -> %s", l, fib_ptr, name, err)
    dos.setioerr(ctx, err)
    if err == NO_ERROR:
        return DOSTRUE
    return DOSFALSE


def examine_fh(dos, ctx, fh_b_addr, fib_ptr):
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr, False)
    fib = FileInfoBlockStruct(ctx.mem, fib_ptr)
    # handler-backed: ACTION_EXAMINE_FH examines the object the handle
    # points at directly
    if fh.handler is not None and fh.handler_file is not None:
        try:
            info = fh.handler.examine_fh(fh.handler_file)
        except HandlerError as e:
            dos.setioerr(ctx, e.code)
            return DOSFALSE
        fill_fib(fib, info, name=fh.name)
        log_dos.info("ExamineFH: %s fib=%06x -> ok", fh, fib_ptr)
        dos.setioerr(ctx, 0)
        return DOSTRUE
    # handler-less fallback: examine via a temporary lock
    l = dos.lock_mgr.create_lock(dos.get_current_dir(ctx), fh.ami_path, False)
    log_dos.info(
        "Lock: (%s) '%s' exc=%s -> %s",
        dos.get_current_dir(ctx),
        fh.ami_path,
        False,
        l,
    )
    if l is None:
        dos.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
        return DOSFALSE

    err = l.examine_lock(fib)
    name = ctx.mem.r_cstr(fib.fib_FileName.addr)
    log_dos.info("ExamineFH: %s fib=%06x(%s) -> %s", fh, fib_ptr, name, err)
    dos.setioerr(ctx, err)

    log_dos.info("UnLock: %s", l)
    dos.lock_mgr.release_lock(l)
    if err == NO_ERROR:
        return DOSTRUE
    return DOSFALSE


def info(dos, ctx, lock_b_addr, info_ptr):
    l = dos.lock_mgr.get_by_b_addr(lock_b_addr)
    info_data = InfoDataStruct(ctx.mem, info_ptr)
    if l is None:
        dos.setioerr(ctx, ERROR_INVALID_LOCK)
        return DOSFALSE
    vol = l.find_volume_node(dos.dos_list)
    if vol:
        if l.handler is None:
            dos.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
            return DOSFALSE
        try:
            if l.handler_lock is not None:
                disk = l.handler.info(l.handler_lock)
            elif dos.handler_mgr is not None:
                # a lock without a handler lock: a lock-less volume query
                # (ACTION_DISK_INFO) resolved through the handler manager
                volume_name = dos.lock_mgr.volume_name_of_lock(l)
                disk = dos.handler_mgr.disk_info(volume_name)
            else:
                disk = l.handler.disk_info(None)
        except HandlerError as e:
            dos.setioerr(ctx, e.code)
            return DOSFALSE
        disk_state = disk.disk_state
        block_size = disk.bytes_per_block
        total = disk.num_blocks
        used = disk.num_blocks_used
        info_data.id_NumSoftErrors.val = 0
        info_data.id_UnitNumber.val = 0  # not that we really care...
        info_data.id_DiskState.val = disk_state
        # InfoData has signed 32-bit block counts. Preserve capacity
        # on large host filesystems by increasing the reporting unit.
        while total > 0x7FFFFFFF:
            total = (total + 1) // 2
            used = (used + 1) // 2
            block_size *= 2
        info_data.id_NumBlocks.val = total
        info_data.id_NumBlocksUsed.val = used
        info_data.id_BytesPerBlock.val = block_size
        info_data.id_DiskType.val = 0x444F5303  # international FFS
        info_data.id_VolumeNode.aptr = vol
        info_data.id_InUse.val = 0
        dos.setioerr(ctx, 0)
        log_dos.info("Info: %s info=%06x -> true", l, info_ptr)
        return DOSTRUE
    else:
        log_dos.info("Info: %s info=%06x -> false", l, info_ptr)
        return DOSFALSE


def exnext(dos, ctx, lock_b_addr, fib_ptr):
    l = dos.lock_mgr.get_by_b_addr(lock_b_addr)
    fib = FileInfoBlockStruct(ctx.mem, fib_ptr)
    err = l.examine_next(fib)
    name = ctx.mem.r_cstr(fib.fib_FileName.addr)
    log_dos.info("ExNext: %s fib=%06x (%s) -> %s", l, fib_ptr, name, err)
    dos.setioerr(ctx, err)
    if err == NO_ERROR:
        dos.setioerr(ctx, 0)
        return DOSTRUE
    else:
        dos.setioerr(ctx, err)
        return DOSFALSE


# bytes of struct ExAllData used by each ED_* type: ED_NAME .. ED_OWNER
EX_ALL_DATA_SIZES = (0, 8, 12, 16, 20, 32, 36, 40)


def free_scan_lock(scan):
    """release the handler lock of an ExAll scan (ACTION_FREE_LOCK)"""
    if scan.handler is not None and scan.handler_lock is not None:
        scan.handler.free_lock(scan.handler_lock)


def drop_exall_scan(dos, control_ptr):
    """drop a control's scan state and release its cloned handler lock"""
    state = dos.exall_scans.pop(control_ptr, None)
    if state is not None:
        free_scan_lock(state[1])
    return state


def drop_all_exall_scans(dos):
    for state in dos.exall_scans.values():
        free_scan_lock(state[1])
    dos.exall_scans.clear()


def exall(dos, ctx, lock_b_addr, buffer, size, data_type, control_ptr):
    """Fill a bounded entry chain using a cursor private to this control."""
    control = ExAllControlStruct(ctx.mem, control_ptr)
    control.eac_Entries.val = 0
    if data_type < 1 or data_type >= len(EX_ALL_DATA_SIZES):
        drop_exall_scan(dos, control_ptr)
        dos.setioerr(ctx, ERROR_BAD_NUMBER)
        return DOSFALSE
    if size < 0 or size > 0x7FFFFFFF:
        drop_exall_scan(dos, control_ptr)
        dos.setioerr(ctx, ERROR_NO_FREE_STORE)
        return DOSFALSE
    lock = dos.lock_mgr.get_by_b_addr(lock_b_addr)
    if lock is None:
        drop_exall_scan(dos, control_ptr)
        dos.setioerr(ctx, ERROR_INVALID_LOCK)
        return DOSFALSE
    last_key = control.eac_LastKey.val
    if last_key == 0:
        # A cloned lock owns its ExNext cache independently of the
        # caller's lock. clone_for_scan also checks that the lock is a
        # directory.
        drop_exall_scan(dos, control_ptr)
        try:
            scan = lock.clone_for_scan()
        except HandlerError as e:
            dos.setioerr(ctx, e.code)
            return DOSFALSE
        dos.exall_scans[control_ptr] = (lock, scan)
    else:
        state = dos.exall_scans.get(control_ptr)
        if state is None or state[0] is not lock:
            drop_exall_scan(dos, control_ptr)
            dos.setioerr(ctx, ERROR_INVALID_LOCK)
            return DOSFALSE
        scan = state[1]

    fib_size = FileInfoBlockStruct.get_size()
    scratch = dos.alloc.alloc_memory(
        fib_size + 4, label="ExAll_FIB", except_on_failure=False
    )
    if scratch is None:
        dos.exall_scans.pop(control_ptr, None)
        dos.setioerr(ctx, ERROR_NO_FREE_STORE)
        return DOSFALSE
    keep_scan = False
    try:
        fib = FileInfoBlockStruct(ctx.mem, scratch.addr)
        if last_key == 0:
            err = scan.examine_lock(fib)
        else:
            fib.fib_DiskKey.val = last_key
            err = NO_ERROR
        if err == NO_ERROR:
            err = exall_fill(
                dos,
                ctx,
                scan,
                fib,
                buffer,
                size,
                data_type,
                control,
                scratch.addr + fib_size,
            )
        control.eac_LastKey.val = fib.fib_DiskKey.val
        keep_scan = err == NO_ERROR
    finally:
        dos.alloc.free_memory(scratch)
        if not keep_scan:
            drop_exall_scan(dos, control_ptr)
    log_dos.info(
        "ExAll: %s buf=%06x size=%d type=%d -> entries=%d err=%d",
        lock,
        buffer,
        size,
        data_type,
        control.eac_Entries.val,
        err,
    )
    dos.setioerr(ctx, err)
    return DOSTRUE if err == NO_ERROR else DOSFALSE


def exall_fill(dos, ctx, scan, fib, buffer, size, data_type, control, type_ptr):
    match_ptr = control.eac_MatchString.aptr
    match_pat = None
    if match_ptr:
        match_pat = Pattern(None, ctx.mem.r_cstr(match_ptr), True, True)
    hook_ptr = control.eac_MatchFunc.aptr
    entry_size = EX_ALL_DATA_SIZES[data_type]
    prev = None
    pos = buffer
    end = buffer + size
    while True:
        key_before = fib.fib_DiskKey.val
        # The Examine helper leaves fib_Size unchanged for directories.
        fib.fib_Size.val = 0
        err = scan.examine_next(fib)
        if err != NO_ERROR:
            return err
        name = ctx.mem.r_cstr(fib.fib_FileName.addr)
        if match_pat is not None and not pattern_match(match_pat, name):
            continue
        comment = ""
        if data_type >= 6:
            comment = ctx.mem.r_cstr(fib.fib_Comment.addr)
        need = entry_size + len(name) + 1
        if comment:
            need += len(comment) + 1
        need = (need + 3) & ~3
        if pos + need > end:
            fib.fib_DiskKey.val = key_before
            if control.eac_Entries.val == 0:
                return ERROR_NO_FREE_STORE
            return NO_ERROR
        ead = ExAllDataStruct(ctx.mem, pos)
        str_addr = pos + entry_size
        ead.ed_Next.aptr = 0
        ead.ed_Name.aptr = str_addr
        ctx.mem.w_cstr(str_addr, name)
        str_addr += len(name) + 1
        if data_type >= 2:
            ead.ed_Type.val = fib.fib_DirEntryType.val
        if data_type >= 3:
            ead.ed_Size.val = fib.fib_Size.val
        if data_type >= 4:
            ead.ed_Prot.val = fib.fib_Protection.val
        if data_type >= 5:
            ead.ed_Days.val = fib.fib_Date.ds_Days.val
            ead.ed_Mins.val = fib.fib_Date.ds_Minute.val
            ead.ed_Ticks.val = fib.fib_Date.ds_Tick.val
        if data_type >= 6:
            ead.ed_Comment.aptr = str_addr if comment else 0
            if comment:
                ctx.mem.w_cstr(str_addr, comment)
        if data_type >= 7:
            ead.ed_OwnerUID.val = fib.fib_OwnerUID.val
            ead.ed_OwnerGID.val = fib.fib_OwnerGID.val
        if hook_ptr:
            # h_Entry follows the Hook's two-pointer MinNode header.
            entry = ctx.mem.r32(hook_ptr + 8)
            ctx.mem.w32(type_ptr, data_type)
            code = Code(
                entry,
                set_regs={REG_A0: hook_ptr, REG_A1: pos, REG_A2: type_ptr},
                get_regs=[REG_D0],
            )
            result = ctx.runner(code, name="ExAllMatch")
            if result.regs[REG_D0] == 0:
                continue
        if prev is not None:
            prev.ed_Next.aptr = pos
        prev = ead
        pos += need
        control.eac_Entries.val += 1


def exall_end(dos, ctx, lock_b_addr, buffer, size, data_type, control_ptr):
    drop_exall_scan(dos, control_ptr)
    control = ExAllControlStruct(ctx.mem, control_ptr)
    control.eac_Entries.val = 0
    control.eac_LastKey.val = 0


def parent_dir(dos, ctx, lock_b_addr):
    l = dos.lock_mgr.get_by_b_addr(lock_b_addr)
    parent_lock = dos.lock_mgr.create_parent_lock(l)
    log_dos.info("ParentDir: %s -> %s", l, parent_lock)
    if parent_lock is not None:
        return parent_lock.b_addr
    return 0


def current_dir(dos, ctx, lock_b_addr):
    # CurrentDir exchanges a BPTR. The old lock may already have been
    # released (e.g. FreeDeviceProc followed by restoring the old cwd).
    proc = ctx.process.get_ami_process()
    old = proc.current_dir.bptr
    proc.current_dir.bptr = lock_b_addr
    return old


def name_from_lock(dos, ctx, lock_b_addr, buf, buf_len):
    if lock_b_addr == 0:
        name = "SYS:"
        lock = None
    else:
        lock = dos.lock_mgr.get_by_b_addr(lock_b_addr)
        name = lock.ami_path
    log_dos.info("NameFromLock(%x,%d): %s -> %s", buf, buf_len, lock, name)
    if len(name) >= buf_len:
        dos.setioerr(ctx, ERROR_LINE_TOO_LONG)
        return DOSFALSE
    ctx.mem.w_cstr(buf, name)
    return DOSTRUE


def name_from_fh(dos, ctx, fh_b_addr, buf, buf_len):
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr)
    if fh is None:
        log_dos.warning("NameFromFH: invalid fh=%x", fh_b_addr)
        dos.setioerr(ctx, ERROR_INVALID_LOCK)
        return DOSFALSE
    name = fh.ami_path
    log_dos.info("NameFromFH(%x,%d): %s -> %s", buf, buf_len, fh, name)
    if len(name) >= buf_len:
        dos.setioerr(ctx, ERROR_LINE_TOO_LONG)
        return DOSFALSE
    ctx.mem.w_cstr(buf, name)
    return DOSTRUE


def same_device(dos, ctx, lock1_b_addr, lock2_b_addr):
    try:
        l1 = dos.lock_mgr.get_by_b_addr(lock1_b_addr) if lock1_b_addr else None
        l2 = dos.lock_mgr.get_by_b_addr(lock2_b_addr) if lock2_b_addr else None
    except Exception:
        dos.setioerr(ctx, ERROR_INVALID_LOCK)
        return DOSFALSE
    name1 = dos.lock_mgr.volume_name_of_lock(l1)
    name2 = dos.lock_mgr.volume_name_of_lock(l2)
    same = name1.lower() == name2.lower()
    log_dos.info("SameDevice(%s, %s) -> %s", name1, name2, same)
    return DOSTRUE if same else DOSFALSE


class LockMixin:
    """dos.library fd methods (HANDLER.md step 22m)."""

    def Lock(self, ctx, name: CSTR, mode):
        return lock(self, ctx, name.get_str(), mode)

    def UnLock(self, ctx, lock_b_addr):
        return unlock(self, ctx, lock_b_addr)

    def DupLock(self, ctx, lock_b_addr):
        return dup_lock(self, ctx, lock_b_addr)

    def SameLock(self, ctx, lock1_b_addr, lock2_b_addr):
        return same_lock(self, ctx, lock1_b_addr, lock2_b_addr)

    def OpenFromLock(self, ctx, lock_b_addr):
        return open_from_lock(self, ctx, lock_b_addr)

    def DupLockFromFH(self, ctx, fh_b_addr):
        return dup_lock_from_fh(self, ctx, fh_b_addr)

    def ParentOfFH(self, ctx, fh_b_addr):
        return parent_of_fh(self, ctx, fh_b_addr)

    def Examine(self, ctx, lock_b_addr, fib_ptr):
        return examine(self, ctx, lock_b_addr, fib_ptr)

    def ExamineFH(self, ctx, fh_b_addr, fib_ptr):
        return examine_fh(self, ctx, fh_b_addr, fib_ptr)

    def Info(self, ctx, lock_b_addr, info_ptr):
        return info(self, ctx, lock_b_addr, info_ptr)

    def ExNext(self, ctx, lock_b_addr, fib_ptr):
        return exnext(self, ctx, lock_b_addr, fib_ptr)

    def ExAll(self, ctx, lock_b_addr, buffer, size, data_type, control_ptr):
        return exall(self, ctx, lock_b_addr, buffer, size, data_type, control_ptr)

    def ExAllEnd(self, ctx, lock_b_addr, buffer, size, data_type, control_ptr):
        return exall_end(self, ctx, lock_b_addr, buffer, size, data_type, control_ptr)

    def ParentDir(self, ctx, lock_b_addr):
        return parent_dir(self, ctx, lock_b_addr)

    def CurrentDir(self, ctx, lock_b_addr):
        return current_dir(self, ctx, lock_b_addr)

    def NameFromLock(self, ctx, lock_b_addr, buf, buf_len):
        return name_from_lock(self, ctx, lock_b_addr, buf, buf_len)

    def NameFromFH(self, ctx, fh_b_addr, buf, buf_len):
        return name_from_fh(self, ctx, fh_b_addr, buf, buf_len)

    def SameDevice(self, ctx, lock1: LONG, lock2: LONG):
        return same_device(self, ctx, lock1.val, lock2.val)
