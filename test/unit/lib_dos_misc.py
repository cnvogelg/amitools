"""dos.library volume, link, notify and miscellaneous functions (Step 18/20).

The front-ends marshal their arguments and map errors; the handler manager
dispatches to the handler. These tests use a recording manager so the packet
path is asserted without a real file system.
"""

from types import SimpleNamespace

from amitools.vamos.astructs import CSTR, LONG
from amitools.vamos.handler import HandlerError
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.libstructs import NotifyRequestStruct
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.machine.regs import REG_D1, REG_D2, REG_D3, REG_D4, REG_D5

from amitools.vamos.lib.dos.Error import (
    DOSFALSE,
    DOSTRUE,
    ERROR_INVALID_LOCK,
    ERROR_LINE_TOO_LONG,
    ERROR_NOT_IMPLEMENTED,
    ERROR_REQUIRED_ARG_MISSING,
)


def _long(mem, cpu, reg, value):
    cpu.w_reg(reg, value)
    return LONG(cpu=cpu, reg=reg, mem=mem)


def _cstr(mem, cpu, reg, base=0x400):
    cpu.w_reg(reg, base)
    return CSTR(cpu=cpu, reg=reg, mem=mem)


def _ctx():
    mem = MockMemory()
    cpu = MockCPU()
    process = SimpleNamespace(get_current_dir=lambda: 0, get_home_dir=lambda: 0)
    return SimpleNamespace(mem=mem, cpu=cpu, process=process), mem, cpu


class _RecordingMgr:
    """record the handler-manager calls the DOS front-ends make"""

    def __init__(self, error=None, link_target="target/path"):
        self.calls = []
        self.error = error
        self.link_target = link_target
        self.port_handler = None

    def _record(self, *args):
        self.calls.append(args)
        if self.error is not None:
            raise HandlerError(self.error)

    def format(self, volume_name, new_vol_name, dos_type):
        self._record("format", volume_name, new_vol_name, dos_type)

    def rename_disk(self, volume_name, new_name):
        self._record("rename_disk", volume_name, new_name)

    def more_cache(self, volume_name, count):
        self._record("more_cache", volume_name, count)

    def make_link(self, ami_path, dest, soft, cwd=None):
        self._record("make_link", ami_path, dest, soft)

    def set_owner(self, ami_path, owner, cwd=None):
        self._record("set_owner", ami_path, owner)

    def add_notify(self, ami_path, notify, cwd=None):
        self._record("add_notify", ami_path, notify)

    def remove_notify(self, ami_path, notify, cwd=None):
        self._record("remove_notify", ami_path, notify)

    def get_handler_by_port(self, port):
        self.calls.append(("get_handler_by_port", port))
        return self.port_handler


def _make_lib(mgr=None):
    lib = DosLibrary()
    lib.handler_mgr = mgr
    # get_cwd_path() resolves the current dir through the lock manager; a
    # missing cwd lock (b_addr 0) yields no cwd
    lib.lock_mgr = SimpleNamespace(get_by_b_addr=lambda b: None)
    return lib


def lib_dos_volume_test():
    mgr = _RecordingMgr()
    lib = _make_lib(mgr)
    ctx, mem, cpu = _ctx()

    mem.w_cstr(0x400, "dos.library")
    mem.w_cstr(0x480, "Work")
    assert (
        lib.Format(
            ctx,
            _cstr(mem, cpu, REG_D1, 0x400),
            _cstr(mem, cpu, REG_D2, 0x480),
            _long(mem, cpu, REG_D3, 0x444F5300),
        )
        == DOSTRUE
    )
    assert lib.io_err == 0
    assert mgr.calls == [("format", "dos.library", "Work", 0x444F5300)]

    mem.w_cstr(0x400, "DF0:")
    mem.w_cstr(0x480, "NewName")
    assert (
        lib.Relabel(
            ctx,
            _cstr(mem, cpu, REG_D1, 0x400),
            _cstr(mem, cpu, REG_D2, 0x480),
        )
        == DOSTRUE
    )
    assert mgr.calls[-1] == ("rename_disk", "DF0:", "NewName")

    assert (
        lib.AddBuffers(
            ctx,
            _cstr(mem, cpu, REG_D1, 0x400),
            _long(mem, cpu, REG_D2, 10),
        )
        == DOSTRUE
    )
    assert mgr.calls[-1] == ("more_cache", "DF0:", 10)

    # missing names are rejected before the handler
    cpu.w_reg(REG_D1, 0)
    assert (
        lib.AddBuffers(
            ctx,
            CSTR(cpu=cpu, reg=REG_D1, mem=mem),
            _long(mem, cpu, REG_D2, 10),
        )
        == DOSFALSE
    )
    assert lib.io_err == ERROR_REQUIRED_ARG_MISSING


def lib_dos_volume_error_test():
    # the handler's error code becomes IoErr
    mgr = _RecordingMgr(error=ERROR_NOT_IMPLEMENTED)
    lib = _make_lib(mgr)
    ctx, mem, cpu = _ctx()
    mem.w_cstr(0x400, "work:")
    mem.w_cstr(0x480, "Work")
    assert (
        lib.Format(
            ctx,
            _cstr(mem, cpu, REG_D1, 0x400),
            _cstr(mem, cpu, REG_D2, 0x480),
            _long(mem, cpu, REG_D3, 0),
        )
        == DOSFALSE
    )
    assert lib.io_err == ERROR_NOT_IMPLEMENTED

    assert (
        lib.Relabel(
            ctx,
            _cstr(mem, cpu, REG_D1, 0x400),
            _cstr(mem, cpu, REG_D2, 0x480),
        )
        == DOSFALSE
    )
    assert lib.io_err == ERROR_NOT_IMPLEMENTED

    # an unknown volume surfaces as 205
    mgr.error = 205
    assert (
        lib.AddBuffers(
            ctx,
            _cstr(mem, cpu, REG_D1, 0x400),
            _long(mem, cpu, REG_D2, 10),
        )
        == DOSFALSE
    )
    assert lib.io_err == 205


def lib_dos_link_test():
    mgr = _RecordingMgr()
    lib = _make_lib(mgr)
    ctx, mem, cpu = _ctx()

    # soft link: dest is a target path string
    mem.w_cstr(0x400, "work:link")
    mem.w_cstr(0x500, "work:target")
    assert (
        lib.MakeLink(
            ctx,
            _cstr(mem, cpu, REG_D1, 0x400),
            _long(mem, cpu, REG_D2, 0x500),
            _long(mem, cpu, REG_D3, 1),
        )
        == DOSTRUE
    )
    assert mgr.calls[-1] == ("make_link", "work:link", "work:target", True)

    # hard link: dest is a BPTR to a lock; its handler lock is passed
    handler_lock = object()
    dest_lock = SimpleNamespace(handler_lock=handler_lock)
    lib.lock_mgr = SimpleNamespace(get_by_b_addr=lambda b: dest_lock if b else None)
    mem.w_cstr(0x400, "work:hard")
    assert (
        lib.MakeLink(
            ctx,
            _cstr(mem, cpu, REG_D1, 0x400),
            _long(mem, cpu, REG_D2, 0x20),
            _long(mem, cpu, REG_D3, 0),
        )
        == DOSTRUE
    )
    assert mgr.calls[-1] == ("make_link", "work:hard", handler_lock, False)

    # an invalid hard link target lock is rejected before the handler
    lib.lock_mgr = SimpleNamespace(get_by_b_addr=lambda b: None)
    assert (
        lib.MakeLink(
            ctx,
            _cstr(mem, cpu, REG_D1, 0x400),
            _long(mem, cpu, REG_D2, 0x20),
            _long(mem, cpu, REG_D3, 0),
        )
        == DOSFALSE
    )
    assert lib.io_err == ERROR_INVALID_LOCK

    # a handler that does not implement links reports 236
    mgr = _RecordingMgr(error=ERROR_NOT_IMPLEMENTED)
    lib = _make_lib(mgr)
    assert (
        lib.MakeLink(
            ctx,
            _cstr(mem, cpu, REG_D1, 0x400),
            _long(mem, cpu, REG_D2, 0x500),
            _long(mem, cpu, REG_D3, 1),
        )
        == DOSFALSE
    )
    assert lib.io_err == ERROR_NOT_IMPLEMENTED


def lib_dos_read_link_test():
    mgr = _RecordingMgr()
    lib = _make_lib(mgr)
    ctx, mem, cpu = _ctx()

    # a lock-based ReadLink resolves the handler from the lock
    handler = SimpleNamespace(read_link=lambda lock, path, size: "resolved/target")
    handler_lock = object()
    lock = SimpleNamespace(handler=handler, handler_lock=handler_lock)
    lib.lock_mgr = SimpleNamespace(get_by_b_addr=lambda b: lock)

    mem.w_cstr(0x480, "work:link")
    assert lib.ReadLink(
        ctx,
        _long(mem, cpu, REG_D1, 0),
        _long(mem, cpu, REG_D2, 0x20),
        _cstr(mem, cpu, REG_D3, 0x480),
        _long(mem, cpu, REG_D4, 0x600),
        _long(mem, cpu, REG_D5, 64),
    ) == len("resolved/target")
    assert lib.io_err == 0
    assert mem.r_cstr(0x600) == "resolved/target"

    # a target that does not fit is a line-too-long error
    assert (
        lib.ReadLink(
            ctx,
            _long(mem, cpu, REG_D1, 0),
            _long(mem, cpu, REG_D2, 0x20),
            _cstr(mem, cpu, REG_D3, 0x480),
            _long(mem, cpu, REG_D4, 0x600),
            _long(mem, cpu, REG_D5, 5),
        )
        == -1
    )
    assert lib.io_err == ERROR_LINE_TOO_LONG

    # a hard link / non-link reports the handler's 233
    handler.read_link = lambda lock, path, size: (_ for _ in ()).throw(
        HandlerError(233)
    )
    assert (
        lib.ReadLink(
            ctx,
            _long(mem, cpu, REG_D1, 0),
            _long(mem, cpu, REG_D2, 0x20),
            _cstr(mem, cpu, REG_D3, 0x480),
            _long(mem, cpu, REG_D4, 0x600),
            _long(mem, cpu, REG_D5, 64),
        )
        == -1
    )
    assert lib.io_err == 233

    # a port-only call resolves the handler by its packet port
    port_handler = SimpleNamespace(
        locate_object=lambda p: "root-lock",
        free_lock=lambda _l: None,
        read_link=lambda lock, path, size: "port/target",
    )
    mgr.port_handler = port_handler
    lib.lock_mgr = SimpleNamespace(get_by_b_addr=lambda b: None)
    assert lib.ReadLink(
        ctx,
        _long(mem, cpu, REG_D1, 0x1234),
        _long(mem, cpu, REG_D2, 0),
        _cstr(mem, cpu, REG_D3, 0x480),
        _long(mem, cpu, REG_D4, 0x600),
        _long(mem, cpu, REG_D5, 64),
    ) == len("port/target")
    assert mem.r_cstr(0x600) == "port/target"


def _notify_request(mem, addr, name):
    request = NotifyRequestStruct(mem, addr)
    if name is not None:
        name_addr = addr + 0x100
        mem.w_bstr(name_addr, name)
        request.nr_Name.bptr = name_addr >> 2
    else:
        request.nr_Name.bptr = 0
    return addr


def lib_dos_notify_test():
    mgr = _RecordingMgr()
    lib = _make_lib(mgr)
    ctx, mem, cpu = _ctx()

    notify_addr = _notify_request(mem, 0x200, "work:file")
    notify = _long(mem, cpu, REG_D1, notify_addr)
    assert lib.StartNotify(ctx, notify) == DOSTRUE
    assert lib.io_err == 0
    assert mgr.calls[-1] == ("add_notify", "work:file", notify_addr)

    assert lib.EndNotify(ctx, notify) == DOSTRUE
    assert mgr.calls[-1] == ("remove_notify", "work:file", notify_addr)

    # a request without a name keeps the no-op success and never reaches
    # the handler
    before = len(mgr.calls)
    empty_addr = _notify_request(mem, 0x300, None)
    notify = _long(mem, cpu, REG_D1, empty_addr)
    assert lib.StartNotify(ctx, notify) == DOSTRUE
    assert lib.EndNotify(ctx, notify) == DOSTRUE
    assert len(mgr.calls) == before

    # a NULL request is rejected
    notify = _long(mem, cpu, REG_D1, 0)
    assert lib.StartNotify(ctx, notify) == DOSFALSE
    assert lib.io_err == ERROR_REQUIRED_ARG_MISSING


def lib_dos_assist_test():
    mgr = _RecordingMgr()
    lib = _make_lib(mgr)
    ctx, mem, cpu = _ctx()

    # ChangeMode(type=CHANGE_LOCK=0): fh is a lock BPTR
    handler = SimpleNamespace(
        change_mode=lambda obj, mode: mgr.calls.append(("change_mode", obj, mode))
    )
    handler_lock = object()
    lock = SimpleNamespace(handler=handler, handler_lock=handler_lock)
    lib.lock_mgr = SimpleNamespace(get_by_b_addr=lambda b: lock if b else None)
    assert (
        lib.ChangeMode(
            ctx,
            _long(mem, cpu, REG_D1, 0),
            _long(mem, cpu, REG_D2, 0x20),
            _long(mem, cpu, REG_D3, 2),
        )
        == DOSTRUE
    )
    assert mgr.calls[-1] == ("change_mode", handler_lock, 2)

    # ChangeMode(type=CHANGE_FH=1): fh is a file handle BPTR
    handler_file = object()
    file_handle = SimpleNamespace(handler=handler, handler_file=handler_file)
    lib.file_mgr = SimpleNamespace(get_by_b_addr=lambda b, w=None: file_handle)
    assert (
        lib.ChangeMode(
            ctx,
            _long(mem, cpu, REG_D1, 1),
            _long(mem, cpu, REG_D2, 0x30),
            _long(mem, cpu, REG_D3, 3),
        )
        == DOSTRUE
    )
    assert mgr.calls[-1] == ("change_mode", handler_file, 3)

    # an invalid type is a bad number
    assert (
        lib.ChangeMode(
            ctx,
            _long(mem, cpu, REG_D1, 7),
            _long(mem, cpu, REG_D2, 0x30),
            _long(mem, cpu, REG_D3, 3),
        )
        == DOSFALSE
    )
    assert lib.io_err != 0

    # SetOwner routes through the handler (which answers 236 here)
    mgr.error = ERROR_NOT_IMPLEMENTED
    mem.w_cstr(0x400, "work:file")
    assert (
        lib.SetOwner(ctx, _cstr(mem, cpu, REG_D1, 0x400), _long(mem, cpu, REG_D2, 0x10))
        == DOSFALSE
    )
    assert lib.io_err == ERROR_NOT_IMPLEMENTED


def lib_dos_same_device_test():
    lib = DosLibrary()
    ctx, mem, cpu = _ctx()
    locks = {
        10: object(),
        11: object(),
        12: object(),
    }
    names = {id(locks[10]): "work:", id(locks[11]): "Work:", id(locks[12]): "ram:"}
    lib.lock_mgr = SimpleNamespace(
        get_by_b_addr=lambda b_addr: locks.get(b_addr),
        volume_name_of_lock=lambda lock: names[id(lock)],
    )

    assert (
        lib.SameDevice(
            ctx,
            _long(mem, cpu, REG_D1, 10),
            _long(mem, cpu, REG_D2, 11),
        )
        == DOSTRUE
    )
    assert (
        lib.SameDevice(
            ctx,
            _long(mem, cpu, REG_D1, 10),
            _long(mem, cpu, REG_D2, 12),
        )
        == DOSFALSE
    )
