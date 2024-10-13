from amitools.vamos.machine import Machine, REG_D0, op_nop, op_rts
from amitools.vamos.schedule import NativeTask, VamosTask, Stack
from amitools.vamos.mem import MemoryAlloc


def setup():
    machine = Machine()
    alloc = MemoryAlloc.for_machine(machine)
    return machine, alloc


def create_native_task(
    machine, alloc, pc, start_regs=None, return_regs=None, name=None
):
    if name is None:
        name = "task"
    stack = Stack.alloc(alloc, 4096)
    task = NativeTask(name, machine, stack, pc, start_regs, return_regs)
    return task


def create_vamos_task(machine, alloc, run, name=None):
    if name is None:
        name = "task"
    stack = Stack.alloc(alloc, 4096)
    task = VamosTask(name, machine, stack, run)
    return task


def schedule_task_native_simple_test():
    machine, alloc = setup()
    mem = alloc.get_mem()
    pc = machine.get_scratch_begin()
    mem.w16(pc, op_nop)
    mem.w16(pc + 2, op_rts)
    task = create_native_task(machine, alloc, pc, {REG_D0: 42})
    result = task.start()
    task.free()
    assert task.get_exit_code() == 42
    assert alloc.is_all_free()
    machine.cleanup()


def schedule_task_vamos_simple_test():
    machine, alloc = setup()
    mem = alloc.get_mem()

    def my_func(task):
        return 42

    task = create_vamos_task(machine, alloc, my_func)
    result = task.start()
    task.free()
    assert task.get_exit_code() == 42
    assert alloc.is_all_free()
    machine.cleanup()
