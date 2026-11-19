"""dos.library assign functions (Step 18).

AssignLate/AssignPath create a DOS list assign entry and mirror the target
into the path manager; AssignAdd/RemAssignList update the directory lock list.
"""

from types import SimpleNamespace

from amitools.vamos.astructs import CSTR, LONG
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.lib.dos.DosList import DosList
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.machine.regs import REG_D1, REG_D2
from amitools.vamos.mem import MemoryAlloc

from amitools.vamos.lib.dos.Error import (
    DOSFALSE,
    DOSTRUE,
    ERROR_INVALID_COMPONENT_NAME,
    ERROR_INVALID_LOCK,
    ERROR_OBJECT_EXISTS,
    ERROR_OBJECT_NOT_FOUND,
)

LDF_ASSIGNS = 1 << 4


class _Lock:
    def __init__(self, path, addr):
        self.ami_path = path
        self.mem = SimpleNamespace(addr=addr)
        self.released = False


class _LockMgr:
    def __init__(self, missing=()):
        self.missing = set(missing)
        self.by_addr = {}
        self.by_path = {}
        self.next_addr = 0x400

    def create_lock(self, cur_dir, path, exclusive, home_dir=None):
        path = str(path)
        if path in self.missing:
            return None
        if path in self.by_path:
            return self.by_path[path]
        lock = _Lock(path, self.next_addr)
        self.next_addr += 0x10
        self.by_addr[lock.mem.addr] = lock
        self.by_path[path] = lock
        return lock

    def get_by_b_addr(self, b_addr):
        return self.by_addr.get(b_addr)

    def same_lock(self, lock1, lock2):
        if lock1 is None or lock2 is None:
            return lock1 is lock2
        return lock1 is lock2 or lock1.ami_path == lock2.ami_path

    def release_lock(self, lock):
        if lock is not None:
            lock.released = True


class _AssignMgr:
    def __init__(self):
        self.assigns = {}
        self.deleted = []

    def set_assign(self, name, paths):
        self.assigns[name] = list(paths)

    def del_assign(self, name):
        self.deleted.append(name)
        self.assigns.pop(name, None)


def _make_lib(volumes=(), missing=()):
    mem = MockMemory()
    cpu = MockCPU()
    alloc = MemoryAlloc(mem)
    lib = DosLibrary()
    lib.path_mgr = SimpleNamespace(
        vol_mgr=SimpleNamespace(
            get_volume=lambda name: name if name in volumes else None
        ),
        ami_abs_path=lambda cwd, path: path,
    )
    lib.assign_mgr = _AssignMgr()
    lib.dos_list = DosList(lib.path_mgr, lib.assign_mgr, mem, alloc)
    lib.lock_mgr = _LockMgr(missing)
    lib.dos_list.lock_mgr = lib.lock_mgr
    lib.get_current_dir = lambda ctx: None
    ctx = SimpleNamespace(mem=mem, cpu=cpu, process=None)
    return lib, ctx, mem, cpu, alloc


def _cstr(mem, cpu, reg, text, base=0x100):
    cpu.w_reg(reg, base)
    mem.w_cstr(base, text)
    return CSTR(cpu=cpu, reg=reg, mem=mem)


def _long(mem, cpu, reg, value):
    cpu.w_reg(reg, value)
    return LONG(cpu=cpu, reg=reg, mem=mem)


def _assign_path(lib, ctx, mem, cpu, name, path):
    return lib.AssignPath(
        ctx,
        _cstr(mem, cpu, REG_D1, name, 0x100),
        _cstr(mem, cpu, REG_D2, path, 0x180),
    )


def _assign_add(lib, ctx, mem, cpu, name, lock):
    return lib.AssignAdd(
        ctx,
        _cstr(mem, cpu, REG_D1, name, 0x100),
        _long(mem, cpu, REG_D2, lock.mem.addr),
    )


def _rem_assign(lib, ctx, mem, cpu, name, lock):
    return lib.RemAssignList(
        ctx,
        _cstr(mem, cpu, REG_D1, name, 0x100),
        _long(mem, cpu, REG_D2, lock.mem.addr),
    )


def lib_dos_assign_path_test():
    lib, ctx, mem, cpu, _alloc = _make_lib()
    assert _assign_path(lib, ctx, mem, cpu, "foo", "work:dir") == DOSTRUE
    assert lib.io_err == 0

    entry = lib.dos_list.get_entry_by_name("foo")
    assert entry is not None
    assert entry.struct.dol_Type.val == 1
    assert entry.assigns == ["work:dir"]
    lock = entry.locks[0]
    assert entry.struct.dol_Lock.aptr == lock.mem.addr
    assert lib.assign_mgr.assigns["foo"] == ["work:dir"]
    assert lib.dos_list.get_first_entry(LDF_ASSIGNS) is entry


def lib_dos_assign_late_test():
    lib, ctx, mem, cpu, _alloc = _make_lib()
    assert (
        lib.AssignLate(
            ctx,
            _cstr(mem, cpu, REG_D1, "bar", 0x100),
            _cstr(mem, cpu, REG_D2, "work:late", 0x180),
        )
        == DOSTRUE
    )
    entry = lib.dos_list.get_entry_by_name("bar")
    assert entry.assigns == ["work:late"]
    assert lib.assign_mgr.assigns["bar"] == ["work:late"]


def lib_dos_assign_missing_path_test():
    # a late assign may point at a path that does not exist yet
    lib, ctx, mem, cpu, _alloc = _make_lib(missing={"work:later"})
    assert _assign_path(lib, ctx, mem, cpu, "foo", "work:later") == DOSTRUE
    entry = lib.dos_list.get_entry_by_name("foo")
    assert entry.locks == []
    assert entry.struct.dol_Lock.aptr == 0
    assert lib.assign_mgr.assigns["foo"] == ["work:later"]


def lib_dos_assign_volume_test():
    lib, ctx, mem, cpu, _alloc = _make_lib(volumes={"work"})
    lib.dos_list.add_volume("work")
    assert _assign_path(lib, ctx, mem, cpu, "work", "work:dir") == DOSFALSE
    assert lib.io_err == ERROR_OBJECT_EXISTS


def lib_dos_assign_invalid_test():
    lib, ctx, mem, cpu, _alloc = _make_lib()
    assert _assign_path(lib, ctx, mem, cpu, "", "work:dir") == DOSFALSE
    assert lib.io_err == ERROR_INVALID_COMPONENT_NAME

    assert _assign_path(lib, ctx, mem, cpu, "foo", "") == DOSFALSE
    assert lib.io_err != 0

    assert _assign_add(lib, ctx, mem, cpu, "foo", _Lock("work:dir", 0x500)) == DOSFALSE
    assert lib.io_err == ERROR_INVALID_LOCK

    lock = lib.lock_mgr.create_lock(None, "work:dir", False)
    assert _assign_add(lib, ctx, mem, cpu, "unknown", lock) == DOSFALSE
    assert lib.io_err == ERROR_OBJECT_NOT_FOUND

    assert _rem_assign(lib, ctx, mem, cpu, "unknown", lock) == DOSFALSE
    assert lib.io_err == ERROR_OBJECT_NOT_FOUND


def lib_dos_assign_add_remove_test():
    lib, ctx, mem, cpu, _alloc = _make_lib()
    assert _assign_path(lib, ctx, mem, cpu, "foo", "work:a") == DOSTRUE
    entry = lib.dos_list.get_entry_by_name("foo")
    first = entry.locks[0]

    second = lib.lock_mgr.create_lock(None, "work:b", False)
    assert _assign_add(lib, ctx, mem, cpu, "foo", second) == DOSTRUE
    assert entry.assigns == ["work:a", "work:b"]
    assert [lock.ami_path for lock in entry.locks] == ["work:a", "work:b"]
    assert entry.struct.dol_List.aptr != 0
    assert lib.assign_mgr.assigns["foo"] == ["work:a", "work:b"]

    assert _rem_assign(lib, ctx, mem, cpu, "foo", second) == DOSTRUE
    assert entry.assigns == ["work:a"]
    assert [lock.ami_path for lock in entry.locks] == ["work:a"]
    assert entry.struct.dol_List.aptr == 0
    assert lib.assign_mgr.assigns["foo"] == ["work:a"]

    # removing the last directory drops the whole assign
    assert _rem_assign(lib, ctx, mem, cpu, "foo", first) == DOSTRUE
    assert lib.dos_list.get_entry_by_name("foo") is None
    assert lib.assign_mgr.deleted == ["foo"]
    assert "foo" not in lib.assign_mgr.assigns
    assert first.released is True
