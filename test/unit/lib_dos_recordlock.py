"""dos.library record locking (Step 18)."""

from types import SimpleNamespace
import pytest

from amitools.vamos.astructs import LONG
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.libstructs import RecordLockStruct
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.machine.regs import REG_D1, REG_D2, REG_D3, REG_D4, REG_D5

from amitools.vamos.lib.dos.Error import (
    DOSFALSE,
    DOSTRUE,
    ERROR_INVALID_LOCK,
    ERROR_LOCK_COLLISION,
    ERROR_LOCK_TIMEOUT,
    ERROR_RECORD_NOT_LOCKED,
)

REC_EXCLUSIVE = 0
REC_EXCLUSIVE_IMMED = 1
REC_SHARED = 2
REC_SHARED_IMMED = 3

ARRAY_ADDR = 0x100


class _FileMgr:
    def __init__(self, handles):
        self.handles = handles
        self.closed = []

    def get_by_b_addr(self, b_addr, for_writing=None):
        if b_addr not in self.handles:
            raise ValueError("invalid handle %s" % b_addr)
        return self.handles[b_addr]

    def close(self, fh):
        self.closed.append(fh)


def _long(mem, cpu, reg, value):
    cpu.w_reg(reg, value)
    return LONG(cpu=cpu, reg=reg, mem=mem)


def _make_lib(handles=(10, 11)):
    mem = MockMemory()
    cpu = MockCPU()
    lib = DosLibrary()
    lib.file_mgr = _FileMgr({b: object() for b in handles})
    ctx = SimpleNamespace(mem=mem, cpu=cpu, process=None)
    return lib, ctx, mem, cpu


def _lock(lib, ctx, mem, cpu, fh, offset, length, mode, timeout=0):
    return lib.LockRecord(
        ctx,
        _long(mem, cpu, REG_D1, fh),
        _long(mem, cpu, REG_D2, offset),
        _long(mem, cpu, REG_D3, length),
        _long(mem, cpu, REG_D4, mode),
        _long(mem, cpu, REG_D5, timeout),
    )


def _unlock(lib, ctx, mem, cpu, fh, offset, length):
    return lib.UnLockRecord(
        ctx,
        _long(mem, cpu, REG_D1, fh),
        _long(mem, cpu, REG_D2, offset),
        _long(mem, cpu, REG_D3, length),
    )


def lib_dos_recordlock_lock_unlock_test():
    lib, ctx, mem, cpu = _make_lib()

    assert _lock(lib, ctx, mem, cpu, 10, 0, 100, REC_EXCLUSIVE) == DOSTRUE
    assert lib.io_err == 0

    # a handle may overlap its own locks
    assert _lock(lib, ctx, mem, cpu, 10, 50, 100, REC_EXCLUSIVE) == DOSTRUE

    assert _unlock(lib, ctx, mem, cpu, 10, 0, 100) == DOSTRUE
    assert _unlock(lib, ctx, mem, cpu, 10, 50, 100) == DOSTRUE
    # unlocking an unlocked region fails
    assert _unlock(lib, ctx, mem, cpu, 10, 0, 100) == DOSFALSE
    assert lib.io_err == ERROR_RECORD_NOT_LOCKED


def lib_dos_recordlock_invalid_test():
    lib, ctx, mem, cpu = _make_lib()

    assert _lock(lib, ctx, mem, cpu, 99, 0, 1, REC_EXCLUSIVE) == DOSFALSE
    assert lib.io_err == ERROR_INVALID_LOCK
    assert _lock(lib, ctx, mem, cpu, 10, 0, 1, 99) == DOSFALSE
    assert lib.io_err != 0
    assert _unlock(lib, ctx, mem, cpu, 99, 0, 1) == DOSFALSE
    assert lib.io_err == ERROR_INVALID_LOCK


def lib_dos_recordlock_shared_test():
    lib, ctx, mem, cpu = _make_lib()

    assert _lock(lib, ctx, mem, cpu, 10, 0, 100, REC_SHARED) == DOSTRUE
    # shared locks do not block each other
    assert _lock(lib, ctx, mem, cpu, 11, 0, 100, REC_SHARED_IMMED) == DOSTRUE

    lib, ctx, mem, cpu = _make_lib()
    assert _lock(lib, ctx, mem, cpu, 10, 0, 100, REC_EXCLUSIVE_IMMED) == DOSTRUE
    assert _lock(lib, ctx, mem, cpu, 11, 0, 100, REC_SHARED_IMMED) == DOSFALSE
    assert lib.io_err == ERROR_LOCK_COLLISION


@pytest.mark.parametrize("mode", [REC_EXCLUSIVE, REC_SHARED, REC_EXCLUSIVE_IMMED])
def lib_dos_recordlock_conflict_test(mode):
    lib, ctx, mem, cpu = _make_lib()
    assert _lock(lib, ctx, mem, cpu, 10, 100, 50, REC_EXCLUSIVE) == DOSTRUE
    assert _lock(lib, ctx, mem, cpu, 11, 120, 10, mode) == DOSFALSE
    if mode == REC_EXCLUSIVE:
        assert lib.io_err == ERROR_LOCK_TIMEOUT
    elif mode == REC_EXCLUSIVE_IMMED:
        assert lib.io_err == ERROR_LOCK_COLLISION
    else:
        assert lib.io_err == ERROR_LOCK_TIMEOUT


def lib_dos_recordlock_non_overlap_test():
    lib, ctx, mem, cpu = _make_lib()
    assert _lock(lib, ctx, mem, cpu, 10, 0, 100, REC_EXCLUSIVE_IMMED) == DOSTRUE
    assert _lock(lib, ctx, mem, cpu, 11, 100, 100, REC_EXCLUSIVE_IMMED) == DOSTRUE


def _write_record(mem, index, fh, offset, length, mode):
    rec = RecordLockStruct(mem, ARRAY_ADDR + index * RecordLockStruct.get_size())
    rec.rec_FH.bptr = fh
    rec.rec_Offset.val = offset
    rec.rec_Length.val = length
    rec.rec_Mode.val = mode


def lib_dos_recordlock_records_rollback_test():
    lib, ctx, mem, cpu = _make_lib()
    _write_record(mem, 0, 10, 0, 100, REC_EXCLUSIVE)
    _write_record(mem, 1, 11, 50, 100, REC_EXCLUSIVE)
    _write_record(mem, 2, 0, 0, 0, 0)

    rec_array = _long(mem, cpu, REG_D1, ARRAY_ADDR)
    timeout = _long(mem, cpu, REG_D2, 0)
    assert lib.LockRecords(ctx, rec_array, timeout) == DOSFALSE
    assert lib.io_err == ERROR_LOCK_TIMEOUT

    # the first record was rolled back: the other handle can take it
    assert _lock(lib, ctx, mem, cpu, 11, 0, 100, REC_EXCLUSIVE_IMMED) == DOSTRUE


def lib_dos_recordlock_records_unlock_test():
    lib, ctx, mem, cpu = _make_lib()
    # the same handle may lock overlapping regions
    _write_record(mem, 0, 10, 0, 100, REC_EXCLUSIVE)
    _write_record(mem, 1, 10, 0, 100, REC_EXCLUSIVE)
    _write_record(mem, 2, 0, 0, 0, 0)

    rec_array = _long(mem, cpu, REG_D1, ARRAY_ADDR)
    timeout = _long(mem, cpu, REG_D2, 0)
    assert lib.LockRecords(ctx, rec_array, timeout) == DOSTRUE

    rec_array = _long(mem, cpu, REG_D1, ARRAY_ADDR)
    assert lib.UnLockRecords(ctx, rec_array) == DOSTRUE

    # unlocking them again reports the first missing record
    rec_array = _long(mem, cpu, REG_D1, ARRAY_ADDR)
    assert lib.UnLockRecords(ctx, rec_array) == DOSFALSE
    assert lib.io_err == ERROR_RECORD_NOT_LOCKED


def lib_dos_recordlock_close_releases_test():
    lib, ctx, mem, cpu = _make_lib()
    assert _lock(lib, ctx, mem, cpu, 10, 0, 100, REC_EXCLUSIVE_IMMED) == DOSTRUE
    assert _lock(lib, ctx, mem, cpu, 11, 0, 100, REC_EXCLUSIVE_IMMED) == DOSFALSE

    assert lib.Close(ctx, 10) == DOSTRUE
    assert lib.file_mgr.closed  # the handle was closed
    assert _lock(lib, ctx, mem, cpu, 11, 0, 100, REC_EXCLUSIVE_IMMED) == DOSTRUE
