from amitools.vamos.machine import Machine, REG_D0, op_nop, op_rts
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.task import ExecTask
from amitools.vamos.loader import SegList


class Ctx:
    def __init__(self):
        self.machine = Machine()
        self.alloc = MemoryAlloc.for_machine(self.machine)
        self.mem = self.machine.get_mem()

    def cleanup(self):
        assert self.alloc.is_all_free()
        self.machine.cleanup()


def setup():
    return Ctx()


def cleanup(ctx):
    ctx.cleanup()


def task_exectask_simple_func_test():
    ctx = setup()

    def func(task):
        return 42

    task = ExecTask(ctx.machine, ctx.alloc, "foo", func=func)
    task.get_sched_task().start()
    assert task.get_sched_task().get_exit_code() == 42
    task.free()

    cleanup(ctx)


def task_exectask_simple_native_test():
    ctx = setup()

    seg_list = SegList.alloc(ctx.alloc, [4])
    pc = seg_list.get_start_pc()
    ctx.mem.w16(pc, op_nop)
    ctx.mem.w16(pc + 2, op_rts)

    regs = {REG_D0: 42}
    task = ExecTask(ctx.machine, ctx.alloc, "foo", seg_list=seg_list, start_regs=regs)
    task.get_sched_task().start()
    assert task.get_sched_task().get_exit_code() == 42
    task.free()

    cleanup(ctx)
