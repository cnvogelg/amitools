from amitools.vamos.machine import Machine, Code, REG_D0, op_nop, op_rts
from amitools.vamos.schedule import NativeTask, PythonTask


def create_native_task(machine, pc, sp, name=None, **kw_args):
    if name is None:
        name = "task"
    code = Code(pc, sp, **kw_args)
    task = NativeTask(name, machine, code)
    return task


def create_python_task(machine, func, sp, name=None):
    if name is None:
        name = "task"
    task = PythonTask(name, machine, func, sp)
    return task


def schedule_task_native_simple_test():
    machine = Machine()

    pc = machine.get_scratch_begin()
    sp = machine.get_scratch_top()
    task = create_native_task(machine, pc, sp, set_regs={REG_D0: 42})

    mem = machine.get_mem()
    mem.w16(pc, op_nop)
    mem.w16(pc + 2, op_rts)

    exit_code = task.start()
    assert exit_code == 42
    assert task.get_exit_code() == 42

    machine.cleanup()


def schedule_task_python_simple_test():
    machine = Machine()

    def my_func(task):
        return 42

    sp = machine.get_scratch_top()
    task = create_python_task(machine, my_func, sp)

    exit_code = task.start()
    assert exit_code == 42
    assert task.get_exit_code() == 42

    machine.cleanup()
