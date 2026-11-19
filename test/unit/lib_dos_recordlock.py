"""dos.library record locking routed through the handler (Step 20).

The handler owns the record locks of an open file (``HandlerFile.record_locks``
via ACTION_LOCK_RECORD / ACTION_FREE_RECORD); ``dos/RecordLock.py`` only
resolves the DOS file handle and walks the ``LockRecords`` array. A
handler-less handle keeps a per-handle fallback list.
"""

import io
from types import SimpleNamespace

from amitools.vamos.astructs import LONG
from amitools.vamos.handler import FileSystemHandler, HandlerFile
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.lib.dos.FileHandle import FileHandle
from amitools.vamos.libstructs import RecordLockStruct
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.machine.regs import REG_D1, REG_D2, REG_D3, REG_D4, REG_D5

from amitools.vamos.lib.dos.Error import (
    DOSFALSE,
    DOSTRUE,
    ERROR_BAD_NUMBER,
    ERROR_INVALID_LOCK,
    ERROR_LOCK_COLLISION,
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
        fh.close()


def _handler_fh(handler, key="f"):
    """a handler-backed file handle (its locks live on the handler file)"""
    hf = HandlerFile(key=key)
    return FileHandle(
        io.BytesIO(b"0123456789"),
        "test:" + key,
        key,
        handler=handler,
        handler_file=hf,
    )


def _bare_fh(key="f"):
    """a handler-less file handle (its locks live on the handle)"""
    return FileHandle(io.BytesIO(b"0123456789"), "test:" + key, key)


def _long(mem, cpu, reg, value):
    cpu.w_reg(reg, value)
    return LONG(cpu=cpu, reg=reg, mem=mem)


def _make_lib(handles):
    mem = MockMemory()
    cpu = MockCPU()
    lib = DosLibrary()
    lib.file_mgr = _FileMgr(handles)
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


def lib_dos_recordlock_handler_lock_unlock_test():
    handler = FileSystemHandler("test")
    fh = _handler_fh(handler)
    lib, ctx, mem, cpu = _make_lib({10: fh})

    assert _lock(lib, ctx, mem, cpu, 10, 0, 100, REC_EXCLUSIVE) == DOSTRUE
    assert lib.io_err == 0
    # the lock lives on the handler file
    assert fh.handler_file.record_locks == [(0, 100, REC_EXCLUSIVE)]

    # an overlapping lock collides (the handler does not special-case the
    # same handle)
    assert _lock(lib, ctx, mem, cpu, 10, 50, 100, REC_EXCLUSIVE) == DOSFALSE
    assert lib.io_err == ERROR_LOCK_COLLISION

    # a disjoint lock is fine
    assert _lock(lib, ctx, mem, cpu, 10, 100, 100, REC_EXCLUSIVE) == DOSTRUE

    assert _unlock(lib, ctx, mem, cpu, 10, 0, 100) == DOSTRUE
    assert _unlock(lib, ctx, mem, cpu, 10, 100, 100) == DOSTRUE
    # unlocking an unlocked region fails
    assert _unlock(lib, ctx, mem, cpu, 10, 0, 100) == DOSFALSE
    assert lib.io_err == ERROR_RECORD_NOT_LOCKED


def lib_dos_recordlock_fallback_lock_unlock_test():
    # a handler-less handle keeps the per-handle fallback list
    fh = _bare_fh()
    lib, ctx, mem, cpu = _make_lib({10: fh})

    assert _lock(lib, ctx, mem, cpu, 10, 0, 100, REC_EXCLUSIVE) == DOSTRUE
    assert fh.record_locks == [(0, 100, REC_EXCLUSIVE)]
    assert _lock(lib, ctx, mem, cpu, 10, 50, 100, REC_EXCLUSIVE) == DOSFALSE
    assert lib.io_err == ERROR_LOCK_COLLISION
    assert _unlock(lib, ctx, mem, cpu, 10, 0, 100) == DOSTRUE
    assert _unlock(lib, ctx, mem, cpu, 10, 0, 100) == DOSFALSE
    assert lib.io_err == ERROR_RECORD_NOT_LOCKED


def lib_dos_recordlock_shared_test():
    # two shared locks may overlap (neither is exclusive)
    handler = FileSystemHandler("test")
    fh = _handler_fh(handler)
    lib, ctx, mem, cpu = _make_lib({10: fh})
    assert _lock(lib, ctx, mem, cpu, 10, 0, 100, REC_SHARED) == DOSTRUE
    assert _lock(lib, ctx, mem, cpu, 10, 50, 100, REC_SHARED_IMMED) == DOSTRUE

    # an exclusive lock blocks an overlapping shared lock
    handler = FileSystemHandler("test")
    fh = _handler_fh(handler)
    lib, ctx, mem, cpu = _make_lib({10: fh})
    assert _lock(lib, ctx, mem, cpu, 10, 0, 100, REC_EXCLUSIVE_IMMED) == DOSTRUE
    assert _lock(lib, ctx, mem, cpu, 10, 50, 100, REC_SHARED_IMMED) == DOSFALSE
    assert lib.io_err == ERROR_LOCK_COLLISION


def lib_dos_recordlock_invalid_test():
    handler = FileSystemHandler("test")
    fh = _handler_fh(handler)
    lib, ctx, mem, cpu = _make_lib({10: fh})

    assert _lock(lib, ctx, mem, cpu, 99, 0, 1, REC_EXCLUSIVE) == DOSFALSE
    assert lib.io_err == ERROR_INVALID_LOCK
    assert _lock(lib, ctx, mem, cpu, 10, 0, 1, 99) == DOSFALSE
    assert lib.io_err == ERROR_BAD_NUMBER
    assert _unlock(lib, ctx, mem, cpu, 99, 0, 1) == DOSFALSE
    assert lib.io_err == ERROR_INVALID_LOCK


def _write_record(mem, index, fh, offset, length, mode):
    rec = RecordLockStruct(mem, ARRAY_ADDR + index * RecordLockStruct.get_size())
    rec.rec_FH.bptr = fh
    rec.rec_Offset.val = offset
    rec.rec_Length.val = length
    rec.rec_Mode.val = mode


def lib_dos_recordlock_records_rollback_test():
    handler = FileSystemHandler("test")
    fh = _handler_fh(handler)
    lib, ctx, mem, cpu = _make_lib({10: fh})
    _write_record(mem, 0, 10, 0, 100, REC_EXCLUSIVE)
    # an invalid mode fails the second entry and rolls back the first
    _write_record(mem, 1, 10, 200, 100, 99)
    _write_record(mem, 2, 0, 0, 0, 0)

    rec_array = _long(mem, cpu, REG_D1, ARRAY_ADDR)
    timeout = _long(mem, cpu, REG_D2, 0)
    assert lib.LockRecords(ctx, rec_array, timeout) == DOSFALSE
    assert lib.io_err == ERROR_BAD_NUMBER
    # the first record was rolled back
    assert fh.handler_file.record_locks == []


def lib_dos_recordlock_records_unlock_test():
    handler = FileSystemHandler("test")
    fh = _handler_fh(handler)
    lib, ctx, mem, cpu = _make_lib({10: fh})
    _write_record(mem, 0, 10, 0, 100, REC_EXCLUSIVE)
    _write_record(mem, 1, 10, 200, 100, REC_EXCLUSIVE)
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


def lib_dos_recordlock_close_owns_locks_test():
    # the locks live on the handler file: DOS Close ends the file but keeps no
    # separate record-lock list to release
    ended = []

    class _H(FileSystemHandler):
        def end(self, fh):
            ended.append(fh)

    handler = _H("test")
    fh = _handler_fh(handler)
    lib, ctx, mem, cpu = _make_lib({10: fh})
    assert _lock(lib, ctx, mem, cpu, 10, 0, 100, REC_EXCLUSIVE) == DOSTRUE
    assert fh.handler_file.record_locks == [(0, 100, REC_EXCLUSIVE)]

    assert lib.Close(ctx, 10) == DOSTRUE
    assert lib.file_mgr.closed == [fh]
    # Close ended the handler file that owns the locks
    assert ended == [fh.handler_file]
