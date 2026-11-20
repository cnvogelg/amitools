"""Native handler packet transport (HANDLER.md step 23).

:meth:`NativeHandler._dopkt` moves a ``DosPacket`` to the running handler task
with the exec.library functions (``CreateMsgPort``/``PutMsg``/``WaitPort``/
``GetMsg``/``DeleteMsgPort``) reached through the exec proxy. Those calls need a
current task, so there are two ways to run the transport:

* driven from inside a scheduler task (a ``dos.library`` call made by an m68k
  program) it runs in that task's context and the caller blocks on the reply
  port's signal;
* driven from Python (the main greenlet, e.g. the startup handshake) a helper
  task carries it out and the scheduler is run until the helper is done.

These tests exercise both paths, the reply-port/signal reuse and the error
paths, using the deterministic Python-task handler (``native_task.TaskHandler``).
"""

import pytest
from native_task import TaskHandler

from amitools.vamos.handler.base import ERROR_NOT_IMPLEMENTED, HandlerError
from amitools.vamos.handler.native import NativeHandler, NativeHandlerManager
from amitools.vamos.libmgr import SetupLibManager
from amitools.vamos.machine import Machine, MemoryMap, Runtime
from amitools.vamos.path import PathManager
from amitools.vamos.schedule import Scheduler
from amitools.vamos.task import ExecTask


def _make_slm():
    machine = Machine()
    mem_map = MemoryMap(machine)
    mem_map.setup_ram_allocator()
    runtime = Runtime(machine)
    scheduler = Scheduler(machine)
    slm = SetupLibManager(machine, mem_map, runtime.run, scheduler, PathManager())
    slm.setup()
    return machine, scheduler, slm


def _start(slm, harness):
    handler = NativeHandler("work", {})
    slm.handler_mgr.register(handler.name, handler)
    mgr = NativeHandlerManager(
        slm.machine,
        slm.alloc,
        slm.scheduler,
        slm.seg_loader,
        slm.exec_impl,
        slm.dos_impl,
        handler_mgr=slm.handler_mgr,
        task_factory=harness,
    )
    mgr.start(handler)
    return handler, mgr


def _finish(slm):
    slm.close_base_libs()
    slm.cleanup()


def handler_native_transport_from_main_test():
    """A call made outside any task drives a helper task until the reply."""
    machine, scheduler, slm = _make_slm()
    slm.open_base_libs()
    harness = TaskHandler()
    handler, mgr = _start(slm, harness)

    # no task is running while the main greenlet makes the call
    assert scheduler.get_running_task() is None
    lock = handler.locate_object("foo")
    assert lock.bptr == 1
    # the helper task is gone again once the reply arrived
    assert scheduler.find_task("native_transport") is None
    handler.free_lock(lock)

    mgr.stop(handler)
    mgr.shutdown()
    _finish(slm)
    assert slm.alloc.is_all_free()


def handler_native_transport_in_task_test():
    """A call made inside a task runs in that task's context."""
    machine, scheduler, slm = _make_slm()
    slm.open_base_libs()
    harness = TaskHandler()
    handler, mgr = _start(slm, harness)

    result = {}

    def caller(task):
        lock = handler.locate_object("bar")
        result["lock"] = lock.bptr
        handler.free_lock(lock)
        return 0

    caller_task = ExecTask(machine, slm.alloc, "caller", func=caller)
    scheduler.add_task(caller_task.get_sched_task())
    scheduler.run_until_idle()

    assert result["lock"] == 1
    # the reply port (and its signal) was created and freed again in the caller
    assert caller_task.get_ami_task().sig_alloc.val == 0xFFFF
    # the transport ran inline: no helper task was needed
    assert scheduler.find_task("native_transport") is None

    caller_task.free()
    mgr.stop(handler)
    mgr.shutdown()
    _finish(slm)
    assert slm.alloc.is_all_free()


def handler_native_transport_reply_port_reuse_test():
    """Repeated calls from the same task reuse one signal bit."""
    machine, scheduler, slm = _make_slm()
    slm.open_base_libs()
    harness = TaskHandler()
    handler, mgr = _start(slm, harness)

    result = {}

    def caller(task):
        l1 = handler.locate_object("one")
        l2 = handler.locate_object("two")
        result["locks"] = (l1.bptr, l2.bptr)
        handler.free_lock(l1)
        handler.free_lock(l2)
        return 0

    caller_task = ExecTask(machine, slm.alloc, "caller", func=caller)
    scheduler.add_task(caller_task.get_sched_task())
    scheduler.run_until_idle()

    assert result["locks"] == (1, 2)
    # every call allocated and freed the same lowest free signal bit
    assert caller_task.get_ami_task().sig_alloc.val == 0xFFFF

    caller_task.free()
    mgr.stop(handler)
    mgr.shutdown()
    _finish(slm)
    assert slm.alloc.is_all_free()


def handler_native_transport_info_test():
    """A struct-returning action (ACTION_INFO/DISK_INFO) round-trips."""
    from native_task import (
        INFO_BYTES_PER_BLOCK,
        INFO_DISK_STATE,
        INFO_DISK_TYPE,
        INFO_NUM_BLOCKS,
        INFO_NUM_BLOCKS_USED,
    )

    machine, scheduler, slm = _make_slm()
    slm.open_base_libs()
    harness = TaskHandler()
    handler, mgr = _start(slm, harness)

    lock = handler.locate_object("foo")
    info = handler.info(lock)
    assert info.num_blocks == INFO_NUM_BLOCKS
    assert info.num_blocks_used == INFO_NUM_BLOCKS_USED
    assert info.bytes_per_block == INFO_BYTES_PER_BLOCK
    assert info.disk_type == INFO_DISK_TYPE
    assert info.disk_state == INFO_DISK_STATE
    handler.free_lock(lock)

    # the lock-less volume query takes the same path
    disk = handler.disk_info(None)
    assert disk.num_blocks == INFO_NUM_BLOCKS
    assert disk.disk_state == INFO_DISK_STATE

    mgr.stop(handler)
    mgr.shutdown()
    _finish(slm)
    assert slm.alloc.is_all_free()


def handler_native_transport_unattached_test():
    """An unattached handler refuses to send packets."""
    handler = NativeHandler("work", {})
    with pytest.raises(HandlerError) as exc:
        handler.locate_object("foo")
    assert exc.value.code == ERROR_NOT_IMPLEMENTED
    # the low-level transport hook is guarded as well
    with pytest.raises(HandlerError) as exc:
        handler._dopkt(None)
    assert exc.value.code == ERROR_NOT_IMPLEMENTED


def handler_native_transport_no_reply_test():
    """A handler that stops answering is reported instead of blocking forever."""
    machine, scheduler, slm = _make_slm()
    slm.open_base_libs()
    harness = TaskHandler()
    handler, mgr = _start(slm, harness)

    # the handler replies to the startup handshake, then goes silent
    harness.reply = False
    with pytest.raises(HandlerError) as exc:
        handler.locate_object("foo")
    assert exc.value.code == ERROR_NOT_IMPLEMENTED
    # the helper task is cleaned up even though it never got a reply
    assert scheduler.find_task("native_transport") is None

    mgr.shutdown()
    _finish(slm)
    assert slm.alloc.is_all_free()
