from types import SimpleNamespace

from amitools.vamos.lib.boopsi import Boopsi
from amitools.vamos.machine import Code, Machine, Runtime
from amitools.vamos.mem import MemoryAlloc


def boopsi_native_dispatch_test():
    machine = Machine()
    runtime = Runtime(machine)
    alloc = MemoryAlloc.for_machine(machine)
    ctx = SimpleNamespace(
        machine=machine,
        cpu=machine.cpu,
        mem=machine.mem,
        alloc=alloc,
        runner=runtime.run,
    )
    b = Boopsi(ctx)
    memory = alloc.alloc_memory(128)
    # Native 68000 dispatcher: OM_GET copies instance data to opg_Storage;
    # OM_SET reads the first tag value; all other methods call cl_Super's
    # hook. This enters a Python root dispatcher from nested guest code.
    ctx.mem.w_block(
        memory.addr,
        bytes.fromhex(
            "0c910000010467200c910000010367222f082f0a2f0920680018266800084e93"
            "225f245f205f4e7526690008269270014e752669000424ab000470014e75"
        ),
    )
    seen = []

    def run(opcode, address):
        cls = b.make_class("testclass", b.root, 4)
        ctx.mem.w32(cls + 8, memory.addr)
        b.add_class(cls)
        assert b.make_class("testclass", b.root, 4) == 0
        obj = b.new_object(cls, 0)
        assert obj and ctx.mem.r32(obj - 4) == cls
        assert ctx.mem.r32(cls + 44) == 1
        assert b.free_class(cls) == 0
        tags = memory.addr + 80
        ctx.mem.w32(tags, 0x80000001)
        ctx.mem.w32(tags + 4, 12345)
        assert b.method(obj, 0x103, tags, 0) == 1
        assert b.method(obj, 0x104, 0x80000001, tags + 16) == 1
        assert ctx.mem.r32(tags + 16) == 12345
        filler = alloc.alloc_memory(alloc.get_free_bytes())
        assert b.new_object(cls, 0) == 0
        assert b.method(obj, 0x102) == 0
        alloc.free_memory(filler)
        assert ctx.mem.r32(cls + 44) == 0
        assert b.free_class(cls) == 1
        seen.append(True)

    trap = machine.setup_quick_trap(run)
    try:
        result = runtime.run(Code(trap, machine.get_scratch_top()))
        assert result.exit and result.mach_error is None
        assert seen == [True]
    finally:
        b.cleanup()
        alloc.free_memory(memory)
        assert alloc.is_all_free()
        machine.cleanup()


def iff_native_stream_hook_test():
    import io

    from amitools.vamos.lib.IFFParseLibrary import IFFParseLibrary
    from amitools.vamos.machine import REG_A0, REG_A1, REG_A2, REG_D0

    machine = Machine()
    runtime = Runtime(machine)
    alloc = MemoryAlloc.for_machine(machine)
    ctx = SimpleNamespace(
        machine=machine,
        cpu=machine.cpu,
        mem=machine.mem,
        alloc=alloc,
        runner=runtime.run,
    )
    lib = IFFParseLibrary()
    lib.setup_lib(ctx, 0)
    iff = lib.AllocIFF(ctx)
    hook = alloc.alloc_memory(20)
    stream = io.BytesIO(b"FORM\0\0\0\x10PREFDATA\0\0\0\x04test")
    commands = []

    def callback(opcode, address):
        assert ctx.cpu.r_reg(REG_A0) == hook.addr
        assert ctx.cpu.r_reg(REG_A2) == iff
        packet = ctx.cpu.r_reg(REG_A1)
        command, buffer, size = (ctx.mem.r32(packet + 4 * n) for n in range(3))
        commands.append(command)
        ctx.cpu.w_reg(REG_D0, 0)
        if command == 2:
            data = stream.read(size)
            if len(data) != size:
                ctx.cpu.w_reg(REG_D0, 0xFFFFFFFB)
            else:
                ctx.mem.w_block(buffer, data)

    entry = machine.setup_quick_trap(callback)
    ctx.mem.w32(hook.addr + 8, entry)

    def run(opcode, address):
        lib.InitIFF(ctx, iff, 0, hook.addr)
        assert lib.OpenIFF(ctx, iff, 0) == 0
        lib.StopChunk(ctx, iff, 0x50524546, 0x44415441)
        assert lib.ParseIFF(ctx, iff, 0) == 0
        assert lib.ParseIFF(ctx, iff, 0) == -1
        lib.CloseIFF(ctx, iff)

    trap = machine.setup_quick_trap(run)
    try:
        result = runtime.run(Code(trap, machine.get_scratch_top()))
        assert result.exit and result.mach_error is None
        assert commands == [0, 2, 2, 2, 2, 1]
    finally:
        lib.FreeIFF(ctx, iff)
        alloc.free_memory(hook)
        assert alloc.is_all_free()
        machine.cleanup()
