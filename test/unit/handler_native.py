"""Native handler manager lifecycle (HANDLER.md step 23).

The manager can run a real 68k handler binary (the checked-in
``data/tinyhandler.hunk``) or, for deterministic tests, a Python task that
stands in for the handler (``native_task.TaskHandler``). Both paths go through
the same transport, so the lifecycle, the startup handshake, the device node
and the ``ACTION_DIE`` shutdown are covered here.
"""

import os

import pytest
from native_task import TaskHandler

import amitools.fs.DosType as DosType
from amitools.fs.FSString import FSString
from amitools.fs.blkdev.DiskGeometry import DiskGeometry
from amitools.fs.blkdev.RawBlockDevice import RawBlockDevice
from amitools.fs.rdb.RDisk import RDisk
from amitools.vamos.disk import DiskSession
from amitools.vamos.handler.base import (
    ERROR_OBJECT_IN_USE,
    ERROR_OBJECT_NOT_FOUND,
    HandlerError,
)
from amitools.vamos.handler.native import NativeHandler, NativeHandlerManager
from amitools.vamos.libmgr import SetupLibManager
from amitools.vamos.main import wire_handler_transports
from amitools.vamos.machine import Machine, MemoryMap, Runtime
from amitools.vamos.path import PathManager
from amitools.vamos.schedule import Scheduler

HUNK = os.path.join(os.path.dirname(__file__), "data", "tinyhandler.hunk")


def _make_slm():
    machine = Machine()
    mem_map = MemoryMap(machine)
    mem_map.setup_ram_allocator()
    runtime = Runtime(machine)
    scheduler = Scheduler(machine)
    slm = SetupLibManager(machine, mem_map, runtime.run, scheduler, PathManager())
    slm.setup()
    return machine, scheduler, slm


def _make_manager(slm, task_factory=None):
    return NativeHandlerManager(
        slm.machine,
        slm.alloc,
        slm.scheduler,
        slm.seg_loader,
        slm.exec_impl,
        slm.dos_impl,
        handler_mgr=slm.handler_mgr,
        task_factory=task_factory,
    )


def _register(slm, handler):
    slm.handler_mgr.register(handler.name, handler)


def _finish(slm):
    slm.close_base_libs()
    slm.cleanup()


def _wire(slm, machine, scheduler):
    """connect the handler transports as the vamos wiring does"""
    wire_handler_transports(slm, slm.handler_mgr, machine, scheduler)


def handler_native_manager_task_factory_test():
    machine, scheduler, slm = _make_slm()
    slm.open_base_libs()
    harness = TaskHandler()
    handler = NativeHandler("work", {})
    _register(slm, handler)
    mgr = _make_manager(slm, task_factory=harness)

    mgr.start(handler)
    # the handler port is the process's pr_MsgPort
    assert handler.handler_port == harness.port.addr
    # the startup packet carried the BSTR path, the startup msg and the DosList
    pkt = harness.startup_pkt
    assert pkt is not None
    assert pkt.type.val == 0
    assert pkt.arg1.val != 0
    assert pkt.arg2.val != 0
    assert pkt.arg3.val != 0
    assert pkt.arg4.val == 0

    # a real DLT_DEVICE node points at the handler port
    entry = slm.dos_impl.dos_list.get_entry_by_name("work")
    assert entry is not None
    assert entry.struct.dol_Task.aptr == handler.handler_port
    assert entry.struct.dol_Startup.val == pkt.arg2.val
    assert entry.struct.dol_Handler.aptr != 0

    # drive a couple of actions through the packet transport
    lock = handler.locate_object("foo")
    assert lock.bptr == 1
    assert harness.locks == {1: harness.locks[1]}
    handler.free_lock(lock)
    assert harness.locks == {}

    mgr.stop(handler)
    assert mgr.started == []
    mgr.shutdown()
    _finish(slm)
    assert slm.alloc.is_all_free()


def handler_native_manager_object_in_use_test():
    machine, scheduler, slm = _make_slm()
    slm.open_base_libs()
    harness = TaskHandler()
    handler = NativeHandler("work", {})
    _register(slm, handler)
    mgr = _make_manager(slm, task_factory=harness)
    mgr.start(handler)

    lock = handler.locate_object("foo")
    # the handler refuses to die while it holds a lock
    with pytest.raises(HandlerError) as exc:
        mgr.stop(handler)
    assert exc.value.code == ERROR_OBJECT_IN_USE
    # ... and is left running so the caller can retry
    assert mgr.started != []
    handler.free_lock(lock)
    mgr.stop(handler)
    assert mgr.started == []
    mgr.shutdown()
    _finish(slm)
    assert slm.alloc.is_all_free()


def handler_native_manager_shutdown_forces_teardown_test():
    machine, scheduler, slm = _make_slm()
    slm.open_base_libs()
    harness = TaskHandler()
    handler = NativeHandler("work", {})
    _register(slm, handler)
    mgr = _make_manager(slm, task_factory=harness)
    mgr.start(handler)

    handler.locate_object("foo")
    # shutdown reports the refusal but still frees every resource
    with pytest.raises(HandlerError) as exc:
        mgr.shutdown()
    assert exc.value.code == ERROR_OBJECT_IN_USE
    assert mgr.started == []
    _finish(slm)
    assert slm.alloc.is_all_free()


def handler_native_manager_idempotent_test():
    machine, scheduler, slm = _make_slm()
    slm.open_base_libs()
    harness = TaskHandler()
    handler = NativeHandler("work", {})
    _register(slm, handler)
    mgr = _make_manager(slm, task_factory=harness)
    mgr.start(handler)

    mgr.stop(handler)
    mgr.stop(handler)
    mgr.shutdown()
    mgr.shutdown()
    _finish(slm)
    assert slm.alloc.is_all_free()


def handler_native_real_binary_wiring_test():
    """``open_base_libs`` starts a native handler whose binary is on disk."""
    machine, scheduler, slm = _make_slm()
    handler = NativeHandler("work", {"binary": HUNK})
    _register(slm, handler)
    _wire(slm, machine, scheduler)

    slm.open_base_libs()
    # the setup manager handed the live machine to the handler manager, which
    # now owns and runs the native task host
    assert slm.handler_mgr.native_mgr is not None
    assert slm.handler_mgr.native_mgr.started != []
    assert handler.handler_port != 0

    # the device node is a real DLT_DEVICE entry and the handler answers
    entry = slm.dos_impl.dos_list.get_entry_by_name("work")
    assert entry.struct.dol_Task.aptr == handler.handler_port
    assert entry.struct.dol_SegList.aptr != 0
    assert entry.struct.dol_GlobVec.val == -1  # C/asm handler
    lock = handler.locate_object("foo")
    assert lock.bptr == 1
    handler.free_lock(lock)

    # DeviceProc reports the running handler's port
    dispatcher = slm.handler_mgr.get_dispatcher("work")
    assert dispatcher.port == handler.handler_port

    _finish(slm)
    assert slm.alloc.is_all_free()


def handler_native_process_options_test():
    """``globvec``/``stack``/``priority`` reach the started handler (24a)."""
    machine, scheduler, slm = _make_slm()
    handler = NativeHandler(
        "work", {"binary": HUNK, "globvec": -2, "stack": 8192, "priority": 5}
    )
    _register(slm, handler)
    _wire(slm, machine, scheduler)

    slm.open_base_libs()
    entry = slm.dos_impl.dos_list.get_entry_by_name("work")
    assert entry.struct.dol_GlobVec.val == -2
    # the handler process carries the configured priority and stack size
    started = slm.handler_mgr.native_mgr.started[0]
    task = started.program.ami_task
    assert task.node.pri.val == 5
    assert task.tc_SPUpper.aptr - task.tc_SPLower.aptr == 8192

    _finish(slm)
    assert slm.alloc.is_all_free()


def _make_rdb_with_driver(path, data):
    raw = RawBlockDevice(str(path), read_only=False, block_bytes=512)
    raw.create(320)
    rdisk = RDisk(raw)
    rdisk.create(DiskGeometry(10, 1, 32), rdb_cyls=1)
    rdisk.add_partition(FSString("DH0"), (1, 9), dos_type=DosType.DOS3)
    assert rdisk.add_filesystem(data, dos_type=DosType.DOS3)
    raw.flush()
    rdisk.close()
    raw.close()


def handler_native_rdb_driver_test(tmp_path):
    """No ``binary=``: the handler mounts the driver stored in the RDB (24d)."""
    with open(HUNK, "rb") as fobj:
        driver = fobj.read()
    image = tmp_path / "disk.hdf"
    _make_rdb_with_driver(image, driver)

    machine, scheduler, slm = _make_slm()
    disk_session = DiskSession([image]).open()
    handler = NativeHandler("work", {"device": "DH0"})
    _register(slm, handler)
    wire_handler_transports(
        slm, slm.handler_mgr, machine, scheduler, disk_session=disk_session
    )
    try:
        slm.open_base_libs()
        # the seglist came from the RDB driver, and its global_vec (-1) is used
        entry = slm.dos_impl.dos_list.get_entry_by_name("work")
        assert entry.struct.dol_SegList.aptr != 0
        assert entry.struct.dol_GlobVec.val == -1
        # the mounted driver actually answers a DOS op
        lock = handler.locate_object("foo")
        assert lock.bptr == 1
        handler.free_lock(lock)
    finally:
        _finish(slm)
        disk_session.close()
    assert slm.alloc.is_all_free()


def handler_native_rdb_driver_globvec_override_test(tmp_path):
    """An explicit ``?globvec=`` wins over the RDB driver's own value (24d)."""
    with open(HUNK, "rb") as fobj:
        driver = fobj.read()
    image = tmp_path / "disk.hdf"
    _make_rdb_with_driver(image, driver)

    machine, scheduler, slm = _make_slm()
    disk_session = DiskSession([image]).open()
    handler = NativeHandler("work", {"device": "DH0", "globvec": -2})
    _register(slm, handler)
    wire_handler_transports(
        slm, slm.handler_mgr, machine, scheduler, disk_session=disk_session
    )
    try:
        slm.open_base_libs()
        entry = slm.dos_impl.dos_list.get_entry_by_name("work")
        assert entry.struct.dol_GlobVec.val == -2
    finally:
        _finish(slm)
        disk_session.close()
    assert slm.alloc.is_all_free()


def handler_native_missing_binary_and_driver_test():
    """No ``binary=`` and no RDB driver is a setup error, not a crash."""
    machine, scheduler, slm = _make_slm()
    slm.open_base_libs()
    handler = NativeHandler("work", {})
    _register(slm, handler)
    mgr = _make_manager(slm)
    with pytest.raises(HandlerError) as exc:
        mgr.start(handler)
    assert exc.value.code == ERROR_OBJECT_NOT_FOUND
    mgr.shutdown()
    _finish(slm)
    assert slm.alloc.is_all_free()


def handler_native_strict_lvo_clean_test():
    """The tiny fixture uses only implemented exec LVOs (step 23h)."""
    machine = Machine()
    mem_map = MemoryMap(machine)
    mem_map.setup_ram_allocator()
    runtime = Runtime(machine)
    scheduler = Scheduler(machine)
    slm = SetupLibManager(machine, mem_map, runtime.run, scheduler, PathManager())
    slm.set_strict_lvo(True)
    slm.setup()
    handler = NativeHandler("work", {"binary": HUNK})
    _register(slm, handler)
    _wire(slm, machine, scheduler)
    # a missing LVO would raise MissingLibFuncError out of the handler task
    slm.open_base_libs()
    lock = handler.locate_object("foo")
    assert lock.bptr == 1
    handler.free_lock(lock)
    _finish(slm)
    assert slm.alloc.is_all_free()
