"""dos.library assign list functions (RKRM AmigaDOS 3, "Creating and
Updating Assigns": AssignLate, AssignPath, AssignAdd, RemAssignList).

Vamos has no late-binding or non-binding handler state, so AssignLate() and
AssignPath() are modelled as regular path assigns: the path is remembered and
resolved through the path manager on every access. AssignAdd()/RemAssignList()
maintain the DOS list's directory lock list and mirror it into the path
manager.
"""

from amitools.vamos.astructs import CSTR, LONG
from amitools.vamos.log import log_dos

from . import Helper
from .Error import (
    ERROR_INVALID_COMPONENT_NAME,
    ERROR_INVALID_LOCK,
    ERROR_OBJECT_EXISTS,
    ERROR_OBJECT_NOT_FOUND,
    ERROR_REQUIRED_ARG_MISSING,
)

MAX_ASSIGN_NAME = 30


def _assign_name(name):
    """strip an (illegal) trailing colon and validate the component name"""
    if name is None:
        name = ""
    name = name.rstrip(":")
    if not name or len(name) > MAX_ASSIGN_NAME:
        return None
    return name


def _check_name(dos, name):
    if name is None:
        return ERROR_INVALID_COMPONENT_NAME
    entry = dos.dos_list.get_entry_by_name(name)
    if entry is not None:
        # only an existing assign may be converted; volumes and devices win
        if dos.dos_list.is_assign_entry(entry):
            return 0
        return ERROR_OBJECT_EXISTS
    vol_mgr = getattr(dos.path_mgr, "vol_mgr", None)
    if vol_mgr is not None and vol_mgr.get_volume(name) is not None:
        return ERROR_OBJECT_EXISTS
    return 0


def assign_path(dos, ctx, name, path):
    """AssignPath()/AssignLate(): return (success, error_code)"""
    name = _assign_name(name)
    if name is None:
        return False, ERROR_INVALID_COMPONENT_NAME
    if not path:
        return False, ERROR_REQUIRED_ARG_MISSING
    error = _check_name(dos, name)
    if error:
        return False, error
    # remember the target as an absolute Amiga path, resolved against the
    # caller's current directory (late/path assigns accept a not yet mounted
    # path, so a missing lock is not an error)
    abs_path = str(dos.path_mgr.ami_abs_path(dos.get_current_dir(ctx), path))
    if dos.dos_list.set_assign_paths(name, [abs_path]) is None:
        return False, ERROR_OBJECT_EXISTS
    log_dos.info("assign %s -> %s", name, abs_path)
    return True, 0


def assign_lock(dos, ctx, name, lockbaddr):
    """AssignLock(): bind an assign to a lock (or remove it with a NULL lock)"""
    if lockbaddr == 0:
        log_dos.info("AssignLock (%s -> null)", name)
        if dos.dos_list.remove_assign(name):
            dos.update_dos_list_head()
        return -1
    lock = dos.lock_mgr.get_by_b_addr(lockbaddr)
    log_dos.info("AssignLock (%s -> %s)", name, lock)
    if dos.dos_list.create_assign(name, lock) is not None:
        dos.update_dos_list_head()
        return -1
    return 0


def assign_add(dos, name, lock_bptr):
    """AssignAdd(): add a directory lock to a multi-assign"""
    name = _assign_name(name)
    if name is None:
        return False, ERROR_INVALID_COMPONENT_NAME
    if lock_bptr == 0:
        return False, ERROR_INVALID_LOCK
    try:
        lock = dos.lock_mgr.get_by_b_addr(lock_bptr)
    except Exception:
        return False, ERROR_INVALID_LOCK
    if lock is None:
        return False, ERROR_INVALID_LOCK
    if not dos.dos_list.add_assign_lock(name, lock):
        return False, ERROR_OBJECT_NOT_FOUND
    log_dos.info("assign add %s -> %s", name, lock.ami_path)
    return True, 0


def rem_assign_list(dos, name, lock_bptr):
    """RemAssignList(): remove a directory lock from an assign"""
    name = _assign_name(name)
    if name is None:
        return False, ERROR_INVALID_COMPONENT_NAME
    if lock_bptr == 0:
        return False, ERROR_INVALID_LOCK
    try:
        lock = dos.lock_mgr.get_by_b_addr(lock_bptr)
    except Exception:
        return False, ERROR_INVALID_LOCK
    if lock is None:
        return False, ERROR_INVALID_LOCK
    if not dos.dos_list.remove_assign_lock(name, lock):
        return False, ERROR_OBJECT_NOT_FOUND
    log_dos.info("assign remove %s -> %s", name, lock.ami_path)
    return True, 0


class AssignMixin:
    """dos.library fd methods (HANDLER.md step 22m)."""

    def AssignLock(self, ctx, name: CSTR, lock: LONG):
        return assign_lock(self, ctx, name.get_str(), lock.val)

    def AssignLate(self, ctx, name: CSTR, path: CSTR):
        ok, err = assign_path(self, ctx, name.get_str(), path.get_str())
        return Helper.bool_result(self, ctx, ok, err)

    def AssignPath(self, ctx, name: CSTR, path: CSTR):
        ok, err = assign_path(self, ctx, name.get_str(), path.get_str())
        return Helper.bool_result(self, ctx, ok, err)

    def AssignAdd(self, ctx, name: CSTR, lock: LONG):
        ok, err = assign_add(self, name.get_str(), lock.val)
        return Helper.bool_result(self, ctx, ok, err)

    def RemAssignList(self, ctx, name: CSTR, lock: LONG):
        ok, err = rem_assign_list(self, name.get_str(), lock.val)
        return Helper.bool_result(self, ctx, ok, err)
