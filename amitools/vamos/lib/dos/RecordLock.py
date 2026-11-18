"""dos.library record locking (RKRM AmigaDOS 3, "Record Locking").

Record locks guard byte ranges of a file, not the file itself. The handler
owns the locks of an open file (``HandlerFile.record_locks`` via
ACTION_LOCK_RECORD / ACTION_FREE_RECORD); this module only resolves the DOS
file handle and walks the ``LockRecords`` array, rolling back the entries it
already took when a later one fails.

A handler-less file handle (a bare test manager) keeps a per-handle list as a
fallback; the locks live on the handle and disappear with it.
"""

from amitools.vamos.libstructs import RecordLockStruct
from amitools.vamos.log import log_dos

from . import Helper
from .Error import (
    ERROR_BAD_NUMBER,
    ERROR_INVALID_LOCK,
)

# dos/record.h
REC_EXCLUSIVE = 0
REC_EXCLUSIVE_IMMED = 1
REC_SHARED = 2
REC_SHARED_IMMED = 3

_VALID_MODES = (
    REC_EXCLUSIVE,
    REC_EXCLUSIVE_IMMED,
    REC_SHARED,
    REC_SHARED_IMMED,
)


class RecordLockManager:
    """route record locks through the DOS file handle (and thus the handler)"""

    def __init__(self, dos_lib):
        self.dos_lib = dos_lib

    def _get_fh(self, fh_b_addr):
        if fh_b_addr == 0:
            return None
        try:
            return self.dos_lib.file_mgr.get_by_b_addr(fh_b_addr)
        except Exception:
            return None

    def lock_record(self, ctx, fh_b_addr, offset, length, mode, timeout):
        """LockRecord(): return (success, error_code)"""
        fh = self._get_fh(fh_b_addr)
        if fh is None:
            return False, ERROR_INVALID_LOCK
        if mode not in _VALID_MODES:
            log_dos.warning("LockRecord: invalid mode %d", mode)
            return False, ERROR_BAD_NUMBER
        return fh.lock_record(offset, length, mode, timeout)

    def unlock_record(self, fh_b_addr, offset, length):
        """UnLockRecord(): return (success, error_code)"""
        fh = self._get_fh(fh_b_addr)
        if fh is None:
            return False, ERROR_INVALID_LOCK
        return fh.free_record(offset, length)

    def _read_records(self, ctx, rec_array):
        """yield the RecordLock entries until the NULL rec_FH terminator"""
        addr = rec_array
        while True:
            entry = RecordLockStruct(ctx.mem, addr)
            fh_b_addr = entry.rec_FH.bptr
            if fh_b_addr == 0:
                return
            yield (
                fh_b_addr,
                entry.rec_Offset.val,
                entry.rec_Length.val,
                entry.rec_Mode.val,
            )
            addr += RecordLockStruct.get_size()

    def lock_records(self, ctx, rec_array, timeout):
        """LockRecords(): lock all entries or roll back and return the error"""
        taken = []
        for fh_b_addr, offset, length, mode in self._read_records(ctx, rec_array):
            ok, error = self.lock_record(ctx, fh_b_addr, offset, length, mode, timeout)
            if not ok:
                for args in taken:
                    self.unlock_record(*args)
                return False, error
            taken.append((fh_b_addr, offset, length))
        return True, 0

    def unlock_records(self, ctx, rec_array):
        """UnLockRecords(): unlock every entry, keep going on errors"""
        ok = True
        error = 0
        for fh_b_addr, offset, length, _mode in self._read_records(ctx, rec_array):
            res, err = self.unlock_record(fh_b_addr, offset, length)
            if not res:
                ok = False
                error = err
        return ok, error


# ----- fd functions -----


def lock_record(dos, ctx, fh, offset, length, mode, timeout):
    ok, err = dos.record_locks.lock_record(ctx, fh, offset, length, mode, timeout)
    return Helper.bool_result(dos, ctx, ok, err)


def lock_records(dos, ctx, rec_array, timeout):
    ok, err = dos.record_locks.lock_records(ctx, rec_array, timeout)
    return Helper.bool_result(dos, ctx, ok, err)


def unlock_record(dos, ctx, fh, offset, length):
    ok, err = dos.record_locks.unlock_record(fh, offset, length)
    return Helper.bool_result(dos, ctx, ok, err)


def unlock_records(dos, ctx, rec_array):
    ok, err = dos.record_locks.unlock_records(ctx, rec_array)
    return Helper.bool_result(dos, ctx, ok, err)
