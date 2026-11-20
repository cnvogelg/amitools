"""Native handler device visibility (HANDLER.md step 23).

A started native handler is published as a ``DLT_DEVICE`` DOS list entry whose
``dol_Task`` is the handler's ``pr_MsgPort`` and whose ``dol_SegList`` /
``dol_GlobVec`` / ``dol_Handler`` describe the loaded binary. This module checks
the new ``DosList.add_device`` fields and that the device is reachable through
``DeviceProc`` / ``GetDeviceProc`` (including the ``"*"`` enumeration).
"""

from types import SimpleNamespace

from native_task import TaskHandler

from amitools.vamos.handler.native import NativeHandler, NativeHandlerManager
from amitools.vamos.lib.dos.DeviceProc import device_proc
from amitools.vamos.lib.dos.DosList import DosList
from amitools.vamos.libmgr import SetupLibManager
from amitools.vamos.libstructs import DevProcStruct
from amitools.vamos.machine import Machine, MemoryMap, Runtime
from amitools.vamos.path.vamos import VamosPathManager
from amitools.vamos.schedule import Scheduler


def dos_list_add_device_fields_test(mem_alloc):
    """``add_device`` stores the native handler's seglist/globvec/handler."""
    mem, alloc = mem_alloc
    listing = DosList(None, None, mem, alloc)

    dev = listing.add_device(
        "DH0",
        startup_bptr=0x1234,
        task=0x2000,
        seg_list=0x100,
        glob_vec=-1,
        handler=0x40,
    )
    s = dev.struct
    assert s.dol_Type.val == 0  # DLT_DEVICE
    assert s.dol_Task.aptr == 0x2000
    assert s.dol_Startup.val == 0x1234
    assert s.dol_SegList.aptr == 0x100
    # -1 is the C/asm handler sentinel stored in the signed long dol_GlobVec
    assert s.dol_GlobVec.val == -1
    assert s.dol_Handler.aptr == 0x40

    # the other sentinel round-trips through the LONG field as well
    dev2 = listing.add_device("DH1", startup_bptr=0, glob_vec=-2)
    assert dev2.struct.dol_GlobVec.val == -2
    # a default device leaves the native fields empty
    dev3 = listing.add_device("DH2", startup_bptr=0)
    assert dev3.struct.dol_SegList.aptr == 0
    assert dev3.struct.dol_GlobVec.val == 0
    assert dev3.struct.dol_Handler.aptr == 0

    listing.free_list()


def _make_slm(tmp_path):
    machine = Machine()
    mem_map = MemoryMap(machine)
    mem_map.setup_ram_allocator()
    runtime = Runtime(machine)
    scheduler = Scheduler(machine)
    path_mgr = VamosPathManager(vols_base_dir=str(tmp_path))
    assert path_mgr.setup()
    slm = SetupLibManager(machine, mem_map, runtime.run, scheduler, path_mgr)
    slm.setup()
    slm.open_base_libs()
    return machine, scheduler, slm


def _start_native(slm, harness):
    handler = NativeHandler("work", {})
    slm.handler_mgr.register("work", handler)
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


def handler_native_device_proc_test(tmp_path):
    """``DeviceProc``/``GetDeviceProc`` report the handler's packet port."""
    machine, scheduler, slm = _make_slm(tmp_path)
    harness = TaskHandler()
    handler, mgr = _start_native(slm, harness)
    dos = slm.dos_impl

    # the DOS list device node points at the handler port
    entry = dos.dos_list.get_entry_by_name("work")
    assert entry is not None
    assert entry.struct.dol_Task.aptr == handler.handler_port

    # the native handler is a file system (local flag, no packet round trip)
    assert slm.handler_mgr.is_filesystem("work") is True

    ctx = SimpleNamespace(
        mem=slm.alloc.get_mem(),
        path_mgr=slm.path_mgr,
        process=SimpleNamespace(get_current_dir=lambda: 0),
    )

    # DeviceProc resolves the name to the handler's port
    assert device_proc(dos, ctx, "work:") == handler.handler_port

    # GetDeviceProc hands out a DevProc bound to that port
    name = slm.alloc.alloc_cstr("work:", label="NativeDevProcName")
    devproc = dos.GetDeviceProc(ctx, name.addr, 0)
    assert devproc != 0
    dvp = DevProcStruct(ctx.mem, devproc)
    assert dvp.dvp_Port.aptr == handler.handler_port
    assert dvp.dvp_DevNode.aptr == entry.mem.addr
    dos.FreeDeviceProc(ctx, devproc)

    slm.alloc.free_cstr(name)

    mgr.stop(handler)
    mgr.shutdown()
    _finish(slm)
    assert slm.alloc.is_all_free()


def handler_native_device_enumerate_test(tmp_path):
    """The native device shows up in the ``GetDeviceProc("*")`` enumeration."""
    machine, scheduler, slm = _make_slm(tmp_path)
    harness = TaskHandler()
    handler, mgr = _start_native(slm, harness)
    dos = slm.dos_impl

    ctx = SimpleNamespace(
        mem=slm.alloc.get_mem(),
        path_mgr=slm.path_mgr,
        process=SimpleNamespace(get_current_dir=lambda: 0),
    )
    star = slm.alloc.alloc_cstr("*", label="NativeDevProcStar")

    seen = []
    devproc = dos.GetDeviceProc(ctx, star.addr, 0)
    while devproc != 0:
        dvp = DevProcStruct(ctx.mem, devproc)
        seen.append((dvp.dvp_DevNode.aptr, dvp.dvp_Port.aptr))
        devproc = dos.GetDeviceProc(ctx, star.addr, devproc)

    entry = dos.dos_list.get_entry_by_name("work")
    assert (entry.mem.addr, handler.handler_port) in seen

    slm.alloc.free_cstr(star)

    mgr.stop(handler)
    mgr.shutdown()
    _finish(slm)
    assert slm.alloc.is_all_free()
