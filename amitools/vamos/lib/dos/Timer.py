"""dos.library timing: the ``Delay`` tick sleep and the DOS timer request.

``Delay`` waits a number of 1/50s ticks. The DOS timer device request lives in
``DOSBase->dl_TimeReq``: ``setup_timer_request`` opens ``timer.device`` and
allocates the ``TimeRequest``; ``finish_timer_request`` releases both again.
"""

import time
from contextlib import ExitStack

from amitools.vamos.libstructs import TimeRequestStruct
from amitools.vamos.log import log_dos


def delay(dos, ctx, timeout):
    # DOS Delay waits d1 ticks (1/50s = 20ms per tick)
    log_dos.info("Delay(%d)", timeout)
    if timeout > 0:
        time.sleep(timeout / 50.0)
    return 0


def setup_timer_request(dos, ctx):
    dos.timer_device = 0
    dos.timer_request = None
    dos.timer_request_mem = None
    dos.lib_struct.dl_TimeReq.aptr = 0
    with ExitStack() as rollback:
        device = ctx.exec_lib.lib_mgr.open_lib("timer.device", 0)
        if device == 0:
            return
        rollback.callback(ctx.exec_lib.lib_mgr.close_lib, device)
        # The typed allocator raises an internal error on exhaustion.
        # Allocate fallibly, then use a typed view of the owned memory.
        memory = ctx.alloc.alloc_memory(
            TimeRequestStruct.get_size(),
            label="DOS TimerRequest",
            except_on_failure=False,
        )
        if memory is None:
            return
        rollback.callback(ctx.alloc.free_memory, memory)
        request = TimeRequestStruct(ctx.mem, memory.addr)
        request.tr_node.io_Device.aptr = device
        dos.timer_device = device
        dos.timer_request = request
        dos.timer_request_mem = memory
        dos.lib_struct.dl_TimeReq.aptr = request.addr
        rollback.pop_all()


def finish_timer_request(dos, ctx):
    memory = dos.timer_request_mem
    device = dos.timer_device
    dos.timer_device = 0
    dos.timer_request = None
    dos.timer_request_mem = None
    dos.lib_struct.dl_TimeReq.aptr = 0
    try:
        if memory is not None:
            ctx.alloc.free_memory(memory)
    finally:
        if device != 0:
            ctx.exec_lib.lib_mgr.close_lib(device)
