import importlib
import struct
from types import SimpleNamespace

import pytest

from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.lib.TimerDevice import TimerDevice
from amitools.vamos.libmgr import LibManager
from amitools.vamos.libstructs import DosLibraryStruct, TimeRequestStruct, TimeValStruct
from amitools.vamos.machine import Code, REG_D0, REG_A6
from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.label import LabelManager

TIMER_BASE = 0x1000


@pytest.fixture(params=[False, True], ids=["unlabelled", "labelled"])
def context(request):
    mem = MockMemory()
    alloc = MemoryAlloc(mem, label_mgr=LabelManager() if request.param else None)
    lib = DosLibrary()
    lib.lib_struct = alloc.alloc_astruct(DosLibraryStruct, label="DOSBase")
    opened = []
    closed = []

    def open_lib(name, version):
        opened.append((name, version))
        return TIMER_BASE

    ctx = SimpleNamespace(
        mem=mem,
        alloc=alloc,
        exec_lib=SimpleNamespace(
            lib_mgr=SimpleNamespace(open_lib=open_lib, close_lib=closed.append)
        ),
    )
    yield SimpleNamespace(lib=lib, ctx=ctx, alloc=alloc, opened=opened, closed=closed)
    lib._finish_timer_request(ctx)
    lib.lib_struct.free()
    assert alloc.is_all_free()
    assert not alloc.mem_objs


def lib_dos_timer_request_lifetime_test(context):
    env = context
    before = env.alloc.get_free_bytes()
    env.lib._setup_timer_request(env.ctx)
    assert env.opened == [("timer.device", 0)]
    ptr = env.lib.lib_struct.dl_TimeReq.aptr
    assert ptr != 0
    request = TimeRequestStruct(env.ctx.mem, ptr)
    assert request.tr_node.io_Device.aptr == TIMER_BASE
    assert env.alloc.get_free_bytes() == before - TimeRequestStruct.get_size()
    assert not env.closed
    env.lib._finish_timer_request(env.ctx)
    assert env.lib.lib_struct.dl_TimeReq.aptr == 0
    assert env.lib.timer_request is None
    assert env.lib.timer_device == 0
    assert env.closed == [TIMER_BASE]
    assert env.alloc.get_memory(ptr) is None
    assert env.alloc.get_free_bytes() == before
    env.lib._finish_timer_request(env.ctx)
    assert env.closed == [TIMER_BASE]


def lib_dos_timer_request_unavailable_test(context):
    env = context
    env.ctx.exec_lib.lib_mgr.open_lib = lambda *args: 0
    before = env.alloc.get_free_bytes()
    env.lib._setup_timer_request(env.ctx)
    assert env.lib.lib_struct.dl_TimeReq.aptr == 0
    assert env.lib.timer_request is None
    assert env.lib.timer_request_mem is None
    env.lib._finish_timer_request(env.ctx)
    assert not env.closed
    assert env.alloc.get_free_bytes() == before


def lib_dos_timer_request_no_memory_test(context):
    env = context
    # Exhaust the actual allocator rather than simulating a typed-allocation
    # exception; DOS must tolerate the fallible memory allocation returning 0.
    remainder = env.alloc.alloc_memory(env.alloc.get_free_bytes())
    try:
        env.lib._setup_timer_request(env.ctx)
        assert env.lib.lib_struct.dl_TimeReq.aptr == 0
        assert env.lib.timer_request is None
        assert env.lib.timer_device == 0
        assert env.closed == [TIMER_BASE]
        env.lib._finish_timer_request(env.ctx)
        assert env.closed == [TIMER_BASE]
    finally:
        env.alloc.free_memory(remainder)
    # A failed optional setup must not prevent a later successful setup.
    env.lib._setup_timer_request(env.ctx)
    assert env.lib.lib_struct.dl_TimeReq.aptr != 0


def lib_dos_timer_request_allocation_exception_test(context, monkeypatch):
    env = context

    def fail(*args, **kwargs):
        raise RuntimeError("allocation failed")

    monkeypatch.setattr(env.alloc, "alloc_memory", fail)
    before = env.alloc.get_free_bytes()
    with pytest.raises(RuntimeError, match="allocation failed"):
        env.lib._setup_timer_request(env.ctx)
    assert env.lib.lib_struct.dl_TimeReq.aptr == 0
    assert env.lib.timer_device == 0
    assert env.closed == [TIMER_BASE]
    assert env.alloc.get_free_bytes() == before


def lib_dos_timer_request_close_exception_test(context):
    env = context
    env.lib._setup_timer_request(env.ctx)
    ptr = env.lib.lib_struct.dl_TimeReq.aptr

    def close(addr):
        env.closed.append(addr)
        raise RuntimeError("close failed")

    env.ctx.exec_lib.lib_mgr.close_lib = close
    with pytest.raises(RuntimeError, match="close failed"):
        env.lib._finish_timer_request(env.ctx)
    assert env.lib.lib_struct.dl_TimeReq.aptr == 0
    assert env.lib.timer_request is None
    assert env.lib.timer_device == 0
    assert env.alloc.get_memory(ptr) is None
    env.lib._finish_timer_request(env.ctx)
    assert env.closed == [TIMER_BASE]


@pytest.mark.parametrize("timer_mode", ["normal", "disabled", "no_memory"])
@pytest.mark.parametrize("execution_fails", [False, True])
def lib_dos_timer_request_main_lifecycle_test(
    monkeypatch, tmp_path, caplog, timer_mode, execution_fails
):
    main = importlib.import_module("amitools.vamos.main")
    closed = []
    snapshots = []
    close_lib = LibManager.close_lib
    alloc_memory = MemoryAlloc.alloc_memory
    error = ValueError("guest failed")

    def close(self, addr, *args, **kwargs):
        closed.append(addr)
        return close_lib(self, addr, *args, **kwargs)

    def allocate(self, size, label=None, except_on_failure=True):
        if timer_mode == "no_memory" and label == "DOS TimerRequest":
            return None
        return alloc_memory(self, size, label, except_on_failure)

    monkeypatch.setattr(LibManager, "close_lib", close)
    monkeypatch.setattr(MemoryAlloc, "alloc_memory", allocate)
    monkeypatch.setattr(TimerDevice, "get_sys_time", staticmethod(lambda: (123, 456)))

    def run(mode_ctx):
        ctx = mode_ctx.dos_ctx
        request = ctx.dos_lib.lib_struct.dl_TimeReq.aptr
        snapshots.append((ctx.alloc, request))
        if timer_mode == "normal":
            assert request != 0
            device = TimeRequestStruct(ctx.mem, request).tr_node.io_Device.aptr
            assert device != 0
            snapshots.append(device)
            # A real 68k call obtains the device via DOSBase.dl_TimeReq and
            # the timerequest's io_Device, then calls GetSysTime at LVO -66.
            code = ctx.alloc.alloc_memory(24)
            dest = ctx.alloc.alloc_astruct(TimeValStruct)
            program = bytes.fromhex("206e003a2c680014207c")
            program += struct.pack(">I", dest.addr)
            program += bytes.fromhex("4eaeffbe70004e75")
            assert len(program) <= code.size
            ctx.mem.w_block(code.addr, program)
            try:
                result = mode_ctx.def_runtime.run(
                    Code(
                        code.addr,
                        ctx.machine.get_scratch_top(),
                        set_regs={REG_A6: ctx.dos_lib.lib_struct.addr},
                        get_regs=[REG_D0],
                    )
                )
                assert result.mach_error is None
                assert (dest.tv_secs.val, dest.tv_micro.val) == (123, 456)
            finally:
                dest.free()
                ctx.alloc.free_memory(code)
        else:
            assert request == 0
        if execution_fails:
            raise error
        return [0]

    args = ["--vols-base-dir", str(tmp_path / "volumes")]
    if timer_mode == "disabled":
        args += ["-O", "timer.device=mode:off"]
    if execution_fails:
        with pytest.raises(ValueError) as caught:
            main.main(cfg_files=[], args=args, mode=SimpleNamespace(run=run))
        assert caught.value is error
    else:
        assert main.main(cfg_files=[], args=args, mode=SimpleNamespace(run=run)) == 0
    assert snapshots
    assert 0 not in closed
    if timer_mode == "normal":
        assert closed.count(snapshots[1]) == 1
    assert snapshots[0][0].is_all_free()
    assert "unknown lib" not in caplog.text
