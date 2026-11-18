"""dos.library link calls (RKRM AmigaDOS 3, "Creating Links" and "Resolving
Soft Links").

The handler API does not expose ACTION_MAKE_LINK/ACTION_READ_LINK yet, so
these front-ends validate and log the request and fail honestly. The real
implementation belongs to the handler packet layer.
"""

from amitools.vamos.log import log_dos

from .Error import ERROR_NOT_IMPLEMENTED, ERROR_REQUIRED_ARG_MISSING

# dos/dos.h
LINK_HARD = 0
LINK_SOFT = 1


def make_link(dos, ctx, name, dest, soft):
    if not name:
        return False, ERROR_REQUIRED_ARG_MISSING
    kind = "soft" if soft == LINK_SOFT else "hard"
    log_dos.warning("MakeLink('%s', %r, %s): not implemented", name, dest, kind)
    return False, ERROR_NOT_IMPLEMENTED


def read_link(dos, ctx, port, lock, path, buffer, size):
    if not path or not buffer or size == 0:
        return -1, ERROR_REQUIRED_ARG_MISSING
    log_dos.warning(
        "ReadLink(port=%06x, lock=%s, path='%s'): not implemented",
        port,
        lock,
        path,
    )
    return -1, ERROR_NOT_IMPLEMENTED
