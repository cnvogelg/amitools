from amitools.vamos.machine import Machine, REG_D1, REG_D0
from amitools.vamos.schedule import Code
from amitools.vamos.mem import MemoryAlloc


def setup():
    machine = Machine()
    alloc = MemoryAlloc.for_machine(machine)
    return machine, alloc


def schedule_code_native_simple_test():
    machine, alloc = setup()
    mem = alloc.get_mem()

    code = Code.alloc(alloc, 100, start_regs={REG_D1: 23}, return_regs=[REG_D0, REG_D1])
    assert code.get_start_regs() == {REG_D1: 23}
    assert code.get_return_regs() == [REG_D0, REG_D1]
    code.free()

    assert alloc.is_all_free()
    machine.cleanup()
