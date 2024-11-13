from amitools.vamos.machine import Machine, Code
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.schedule import Scheduler, TaskState, NativeTask, PythonTask
from amitools.vamos.maptask import MappedProcess
from amitools.vamos.libtypes import Process
from amitools.vamos.machine.opcodes import *
from amitools.vamos.machine.regs import *


class Ctx:
    def __init__(self):
        self.machine = Machine()
        self.alloc = MemoryAlloc.for_machine(self.machine)

    def cleanup(self):
        assert self.alloc.is_all_free()
        self.machine.cleanup()


def setup():
    return Ctx()


def cleanup(ctx):
    ctx.cleanup()


class MyNativeProcess:
    def __init__(self, ctx, name=None, **code_kw_args):
        if name is None:
            name = "task"
        self.ctx = ctx
        self.name = name
        self.stack = ctx.alloc.alloc_memory(4096, name + "_Stack")
        self.prog = ctx.alloc.alloc_memory(1024, name + "_Code")
        self.sp = self.stack.addr
        self.pc = self.prog.addr
        self.code = Code(self.pc, self.sp, **code_kw_args)
        self.sched_task = NativeTask(name, ctx.machine, self.code)
        self.ami_proc = Process.alloc(ctx.alloc, name=name)
        self.map_proc = MappedProcess(self.sched_task, self.ami_proc)

    def free(self):
        self.ami_proc.free()
        self.ctx.alloc.free_memory(self.stack)
        self.ctx.alloc.free_memory(self.prog)


class MyPythonProcess:
    def __init__(self, ctx, func=None, name=None, **code_kw_args):
        if name is None:
            name = "task"
        self.ctx = ctx
        self.name = name
        self.func = func
        self.stack = ctx.alloc.alloc_memory(4096, name + "_Stack")
        self.sp = self.stack.addr
        self.sched_task = PythonTask(name, ctx.machine, self.func, self.sp)
        self.ami_proc = Process.alloc(ctx.alloc, name=name)
        self.map_proc = MappedProcess(self.sched_task, self.ami_proc)

    def free(self):
        self.ami_proc.free()
        self.ctx.alloc.free_memory(self.stack)


def create_both_processes(ctx, name=None):
    return [
        MyNativeProcess(ctx, name=name),
        MyPythonProcess(ctx, name=name),
    ]


def check_process(proc, name):
    # check ami values
    ami_proc = proc.get_ami_process()
    assert ami_proc.task.name.str == name
    # check sched_task
    sched_task = proc.get_sched_task()
    assert sched_task.get_name() == name


# test allocation of map task


def maptask_process_alloc_test():
    ctx = setup()
    for proc_ctx in create_both_processes(ctx, name="foo"):
        map_proc = proc_ctx.map_proc
        check_process(map_proc, "foo")
        # clean up
        proc_ctx.free()
    cleanup(ctx)


def maptask_process_state_test():
    ctx = setup()
    for proc_ctx in create_both_processes(ctx):
        map_proc = proc_ctx.map_proc
        # set state and check if mapped state was updated
        map_proc.get_sched_task().set_state(TaskState.TS_RUN)
        assert str(map_proc.get_ami_task().tc_State) == TaskState.TS_RUN.name
        assert str(map_proc.get_ami_process().task.tc_State) == TaskState.TS_RUN.name
        # clean up
        proc_ctx.free()
    cleanup(ctx)


def maptask_process_sigmask_test():
    ctx = setup()
    for proc_ctx in create_both_processes(ctx):
        map_proc = proc_ctx.map_proc
        # set state and check if mapped state was updated
        map_proc.get_sched_task().set_signal(2, 2)
        assert map_proc.get_ami_task().tc_SigRecvd.val == 2
        assert map_proc.get_ami_process().task.tc_SigRecvd.val == 2
        # clean up
        proc_ctx.free()
    cleanup(ctx)
