from amitools.vamos.machine import Machine, REG_D0, op_nop, op_rts
from amitools.vamos.schedule import NativeTask, PythonTask, Stack, Code
from amitools.vamos.mem import MemoryAlloc


def setup():
    machine = Machine()
    alloc = MemoryAlloc.for_machine(machine)
    return machine, alloc


def create_native_task(machine, alloc, name=None, **kw_args):
    if name is None:
        name = "task"
    stack = Stack.alloc(alloc, 4096)
    code = Code.alloc(alloc, 100, **kw_args)
    task = NativeTask(name, machine, stack, code)
    return task


def create_python_task(machine, alloc, func, name=None):
    if name is None:
        name = "task"
    stack = Stack.alloc(alloc, 4096)
    task = PythonTask(name, machine, stack, func)
    return task


def schedule_task_native_simple_test():
    machine, alloc = setup()
    mem = alloc.get_mem()
    task = create_native_task(machine, alloc, start_regs={REG_D0: 42})

    pc = task.get_start_pc()
    mem.w16(pc, op_nop)
    mem.w16(pc + 2, op_rts)

    result = task.start()
    task.free()
    assert task.get_exit_code() == 42
    assert alloc.is_all_free()
    machine.cleanup()


def schedule_task_python_simple_test():
    machine, alloc = setup()
    mem = alloc.get_mem()

    def my_func(task):
        return 42

    task = create_python_task(machine, alloc, my_func)
    result = task.start()
    task.free()
    assert task.get_exit_code() == 42
    assert alloc.is_all_free()
    machine.cleanup()
