"""dos.library record locking (RKRM AmigaDOS 3, "Record Locking").

Record locks guard byte ranges of a file, not the file itself. Vamos does not
run concurrent AmigaDOS writers, so a per-file-handle list in this Python
process is enough to model the locking rules:

* ``REC_EXCLUSIVE``/``REC_SHARED`` honour a timeout, they fail with
  ``ERROR_LOCK_TIMEOUT`` when the region is already locked.
* ``REC_EXCLUSIVE_IMMED``/``REC_SHARED_IMMED`` ignore the timeout and fail
  with ``ERROR_LOCK_COLLISION``.

The locks belong to the handle that took them and are released when the
handle is closed (``Close()``) or explicitly unlocked.
"""

from amitools.vamos.libstructs import RecordLockStruct
from amitools.vamos.log import log_dos

from .Error import (
    ERROR_BAD_NUMBER,
    ERROR_INVALID_LOCK,
    ERROR_LOCK_COLLISION,
    ERROR_LOCK_TIMEOUT,
    ERROR_RECORD_NOT_LOCKED,
)

# dos/record.h
REC_EXCLUSIVE = 0
REC_EXCLUSIVE_IMMED = 1
REC_SHARED = 2
REC_SHARED_IMMED = 3

_IMMEDIATE_MODES = (REC_EXCLUSIVE_IMMED, REC_SHARED_IMMED)
_VALID_MODES = (
    REC_EXCLUSIVE,
    REC_EXCLUSIVE_IMMED,
    REC_SHARED,
    REC_SHARED_IMMED,
)


class RecordLock:
    def __init__(self, offset, length, shared):
        self.offset = offset
        self.length = length
        self.shared = shared

    def __repr__(self):
        kind = "shared" if self.shared else "exclusive"
        return "RecordLock(%d:%d,%s)" % (self.offset, self.length, kind)

    def overlaps(self, other):
        if self.length == 0 or other.length == 0:
            return False
        return (
            self.offset < other.offset + other.length
            and other.offset < self.offset + self.length
        )


class RecordLockManager:
    """per-file-handle record lock lists"""

    def __init__(self, dos_lib):
        self.dos_lib = dos_lib
        # baddr of the file handle -> [RecordLock, ...]
        self.locks_by_fh = {}

    def _check_fh(self, fh_b_addr):
        if fh_b_addr == 0:
            return ERROR_INVALID_LOCK
        try:
            fh = self.dos_lib.file_mgr.get_by_b_addr(fh_b_addr)
        except ValueError:
            return ERROR_INVALID_LOCK
        if fh is None:
            return ERROR_INVALID_LOCK
        return 0

    def _conflict(self, fh_b_addr, new_lock):
        """the conflicting lock in another handle (or None)"""
        for b_addr, locks in self.locks_by_fh.items():
            # a handle may overlap its own record locks
            if b_addr == fh_b_addr:
                continue
            for lock in locks:
                if not lock.overlaps(new_lock):
                    continue
                # shared locks do not block each other
                if lock.shared and new_lock.shared:
                    continue
                return lock
        return None

    def lock_record(self, ctx, fh_b_addr, offset, length, mode, timeout):
        """LockRecord(): return (success, error_code)"""
        error = self._check_fh(fh_b_addr)
        if error:
            return False, error
        if mode not in _VALID_MODES:
            log_dos.warning("LockRecord: invalid mode %d", mode)
            return False, ERROR_BAD_NUMBER
        lock = RecordLock(offset, length, mode in (REC_SHARED, REC_SHARED_IMMED))
        other = self._conflict(fh_b_addr, lock)
        if other is not None:
            log_dos.info(
                "LockRecord: fh=%s %s conflicts with %s",
                fh_b_addr,
                lock,
                other,
            )
            if mode in _IMMEDIATE_MODES:
                return False, ERROR_LOCK_COLLISION
            # a timeout would wait for the other lock to go away; there is no
            # other writer in this process, so report the wait as timed out
            return False, ERROR_LOCK_TIMEOUT
        self.locks_by_fh.setdefault(fh_b_addr, []).append(lock)
        log_dos.info("LockRecord: fh=%s %s -> locked", fh_b_addr, lock)
        return True, 0

    def unlock_record(self, fh_b_addr, offset, length):
        """UnLockRecord(): return (success, error_code)"""
        error = self._check_fh(fh_b_addr)
        if error:
            return False, error
        locks = self.locks_by_fh.get(fh_b_addr, [])
        for lock in locks:
            if lock.offset == offset and lock.length == length:
                locks.remove(lock)
                if not locks:
                    del self.locks_by_fh[fh_b_addr]
                log_dos.info("UnLockRecord: fh=%s %s -> unlocked", fh_b_addr, lock)
                return True, 0
        return False, ERROR_RECORD_NOT_LOCKED

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

    def release_handle(self, fh_b_addr):
        """drop all locks a handle still owns (called on Close)"""
        locks = self.locks_by_fh.pop(fh_b_addr, None)
        if locks:
            log_dos.info("release record locks: fh=%s %s", fh_b_addr, locks)
