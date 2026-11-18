"""dos.library link calls (RKRM AmigaDOS 3, "Creating Links" and "Resolving
Soft Links").

The front-ends only marshal the DOS arguments and map errors: the handler
owns the link behaviour (``make_link``/``read_link``, ACTION_MAKE_LINK /
ACTION_READ_LINK). A hard link's target is a lock on the same volume; a soft
link's target is a path string.
"""

from amitools.vamos.handler import HandlerError
from amitools.vamos.log import log_dos

from .Error import (
    ERROR_INVALID_LOCK,
    ERROR_LINE_TOO_LONG,
    ERROR_NOT_IMPLEMENTED,
    ERROR_REQUIRED_ARG_MISSING,
)

# dos/dos.h
LINK_HARD = 0
LINK_SOFT = 1


def make_link(dos, ctx, name, dest, soft):
    if not name:
        return False, ERROR_REQUIRED_ARG_MISSING
    if dos.handler_mgr is None:
        log_dos.warning("MakeLink('%s'): no handler manager", name)
        return False, ERROR_NOT_IMPLEMENTED
    soft_link = soft == LINK_SOFT
    if soft_link:
        # a soft link's dest is the target path string
        dest_arg = ctx.mem.r_cstr(dest)
    else:
        # a hard link's dest is a BPTR to a FileLock on the target
        try:
            dest_lock = dos.lock_mgr.get_by_b_addr(dest) if dest else None
        except Exception:
            dest_lock = None
        if dest_lock is None or dest_lock.handler_lock is None:
            return False, ERROR_INVALID_LOCK
        dest_arg = dest_lock.handler_lock
    try:
        dos.handler_mgr.make_link(name, dest_arg, soft_link, cwd=dos.get_cwd_path(ctx))
    except HandlerError as e:
        log_dos.info("MakeLink('%s', soft=%s): %s", name, soft_link, e)
        return False, e.code
    log_dos.info("MakeLink('%s', soft=%s): ok", name, soft_link)
    return True, 0


def _resolve_read_link_target(dos, port, lock):
    """return ``(handler, handler_lock, owned)`` for a ReadLink call"""
    if lock:
        try:
            dos_lock = dos.lock_mgr.get_by_b_addr(lock)
        except Exception:
            dos_lock = None
        if dos_lock is not None and dos_lock.handler is not None:
            return dos_lock.handler, dos_lock.handler_lock, False
    # no lock: resolve the handler from its packet port and use its root lock
    if port and dos.handler_mgr is not None:
        handler = dos.handler_mgr.get_handler_by_port(port)
        if handler is not None:
            try:
                handler_lock = handler.locate_object("")
            except HandlerError:
                return None, None, False
            return handler, handler_lock, True
    return None, None, False


def read_link(dos, ctx, port, lock, path, buffer, size):
    if not path or not buffer or size == 0:
        return -1, ERROR_REQUIRED_ARG_MISSING
    handler, handler_lock, owned = _resolve_read_link_target(dos, port, lock)
    if handler is None:
        return -1, ERROR_INVALID_LOCK
    try:
        target = handler.read_link(handler_lock, path, size)
    except HandlerError as e:
        log_dos.info("ReadLink('%s'): %s", path, e)
        return -1, e.code
    finally:
        if owned:
            handler.free_lock(handler_lock)
    if len(target) >= size:
        return -1, ERROR_LINE_TOO_LONG
    ctx.mem.w_cstr(buffer, target)
    log_dos.info("ReadLink('%s') -> '%s'", path, target)
    return len(target), 0
