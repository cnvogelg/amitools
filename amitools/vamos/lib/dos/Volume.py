"""dos.library volume maintenance calls (RKRM AmigaDOS 3, Format, Relabel
and AddBuffers).

The front-ends resolve the volume's handler through the handler manager and
map errors; the handler owns the behaviour (``format``, ``rename_disk``,
``more_cache`` -> ACTION_FORMAT / ACTION_RENAME_DISK / ACTION_MORE_CACHE).
"""

from amitools.vamos.astructs import CSTR, LONG
from amitools.vamos.handler import HandlerError
from amitools.vamos.log import log_dos

from . import Helper
from .Error import ERROR_NOT_IMPLEMENTED, ERROR_REQUIRED_ARG_MISSING


def format_volume(dos, ctx, filesystem, volume_name, dos_type):
    if not volume_name:
        return False, ERROR_REQUIRED_ARG_MISSING
    if dos.handler_mgr is None:
        log_dos.warning("Format('%s'): no handler manager", volume_name)
        return False, ERROR_NOT_IMPLEMENTED
    try:
        dos.handler_mgr.format(filesystem, volume_name, dos_type)
    except HandlerError as e:
        log_dos.info("Format('%s', fs=%r): %s", volume_name, filesystem, e)
        return False, e.code
    log_dos.info("Format('%s', fs=%r): ok", volume_name, filesystem)
    return True, 0


def relabel(dos, ctx, drive, new_name):
    if not drive or not new_name:
        return False, ERROR_REQUIRED_ARG_MISSING
    if dos.handler_mgr is None:
        log_dos.warning("Relabel('%s'): no handler manager", drive)
        return False, ERROR_NOT_IMPLEMENTED
    try:
        dos.handler_mgr.rename_disk(drive, new_name)
    except HandlerError as e:
        log_dos.info("Relabel('%s' -> '%s'): %s", drive, new_name, e)
        return False, e.code
    log_dos.info("Relabel('%s' -> '%s'): ok", drive, new_name)
    return True, 0


def add_buffers(dos, ctx, name, number):
    if not name:
        return False, ERROR_REQUIRED_ARG_MISSING
    if dos.handler_mgr is None:
        log_dos.warning("AddBuffers('%s'): no handler manager", name)
        return False, ERROR_NOT_IMPLEMENTED
    try:
        dos.handler_mgr.more_cache(name, number)
    except HandlerError as e:
        log_dos.info("AddBuffers('%s', %d): %s", name, number, e)
        return False, e.code
    log_dos.info("AddBuffers('%s', %d): ok", name, number)
    return True, 0


def volume_request_hook(dos, ctx, vol):
    log_dos.warning("VolumeRequestHook(%s): not implemented", vol)
    return 0


class VolumeMixin:
    """dos.library fd methods (HANDLER.md step 22m)."""

    def Format(
        self,
        ctx,
        filesystem: CSTR,
        volumename: CSTR,
        dostype: LONG,
    ):
        ok, err = format_volume(
            self,
            ctx,
            filesystem.get_str(),
            volumename.get_str(),
            dostype.val,
        )
        return Helper.bool_result(self, ctx, ok, err)

    def Relabel(self, ctx, drive: CSTR, newname: CSTR):
        ok, err = relabel(self, ctx, drive.get_str(), newname.get_str())
        return Helper.bool_result(self, ctx, ok, err)

    def AddBuffers(self, ctx, name: CSTR, number: LONG):
        ok, err = add_buffers(self, ctx, name.get_str(), number.val)
        return Helper.bool_result(self, ctx, ok, err)

    def VolumeRequestHook(self, ctx, vol: LONG):
        return volume_request_hook(self, ctx, vol.val)
