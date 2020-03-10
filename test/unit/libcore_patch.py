from amitools.vamos.libcore import *
from amitools.vamos.machine import *
from amitools.vamos.lib.VamosTestLibrary import VamosTestLibrary
from amitools.vamos.mem import MemoryAlloc
from amitools.fd import read_lib_fd
from amitools.vamos.machine.opcodes import op_jmp


def libcore_patch_multi_trap_test(capsys):
    name = "vamostest.library"
    impl = VamosTestLibrary()
    fd = read_lib_fd(name)
    machine = MockMachine()
    ctx = LibCtx(machine)
    # create stub
    scanner = LibImplScanner()
    scan = scanner.scan(name, impl, fd)
    gen = LibStubGen()
    stub = gen.gen_stub(scan, ctx)
    # now patcher
    alloc = MemoryAlloc(ctx.mem)
    traps = machine.get_traps()
    p = LibPatcherMultiTrap(alloc, traps, stub)
    base_addr = 0x100
    p.patch_jump_table(base_addr)
    # lookup trap for function
    func = fd.get_func_by_name("PrintHello")
    bias = func.get_bias()
    func_addr = base_addr - bias
    # check that jump table has jump + addr
    op = ctx.mem.r16(func_addr)
    assert op == op_jmp
    trap_addr = ctx.mem.r32(func_addr + 2)
    # check jump target is trap
    op = ctx.mem.r16(trap_addr)
    assert op & 0xF000 == 0xA000
    # trigger trap
    traps.trigger(op)
    captured = capsys.readouterr()
    assert captured.out.strip().split("\n") == ["VamosTest: PrintHello()"]
    # remove traps
    p.cleanup()
    assert traps.get_num_traps() == 0
    assert alloc.is_all_free()
