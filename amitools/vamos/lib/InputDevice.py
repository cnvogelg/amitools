"""
Minimal input.device stub for filesystem handlers.
"""

from amitools.vamos.libcore import LibImpl
from amitools.vamos.libstructs.exec_ import IORequestStruct


class InputDevice(LibImpl):
    def BeginIO(self, ctx, io_request):
        io = IORequestStruct(ctx.mem, io_request)
        io.error.val = 0
        return 0

    def AbortIO(self, ctx, io_request=None):
        return 0
