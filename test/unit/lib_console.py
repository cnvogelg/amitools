import importlib
from types import SimpleNamespace

import pytest

from amitools.vamos.lib.ConsoleDevice import ConsoleDevice
from amitools.vamos.libstructs import IORequestStruct
from amitools.vamos.machine import Code, REG_A0, REG_A1, REG_A2, REG_A6, REG_D0, REG_D1
from amitools.vamos.machine.mock import MockMemory


@pytest.mark.parametrize(
    "code,qualifier,expected",
    [
        (0x20, 0, b"a"),
        (0x20, 1, b"A"),
        (0x20, 2, b"A"),
        (0x20, 4, b"A"),
        (0x20, 5, b"A"),
        (0x20, 8, b"\x01"),
        (0x01, 1, b"!"),
        (0x01, 4, b"1"),
        (0x40, 0, b" "),
        (0x41, 0, b"\b"),
        (0x42, 0, b"\t"),
        (0x44, 0, b"\r"),
        (0x45, 0, b"\x1b"),
        (0x46, 0, b"\x7f"),
        (0xA0, 0, b""),
        (0x20, 0x10, b""),
        (0x50, 0, b""),
    ],
)
def console_convert_key_test(code, qualifier, expected):
    ctx = SimpleNamespace(mem=MockMemory())
    ctx.mem.w8(0x104, 1)
    ctx.mem.w16(0x106, code)
    ctx.mem.w16(0x108, qualifier)
    ctx.mem.w_block(0x200, b"???")
    assert ConsoleDevice().RawKeyConvert(ctx, 0x100, 0x201, 1, 0) == len(expected)
    assert bytes(ctx.mem.r_block(0x200, 3)) == b"?" + (expected or b"?") + b"?"


@pytest.mark.parametrize("length", [0, 1, 2, 0xFFFFFFFF])
def console_chain_and_buffer_bounds_test(length):
    ctx = SimpleNamespace(mem=MockMemory())
    for address, code in [(0x100, 0x20), (0x120, 0x35)]:
        ctx.mem.w8(address + 4, 1)
        ctx.mem.w16(address + 6, code)
    ctx.mem.w32(0x100, 0x120)
    ctx.mem.w_block(0x200, b"????")
    result = ConsoleDevice().RawKeyConvert(ctx, 0x100, 0x201, length, 0)
    assert result == (2 if length == 2 else -1)
    assert bytes(ctx.mem.r_block(0x200, 4)) == (b"?ab?" if length == 2 else b"????")


def console_unsupported_and_cyclic_events_test():
    ctx = SimpleNamespace(mem=MockMemory())
    lib = ConsoleDevice()
    assert lib.RawKeyConvert(ctx, 0, 0, 0, 0) == 0
    ctx.mem.w8(0x104, 2)
    assert lib.RawKeyConvert(ctx, 0x100, 0, 0, 0) == 0
    ctx.mem.w8(0x104, 1)
    ctx.mem.w16(0x106, 0x20)
    assert lib.RawKeyConvert(ctx, 0x100, 0, 1, 0x800) == 0
    assert lib.RawKeyConvert(ctx, 0x100, 0, 1, 0) == -1
    ctx.mem.w32(0x100, 0x100)
    assert lib.RawKeyConvert(ctx, 0x100, 0x200, 10, 0) == -1


def console_native_vector_and_device_lifecycle_test(tmp_path):
    main = importlib.import_module("amitools.vamos.main")
    allocations = []

    def run(mode):
        ctx = mode.exec_ctx
        exec_lib = mode.dos_ctx.exec_lib
        allocations.append(ctx.alloc)
        request = ctx.alloc.alloc_astruct(IORequestStruct)
        block = ctx.alloc.alloc_memory(64)
        try:
            device = SimpleNamespace(str="console.device")
            assert exec_lib.OpenDevice(ctx, device, 0, request.addr, 0) == -1
            assert request.io_Device.aptr == 0
            assert request.io_Error.val == -1
            assert (
                exec_lib.OpenDevice(ctx, device, 0xFFFFFFFF, request.addr, 0) == 0
            )
            assert request.io_Error.val == 0
            # Call the real device vector through the generated FD stubs.
            ctx.mem.w_block(block.addr, bytes.fromhex("4eaeffd04e75"))
            event, dest = block.addr + 8, block.addr + 40
            ctx.mem.w8(event + 4, 1)
            ctx.mem.w16(event + 6, 0x20)
            ctx.mem.w8(dest + 1, 0x55)
            result = mode.def_runtime.run(
                Code(
                    block.addr,
                    ctx.machine.get_scratch_top(),
                    set_regs={
                        REG_A6: request.io_Device.aptr,
                        REG_A0: event,
                        REG_A1: dest,
                        REG_D1: 1,
                        REG_A2: 0,
                    },
                    get_regs=[REG_D0],
                )
            )
            assert result.mach_error is None
            assert result.regs[REG_D0] == 1
            assert bytes(ctx.mem.r_block(dest, 2)) == b"aU"
            exec_lib.CloseDevice(ctx, request.addr)
            assert request.io_Device.aptr == 0
        finally:
            if request.io_Device.aptr:
                exec_lib.CloseDevice(ctx, request.addr)
            ctx.alloc.free_memory(block)
            request.free()
        return [0]

    assert (
        main.main(
            cfg_files=[],
            args=["--vols-base-dir", str(tmp_path / "volumes")],
            mode=SimpleNamespace(run=run),
        )
        == 0
    )
    assert allocations[0].is_all_free()
