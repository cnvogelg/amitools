"""dos.library lock/file functions wired to the handler API (step 12).

These tests drive the real :class:`DosLibrary` methods with a real
:class:`HostFileSysHandler` and a real :class:`LockManager`/`FileManager`, so
the handler-backed path (not a mock) is exercised:

``SameLock`` (D1/D2 fix), ``DupLock`` on a file, ``OpenFromLock``,
``DupLockFromFH``, ``ParentOfFH`` and ``SetFileSize``.
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from amitools.vamos.handler import (
    MODE_OLDFILE,
    HandlerFileInfo,
    HostFileSysHandler,
)
from amitools.vamos.lib.dos.Error import (
    DOSFALSE,
    DOSTRUE,
    ERROR_BAD_NUMBER,
    ERROR_INVALID_LOCK,
    ERROR_LINE_TOO_LONG,
    ERROR_NO_FREE_STORE,
    ERROR_NO_MORE_ENTRIES,
    ERROR_OBJECT_NOT_FOUND,
    ERROR_OBJECT_WRONG_TYPE,
)
from amitools.vamos.lib.dos.FileManager import FileManager
from amitools.vamos.lib.dos.Lock import Lock
from amitools.vamos.lib.dos.LockManager import LockManager
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.libstructs import (
    ExAllControlStruct,
    ExAllDataStruct,
    FileInfoBlockStruct,
)
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.machine.regs import REG_D1, REG_D2
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.path.amipath import AmiPath


def _ami_volume_of_path(path):
    return AmiPath(path).prefix()


def _ami_abs_parent_path(path):
    ap = AmiPath(path)
    parent = ap.parent()
    return str(parent if parent is not None else ap)


def _ami_name_of_path(cwd, path):
    ap = AmiPath(path)
    name = ap.filename()
    return name if name is not None else ap.prefix() + ":"


class _Env:
    def __init__(self, tmp_path):
        self.path = tmp_path
        (tmp_path / "f").write_bytes(b"0123456789")
        (tmp_path / "d").mkdir()
        (tmp_path / "d" / "x").write_bytes(b"q")

        self.mem = MockMemory(size_kib=256)
        self.cpu = MockCPU()
        self.alloc = MemoryAlloc(self.mem)
        self.handler = HostFileSysHandler("SYS", str(tmp_path))
        self.path_mgr = SimpleNamespace(
            ami_volume_of_path=_ami_volume_of_path,
            ami_abs_parent_path=_ami_abs_parent_path,
            ami_name_of_path=_ami_name_of_path,
        )
        self.dos_list = SimpleNamespace(
            get_entry_by_name=lambda name: SimpleNamespace(
                mem=SimpleNamespace(addr=0x1000)
            )
        )
        self.lock_mgr = LockManager(
            self.path_mgr, self.dos_list, self.alloc, self.mem, handler_mgr=None
        )
        self.file_mgr = FileManager.__new__(FileManager)
        self.file_mgr.alloc = self.alloc
        self.file_mgr.mem = self.mem
        self.file_mgr.files_by_b_addr = {}
        self.file_mgr.handler_mgr = None
        self.file_mgr.std_input = None
        self.file_mgr.std_output = None

        self.lib = DosLibrary()
        self.lib.lock_mgr = self.lock_mgr
        self.lib.file_mgr = self.file_mgr
        self.lib.path_mgr = self.path_mgr
        self.lib.dos_list = self.dos_list
        self.lib.handler_mgr = None
        self.lib.alloc = self.alloc
        self.lib.exall_scans = {}
        self.lib.setioerr = Mock()
        self.ctx = SimpleNamespace(mem=self.mem, cpu=self.cpu, alloc=self.alloc)

    # ----- helpers -----

    def make_lock(self, rel_path, exclusive=False):
        handler_lock = self.handler.locate_object(rel_path, exclusive)
        ami_path = "SYS:" + rel_path if rel_path else "SYS:"
        return self.lock_mgr.register_handler_lock(
            self.handler, handler_lock, ami_path, exclusive=exclusive
        )

    def open_file(self, rel_path, mode=MODE_OLDFILE):
        ami_path = "SYS:" + rel_path
        handler_file = self.handler.find_output(rel_path, mode)
        return self.file_mgr.wrap_handler_file(
            self.handler, handler_file, ami_path, name=AmiPath(ami_path).filename()
        )

    def call1(self, func, arg):
        self.cpu.w_reg(REG_D1, arg)
        return func(self.ctx, self.cpu.r_reg(REG_D1))

    def call2(self, func, a, b):
        self.cpu.w_reg(REG_D1, a)
        self.cpu.w_reg(REG_D2, b)
        return func(self.ctx, self.cpu.r_reg(REG_D1), self.cpu.r_reg(REG_D2))


@pytest.fixture
def env(tmp_path):
    return _Env(tmp_path)


# ----- SameLock (the D1/D2 fix) -----


def lib_dos_same_lock_distinct_objects_test(env):
    # SameLock reads D1 and D2; the old code read D1 twice, so two different
    # locks always compared equal
    dir_lock = env.make_lock("d")
    file_lock = env.make_lock("f")
    assert env.call2(env.lib.SameLock, dir_lock.b_addr, file_lock.b_addr) == DOSFALSE
    # a lock is the same as itself
    assert env.call2(env.lib.SameLock, dir_lock.b_addr, dir_lock.b_addr) == DOSTRUE


def lib_dos_same_lock_same_object_test(env):
    # two locks on the same object are the same
    a = env.make_lock("d")
    b = env.make_lock("d")
    assert a is not b
    assert env.call2(env.lib.SameLock, a.b_addr, b.b_addr) == DOSTRUE


def lib_dos_same_lock_handlerless_test(env):
    # handler-less locks compare by their DOS key
    a = env.lock_mgr._register_lock(Lock("a", "SYS:a"))
    same = env.lock_mgr._register_lock(Lock("a", "SYS:a"))
    other = env.lock_mgr._register_lock(Lock("b", "SYS:b"))
    assert env.call2(env.lib.SameLock, a.b_addr, same.b_addr) == DOSTRUE
    assert env.call2(env.lib.SameLock, a.b_addr, other.b_addr) == DOSFALSE


def lib_dos_same_lock_null_test(env):
    a = env.make_lock("d")
    assert env.call2(env.lib.SameLock, a.b_addr, 0) == DOSFALSE
    assert env.call2(env.lib.SameLock, 0, a.b_addr) == DOSFALSE


# ----- DupLock (COPY_DIR, must keep file locks working) -----


def lib_dos_duplock_file_test(env):
    lock = env.make_lock("f")
    dup_b = env.call1(env.lib.DupLock, lock.b_addr)
    assert dup_b != 0
    dup = env.lock_mgr.get_by_b_addr(dup_b)
    assert dup is not lock
    assert env.handler.same_lock(dup.handler_lock, lock.handler_lock)
    assert env.lib.setioerr.call_args.args[1] == 0


def lib_dos_duplock_dir_test(env):
    lock = env.make_lock("d")
    dup = env.lock_mgr.get_by_b_addr(env.call1(env.lib.DupLock, lock.b_addr))
    assert env.handler.same_lock(dup.handler_lock, lock.handler_lock)


# ----- OpenFromLock (FH_FROM_LOCK) -----


def lib_dos_open_from_lock_file_test(env):
    lock = env.make_lock("f")
    fh_b = env.call1(env.lib.OpenFromLock, lock.b_addr)
    assert fh_b != 0
    fh = env.file_mgr.get_by_b_addr(fh_b)
    assert fh.read(10) == b"0123456789"
    # the handle absorbs the lock
    assert env.lock_mgr.keys.num_free() == len(env.lock_mgr.keys)
    assert env.lib.setioerr.call_args.args[1] == 0


def lib_dos_open_from_lock_dir_test(env):
    lock = env.make_lock("d")
    assert env.call1(env.lib.OpenFromLock, lock.b_addr) == 0
    assert env.lib.setioerr.call_args.args[1] == ERROR_OBJECT_WRONG_TYPE


def lib_dos_open_from_lock_null_test(env):
    assert env.call1(env.lib.OpenFromLock, 0) == 0
    assert env.lib.setioerr.call_args.args[1] == ERROR_INVALID_LOCK


# ----- DupLockFromFH (COPY_DIR_FH) / ParentOfFH (PARENT_FH) -----


def lib_dos_dup_lock_from_fh_test(env):
    fh = env.open_file("d/x")
    lock_b = env.call1(env.lib.DupLockFromFH, fh.b_addr)
    assert lock_b != 0
    lock = env.lock_mgr.get_by_b_addr(lock_b)
    assert env.handler.same_lock(lock.handler_lock, env.handler.locate_object("d/x"))
    assert lock.ami_path == "SYS:d/x"
    assert lock.name == "x"


def lib_dos_parent_of_fh_test(env):
    fh = env.open_file("d/x")
    lock_b = env.call1(env.lib.ParentOfFH, fh.b_addr)
    assert lock_b != 0
    lock = env.lock_mgr.get_by_b_addr(lock_b)
    assert env.handler.same_lock(lock.handler_lock, env.handler.locate_object("d"))
    assert lock.ami_path == "SYS:d"
    assert lock.name == "d"


def lib_dos_parent_of_fh_null_test(env):
    assert env.call1(env.lib.ParentOfFH, 0) == 0
    assert env.lib.setioerr.call_args.args[1] == ERROR_OBJECT_NOT_FOUND


# ----- SetFileSize (SET_FILE_SIZE) -----


def lib_dos_set_file_size_modes_test(env):
    fh = env.open_file("f")
    # OFFSET_BEGINNING: size = offset
    assert env.lib.SetFileSize(env.ctx, fh.b_addr, 4, 0xFFFFFFFF) == 4
    assert (env.path / "f").read_bytes() == b"0123"
    # OFFSET_END: size = file size + offset
    assert env.lib.SetFileSize(env.ctx, fh.b_addr, 2, 1) == 6
    assert (env.path / "f").read_bytes() == b"0123\x00\x00"
    # OFFSET_CURRENT: size = position + offset (position is at EOF after END)
    assert env.lib.SetFileSize(env.ctx, fh.b_addr, 0xFFFFFFFF, 0) == 3
    assert (env.path / "f").read_bytes() == b"012"


def lib_dos_set_file_size_error_test(env):
    fh = env.open_file("f")
    # a negative resulting size fails with -1 + IoErr
    assert env.lib.SetFileSize(env.ctx, fh.b_addr, 0xFFFFFFFF, 0xFFFFFFFF) == -1
    assert env.lib.setioerr.call_args.args[1] == ERROR_OBJECT_WRONG_TYPE


def lib_dos_set_file_size_bad_fh_test(env):
    assert env.lib.SetFileSize(env.ctx, 0, 0, 0) == -1
    assert env.lib.setioerr.call_args.args[1] == ERROR_INVALID_LOCK


def lib_dos_set_file_size_grow_test(env):
    fh = env.open_file("f")
    # growing keeps the existing bytes and zero-fills
    assert env.lib.SetFileSize(env.ctx, fh.b_addr, 12, 0xFFFFFFFF) == 12
    assert (env.path / "f").read_bytes() == b"0123456789\x00\x00"


# ----- ParentDir (PARENT_DIR) -----


def lib_dos_parent_dir_test(env):
    lock = env.make_lock("d")
    parent_b = env.call1(env.lib.ParentDir, lock.b_addr)
    assert parent_b != 0
    parent = env.lock_mgr.get_by_b_addr(parent_b)
    assert env.handler.same_lock(parent.handler_lock, env.handler.locate_object(""))
    assert parent.ami_path == "SYS:"
    assert parent.name == "SYS:"


def lib_dos_parent_dir_root_test(env):
    # the volume root has no parent
    lock = env.make_lock("")
    assert env.call1(env.lib.ParentDir, lock.b_addr) == 0


# ----- NameFromLock (NAME_FROM_LOCK) -----


def lib_dos_name_from_lock_test(env):
    lock = env.make_lock("d")
    buf = env.alloc.alloc_memory(64)
    try:
        assert env.lib.NameFromLock(env.ctx, lock.b_addr, buf.addr, 64) == DOSTRUE
        assert env.mem.r_cstr(buf.addr) == "SYS:d"
    finally:
        env.alloc.free_memory(buf)


def lib_dos_name_from_lock_null_test(env):
    # a NULL lock names the boot volume
    buf = env.alloc.alloc_memory(64)
    try:
        assert env.lib.NameFromLock(env.ctx, 0, buf.addr, 64) == DOSTRUE
        assert env.mem.r_cstr(buf.addr) == "SYS:"
    finally:
        env.alloc.free_memory(buf)


def lib_dos_name_from_lock_too_small_test(env):
    lock = env.make_lock("d")
    buf = env.alloc.alloc_memory(64)
    try:
        # "SYS:d" needs 6 bytes including the NUL terminator
        assert env.lib.NameFromLock(env.ctx, lock.b_addr, buf.addr, 5) == DOSFALSE
        assert env.lib.setioerr.call_args.args[1] == ERROR_LINE_TOO_LONG
    finally:
        env.alloc.free_memory(buf)


# ----- NameFromFH (NAME_FROM_FH) -----


def lib_dos_name_from_fh_test(env):
    fh = env.open_file("d/x")
    buf = env.alloc.alloc_memory(64)
    try:
        assert env.lib.NameFromFH(env.ctx, fh.b_addr, buf.addr, 64) == DOSTRUE
        assert env.mem.r_cstr(buf.addr) == "SYS:d/x"
    finally:
        env.alloc.free_memory(buf)


def lib_dos_name_from_fh_errors_test(env):
    fh = env.open_file("f")
    buf = env.alloc.alloc_memory(64)
    try:
        # "SYS:f" needs 6 bytes including the NUL terminator
        assert env.lib.NameFromFH(env.ctx, fh.b_addr, buf.addr, 5) == DOSFALSE
        assert env.lib.setioerr.call_args.args[1] == ERROR_LINE_TOO_LONG
        # a NULL handle is an invalid lock
        assert env.lib.NameFromFH(env.ctx, 0, buf.addr, 64) == DOSFALSE
        assert env.lib.setioerr.call_args.args[1] == ERROR_INVALID_LOCK
    finally:
        env.alloc.free_memory(buf)


# ----- ExNext (EXAMINE_NEXT) -----


def lib_dos_exnext_test(env):
    lock = env.make_lock("")
    fib = env.alloc.alloc_astruct(FileInfoBlockStruct)
    try:
        # Examine primes fib_DiskKey so ExNext starts at the first entry
        assert env.lib.Examine(env.ctx, lock.b_addr, fib.addr) == DOSTRUE
        entries = {}
        while True:
            res = env.lib.ExNext(env.ctx, lock.b_addr, fib.addr)
            if res == DOSFALSE:
                break
            assert res == DOSTRUE
            entries[env.mem.r_cstr(fib.fib_FileName.addr)] = fib.fib_DirEntryType.val
        # end of directory
        assert env.lib.setioerr.call_args.args[1] == ERROR_NO_MORE_ENTRIES
    finally:
        fib.free()
    assert set(entries) == {"d", "f"}
    assert entries["f"] == HandlerFileInfo.FILE
    assert entries["d"] == HandlerFileInfo.DIR


# ----- ExAll (EXAMINE_ALL) -----


def _exall_run(env, lock_b_addr, size=4096, data_type=3):
    """drive the typed ``lib.ExAll`` and parse the returned entry chain"""
    control = env.alloc.alloc_astruct(ExAllControlStruct)
    buffer = env.alloc.alloc_memory(max(size, 4))
    try:
        env.mem.clear_block(buffer.addr, buffer.size, 0)
        res = env.lib.ExAll(
            env.ctx, lock_b_addr, buffer.addr, size, data_type, control.addr
        )
        entries = []
        addr = buffer.addr
        for _ in range(control.eac_Entries.val):
            entry = ExAllDataStruct(env.mem, addr)
            entries.append({"name": env.mem.r_cstr(entry.ed_Name.aptr), "entry": entry})
            addr = entry.ed_Next.aptr
        return res, env.lib.setioerr.call_args.args[1], entries
    finally:
        control.free()
        env.alloc.free_memory(buffer)


def lib_dos_exall_test(env):
    lock = env.make_lock("")
    res, error, entries = _exall_run(env, lock.b_addr, data_type=3)
    assert res == DOSFALSE and error == ERROR_NO_MORE_ENTRIES
    by_name = {item["name"]: item["entry"] for item in entries}
    assert set(by_name) == {"d", "f"}
    assert by_name["f"].ed_Size.val == 10
    assert by_name["d"].ed_Size.val == 0
    assert env.lib.exall_scans == {}


def lib_dos_exall_name_type_test(env):
    # ED_NAME: only the entry chain and the name are filled in
    lock = env.make_lock("")
    res, error, entries = _exall_run(env, lock.b_addr, data_type=1)
    assert res == DOSFALSE and error == ERROR_NO_MORE_ENTRIES
    assert {item["name"] for item in entries} == {"d", "f"}


def lib_dos_exall_owner_type_test(env):
    # ED_OWNER: the owner ids match what the handler reports
    lock = env.make_lock("")
    res, error, entries = _exall_run(env, lock.b_addr, data_type=7)
    assert res == DOSFALSE and error == ERROR_NO_MORE_ENTRIES
    for item in entries:
        info = env.handler.examine_object(env.handler.locate_object(item["name"]))
        assert item["entry"].ed_OwnerUID.val == info.owner_uid
        assert item["entry"].ed_OwnerGID.val == info.owner_gid


def lib_dos_exall_bad_lock_test(env):
    res, error, entries = _exall_run(env, 0)
    assert (res, error, entries) == (DOSFALSE, ERROR_INVALID_LOCK, [])


def lib_dos_exall_bad_type_test(env):
    lock = env.make_lock("")
    res, error, entries = _exall_run(env, lock.b_addr, data_type=0)
    assert (res, error, entries) == (DOSFALSE, ERROR_BAD_NUMBER, [])


def lib_dos_exall_small_buffer_test(env):
    lock = env.make_lock("")
    res, error, entries = _exall_run(env, lock.b_addr, size=4, data_type=3)
    assert (res, error, entries) == (DOSFALSE, ERROR_NO_FREE_STORE, [])
    assert env.lib.exall_scans == {}


def lib_dos_exall_not_directory_test(env):
    lock = env.make_lock("f")
    res, error, entries = _exall_run(env, lock.b_addr, data_type=1)
    assert (res, error, entries) == (DOSFALSE, ERROR_OBJECT_WRONG_TYPE, [])
    assert env.lib.exall_scans == {}
