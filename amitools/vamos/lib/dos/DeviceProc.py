"""dos.library device process (DevProc) calls (RKRM AmigaDOS 3,
GetDeviceProc/FreeDeviceProc/DeviceProc).

A ``DevProc`` describes how to reach the handler behind a device, volume or
assign. Vamos maps a name to a DOS list entry and hands out a temporary root
lock owned by the ``DevProc`` (``DVPF_UNLOCK``); a multi-directory assign sets
``DVPF_ASSIGN`` and is advanced directory by directory. ``GetDeviceProc("*")``
enumerates the DOS device list.
"""

from amitools.vamos.libstructs import DevProcStruct, DosListAssignStruct
from amitools.vamos.log import log_dos

from .Error import (
    ERROR_NO_MORE_ENTRIES,
    ERROR_OBJECT_NOT_FOUND,
    ERROR_REQUIRED_ARG_MISSING,
    NO_ERROR,
)


def _handler_port(dos, name):
    """the packet port of the handler serving ``name`` (0 if none)"""
    if dos.handler_mgr is None:
        return 0
    get_dispatcher = getattr(dos.handler_mgr, "get_dispatcher", None)
    if get_dispatcher is None:
        return 0
    dispatcher = get_dispatcher(name)
    return dispatcher.port if dispatcher is not None else 0


def _port_of_lock(dos, lock, name):
    """the packet port of the handler behind ``lock`` (fallback ``name``)"""
    if lock is not None and lock.handler is not None:
        dispatcher = getattr(lock.handler, "dispatcher", None)
        if dispatcher is not None:
            return dispatcher.port
    return _handler_port(dos, name)


def _new_devproc(dos, ctx, name, port, lock, flags, devnode=0):
    """allocate a DevProc for a handler/lock/device node"""
    addr = dos._alloc_mem("DevProc:%s" % name, DevProcStruct.get_size())
    devproc = DevProcStruct(ctx.mem, addr)
    devproc.dvp_Port.aptr = port
    devproc.dvp_Lock.aptr = (lock.b_addr << 2) if lock is not None else 0
    # a lock only needs unlocking if the DevProc owns it
    devproc.dvp_Flags.val = flags if lock is not None else flags & ~dos.DVPF_UNLOCK
    devproc.dvp_DevNode.aptr = devnode
    return addr


def get_device_proc(dos, ctx, name_ptr, last_devproc):
    name = ctx.mem.r_cstr(name_ptr)
    uname = name.upper()

    # "*" enumerates every entry of the DOS device list, returning the
    # next device on each call (AmigaDOS listing extension)
    if uname == "*":
        return _enumerate_devproc(dos, ctx, last_devproc)

    # a repeated call only continues a multi-directory assign
    if last_devproc != 0:
        if _advance_assign_devproc(dos, ctx, last_devproc):
            return last_devproc
        # AmigaDOS frees the DevProc and returns NULL at the end
        _release_devproc_lock(dos, DevProcStruct(ctx.mem, last_devproc))
        dos._free_mem(last_devproc)
        dos.setioerr(ctx, ERROR_NO_MORE_ENTRIES)
        return 0

    # initial named lookup
    abs_name = ctx.path_mgr.ami_abs_path(dos.get_current_dir(ctx), name)
    volume = ctx.path_mgr.ami_volume_of_path(abs_name)
    entry = dos.dos_list.get_entry_by_name(volume) if volume else None

    if entry is not None and entry.struct_def is DosListAssignStruct and entry.locks:
        # an assign: hand out its primary directory lock. A
        # multi-directory assign asks the caller to loop (DVPF_ASSIGN)
        flags = dos.DVPF_ASSIGN if len(entry.locks) > 1 else 0
        lock = entry.locks[0]
        port = _port_of_lock(dos, lock, volume)
        addr = _new_devproc(dos, ctx, name, port, lock, flags, entry.mem.addr)
    elif entry is not None and entry.locks:
        # a volume: use its DOS list root lock
        lock = entry.locks[0]
        port = _port_of_lock(dos, lock, volume)
        addr = _new_devproc(dos, ctx, name, port, lock, 0, entry.mem.addr)
    else:
        # a device (NIL:, CONSOLE:, ...) or an unknown volume: the DevProc
        # owns a temporary root lock that FreeDeviceProc releases
        vol_name = entry.name if entry is not None else volume
        lock = (
            dos.lock_mgr.create_lock(None, vol_name + ":", False) if vol_name else None
        )
        flags = dos.DVPF_UNLOCK if lock is not None else 0
        port = _port_of_lock(dos, lock, vol_name or name)
        devnode = entry.mem.addr if entry is not None else 0
        addr = _new_devproc(dos, ctx, name, port, lock, flags, devnode)

    log_dos.info(
        "GetDeviceProc: name='%s' devproc=%06x -> volume=%s devproc=%06x",
        name,
        last_devproc,
        volume,
        addr,
    )
    dos.setioerr(ctx, NO_ERROR)
    return addr


def _enumerate_devproc(dos, ctx, last_devproc):
    """one device entry of a ``GetDeviceProc("*")`` enumeration

    Like AmigaDOS the DevProc handed in is reused in place; it is only
    freed once the device list is exhausted.
    """
    flags = dos.dos_list.LDF_DEVICES
    prev = None
    if last_devproc == 0:
        entry = dos.dos_list.get_first_entry(flags)
    else:
        prev = DevProcStruct(ctx.mem, last_devproc)
        node = prev.dvp_DevNode.aptr
        cur = dos.dos_list.get_entry_by_b_addr(node >> 2) if node else None
        entry = dos.dos_list.get_next_entry(cur, flags)
    if entry is None:
        if prev is not None:
            _release_devproc_lock(dos, prev)
            dos._free_mem(last_devproc)
        dos.setioerr(ctx, ERROR_NO_MORE_ENTRIES)
        return 0
    if prev is not None:
        _release_devproc_lock(dos, prev)
    # each step hands out a temporary root lock owned by the DevProc
    lock = dos.lock_mgr.create_lock(None, entry.name + ":", False)
    dev_flags = dos.DVPF_UNLOCK if lock is not None else 0
    port = _port_of_lock(dos, lock, entry.name)
    if prev is not None:
        prev.dvp_Port.aptr = port
        prev.dvp_Lock.aptr = (lock.b_addr << 2) if lock is not None else 0
        prev.dvp_Flags.val = dev_flags
        prev.dvp_DevNode.aptr = entry.mem.addr
        addr = last_devproc
    else:
        addr = _new_devproc(dos, ctx, entry.name, port, lock, dev_flags, entry.mem.addr)
    log_dos.info(
        "GetDeviceProc('*'): devproc=%06x -> device=%s", last_devproc, entry.name
    )
    dos.setioerr(ctx, NO_ERROR)
    return addr


def _advance_assign_devproc(dos, ctx, addr):
    """advance an in-place multi-directory assign DevProc

    Returns True if the DevProc now points at the next directory, False
    when the assign has no further directory.
    """
    devproc = DevProcStruct(ctx.mem, addr)
    if not (devproc.dvp_Flags.val & dos.DVPF_ASSIGN):
        return False
    entry = dos.dos_list.get_entry_by_b_addr(devproc.dvp_DevNode.aptr >> 2)
    if entry is None:
        return False
    locks = entry.locks
    cur = devproc.dvp_Lock.aptr
    index = None
    for i, lock in enumerate(locks):
        if (lock.b_addr << 2) == cur:
            index = i
            break
    if index is None or index + 1 >= len(locks):
        return False
    lock = locks[index + 1]
    devproc.dvp_Lock.aptr = lock.b_addr << 2
    devproc.dvp_Port.aptr = _port_of_lock(dos, lock, entry.name)
    return True


def _release_devproc_lock(dos, devproc):
    """release the temporary lock a DevProc owns (DVPF_UNLOCK)"""
    if (devproc.dvp_Flags.val & dos.DVPF_UNLOCK) and devproc.dvp_Lock.aptr != 0:
        lock = dos.lock_mgr.get_by_b_addr(devproc.dvp_Lock.aptr >> 2)
        dos.lock_mgr.release_lock(lock)
    devproc.dvp_Lock.aptr = 0
    devproc.dvp_Flags.val &= ~dos.DVPF_UNLOCK


def free_device_proc(dos, ctx, addr):
    if addr == 0:
        return
    devproc = DevProcStruct(ctx.mem, addr)
    _release_devproc_lock(dos, devproc)
    dos._free_mem(addr)
    log_dos.info("FreeDeviceProc: devproc=%06x", addr)


def device_proc(dos, ctx, dev_name):
    if not dev_name:
        dos.setioerr(ctx, ERROR_REQUIRED_ARG_MISSING)
        return 0
    abs_name = dos.path_mgr.ami_abs_path(dos.get_current_dir(ctx), dev_name)
    volume = str(dos.path_mgr.ami_volume_of_path(abs_name) or dev_name)
    volume = volume.rstrip(":")
    dispatcher = (
        dos.handler_mgr.get_dispatcher(volume) if dos.handler_mgr is not None else None
    )
    if dispatcher is None:
        log_dos.warning("DeviceProc('%s'): no handler", dev_name)
        dos.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
        return 0
    log_dos.info("DeviceProc('%s') -> port %06x", dev_name, dispatcher.port)
    return dispatcher.port
