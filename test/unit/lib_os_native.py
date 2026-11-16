"""Native integration of the OS services through the configured library manager."""

import os
import struct

import pytest


@pytest.mark.skipif(
    os.environ.get("AMITOOLS_TEST_SDL") != "1", reason="native SDL opt-in"
)
def os_services_native_test(monkeypatch, tmp_path):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    from amitools.vamos.lib.intuition import TextFontStruct
    from amitools.vamos.libmgr import SetupLibManager
    from amitools.vamos.machine import Code, Machine, MemoryMap, Runtime
    from amitools.vamos.path import VamosPathManager
    from amitools.vamos.schedule import Scheduler
    from amitools.vamos.task import DosProcess

    machine = Machine()
    runtime = Runtime(machine)
    memory_map = MemoryMap(machine)
    memory_map.setup_ram_allocator()
    scheduler = Scheduler(machine)
    paths = VamosPathManager(vols_base_dir=str(tmp_path))
    assert paths.setup()
    manager = SetupLibManager(machine, memory_map, runtime.run, scheduler, paths)
    manager.setup()
    manager.open_base_libs()
    ctx = manager.dos_ctx
    task = DosProcess(machine, ctx.alloc, "OS service test", func=lambda task: 0)
    task.get_sched_task().config(scheduler, 1000)
    manager.exec_ctx.set_cur_task_process(task, task)
    ctx.set_cur_process(task)
    block = ctx.alloc.alloc_memory(1024)
    libraries = []
    try:
        for name in (
            "datatypes.library",
            "diskfont.library",
            "asl.library",
            "icon.library",
            "iffparse.library",
        ):
            addr = manager.lib_mgr.open_lib(name)
            assert addr
            libraries.append(addr)
        dt = manager.lib_mgr.get_vlib_by_addr(libraries[0]).get_impl()
        diskfont = manager.lib_mgr.get_vlib_by_addr(libraries[1]).get_impl()
        DTA = 0x80001000
        bmhd = struct.pack(">HHhhBBBBHBBhh", 16, 1, 0, 0, 1, 0, 0, 0, 0, 1, 1, 16, 1)
        chunks = b"BMHD\0\0\0\x14" + bmhd + b"BODY\0\0\0\x02\xaa\x55"
        data = b"FORM" + struct.pack(">I", len(chunks) + 4) + b"ILBM" + chunks
        ctx.mem.w_block(block.addr, data)
        tags = block.addr + 80
        for i, (tag, value) in enumerate(
            ((DTA + 101, 5), (DTA + 39, block.addr), (DTA + 40, len(data)), (0, 0))
        ):
            ctx.mem.w32(tags + 8 * i, tag)
            ctx.mem.w32(tags + 8 * i + 4, value)
        seen = []

        def run(opcode, address):
            obj = dt.NewDTObjectA(ctx, 0, tags)
            assert obj and ctx.mem.r32(obj - 4) == dt.cls
            output = block.addr + 128
            assert dt.intuition.GetAttr(manager.exec_ctx, DTA + 202, obj, output) == 1
            bitmap = ctx.mem.r32(output)
            assert ctx.mem.r16(bitmap) == 2
            assert ctx.mem.r16(bitmap + 2) == 1
            assert bytes(ctx.mem.r_block(ctx.mem.r32(bitmap + 8), 2)) == b"\xaa\x55"
            assert dt.boopsi.method(obj, 0x601, 0, 0, output, 36, 0) == 1
            assert ctx.mem.r32(output + 12) == 16
            assert ctx.mem.r32(output + 20) == 1
            assert dt.boopsi.method(obj, 0x602, 0, 1) == 1
            dt.DisposeDTObject(ctx, obj)
            assert not dt.objects
            ctx.mem.w_cstr(block.addr + 180, "topaz.font")
            ctx.mem.w32(block.addr + 160, block.addr + 180)
            ctx.mem.w16(block.addr + 164, 16)
            font = diskfont.OpenDiskFont(ctx, block.addr + 160)
            assert font
            tf = TextFontStruct(ctx.mem, font)
            assert tf.tf_YSize.val == 16 and tf.tf_CharLoc.val
            diskfont.graphics._close_font(ctx, font)
            icons = manager.lib_mgr.get_vlib_by_addr(libraries[3]).get_impl()
            icon = icons.NewDiskObject(ctx, 3)
            assert icon
            copy = icons.DupDiskObjectA(ctx, icon, 0)
            assert copy and copy != icon
            filename = "root:" + str(tmp_path / "sample").lstrip("/")
            ctx.mem.w_cstr(block.addr + 256, filename)
            assert icons.PutDiskObject(ctx, block.addr + 256, icon) == 1
            loaded = icons.GetDiskObject(ctx, block.addr + 256)
            assert loaded and icons._export(ctx, loaded) == icons._export(ctx, icon)
            icons.FreeDiskObject(ctx, loaded)
            assert icons.DeleteDiskObject(ctx, block.addr + 256) == 1
            icons.FreeDiskObject(ctx, icon)
            icons.FreeDiskObject(ctx, copy)
            seen.append(True)

        trap = machine.setup_quick_trap(run)
        result = runtime.run(Code(trap, machine.get_scratch_top()))
        assert result.exit and result.mach_error is None
        assert seen == [True]
    finally:
        ctx.alloc.free_memory(block)
        for addr in reversed(libraries):
            manager.lib_mgr.close_lib(addr)
        manager.close_base_libs()
        manager.cleanup()
        task.free()
        assert ctx.alloc.is_all_free()
        machine.cleanup()
        paths.shutdown()
