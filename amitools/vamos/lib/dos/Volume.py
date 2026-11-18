"""dos.library volume maintenance calls (RKRM AmigaDOS 3, Format, Relabel
and AddBuffers).

The handler API has no format/relabel/cache packets yet; these functions
validate their arguments, log what was requested and report
``ERROR_NOT_IMPLEMENTED`` instead of silently succeeding.
"""

from amitools.vamos.log import log_dos

from .Error import ERROR_NOT_IMPLEMENTED, ERROR_REQUIRED_ARG_MISSING


def format_volume(dos, ctx, filesystem, volume_name, dos_type):
    if not volume_name:
        return False, ERROR_REQUIRED_ARG_MISSING
    log_dos.warning(
        "Format('%s', fs=%r, dostype=%r): not implemented",
        volume_name,
        filesystem,
        dos_type,
    )
    return False, ERROR_NOT_IMPLEMENTED


def relabel(dos, ctx, drive, new_name):
    if not drive or not new_name:
        return False, ERROR_REQUIRED_ARG_MISSING
    log_dos.warning("Relabel('%s' -> '%s'): not implemented", drive, new_name)
    return False, ERROR_NOT_IMPLEMENTED


def add_buffers(dos, ctx, name, number):
    if not name:
        return False, ERROR_REQUIRED_ARG_MISSING
    log_dos.warning("AddBuffers('%s', %d): not implemented", name, number)
    return False, ERROR_NOT_IMPLEMENTED
