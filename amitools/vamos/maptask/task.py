from amitools.vamos.schedule import NativeTask, PythonTask, Stack
from amitools.vamos.libtypes import Task


class MappedTask:
    """the mapped task combines a scheduler task with an in-memory ami Task structure"""

    def __init__(
        self, task_ctx, sched_task, ami_task=None, code=None, pri=0, **kw_args
    ):
        if not ami_task:
            name = sched_task.get_name()
            ami_task = Task.alloc(task_ctx.alloc, name=name, **kw_args)
            ami_task.new_task(pri=pri)

        self.task_ctx = task_ctx
        self.sched_task = sched_task
        self.ami_task = ami_task
        self.code = code
        self.stack = sched_task.get_stack()

        # back refs
        self.sched_task.map_task = self
        self.ami_task.map_task = self

        self._setup_state_sync()
        self._setup_sigmask_sync()
        self._setup_stack_vals()

    def __repr__(self):
        return f"[MappedTask(sched_task={self.sched_task}, ami_task={self.ami_task})]"

    def _setup_state_sync(self):
        # install state hook to map state to mapped task value
        def map_state(task, state):
            self.ami_task.tc_State.val = state.name

        self.sched_task.set_state_callback(map_state)

    def _setup_sigmask_sync(self):
        def map_sigmask(task, sigmask_received, sigmask_wait):
            self.ami_task.tc_SigRecvd.val = sigmask_received
            self.ami_task.tc_SigWait.val = sigmask_wait

        self.sched_task.set_sigmask_callback(map_sigmask)

    def _setup_stack_vals(self):
        stack = self.sched_task.get_stack()
        ami_task = self.ami_task
        ami_task.tc_SPReg.aptr = stack.get_initial_sp()
        ami_task.tc_SPLower.aptr = stack.get_lower()
        ami_task.tc_SPUpper.aptr = stack.get_upper()

    def free(self):
        self.ami_task.free()
        self.stack.free()
        if self.code:
            self.code.free()

    def is_process(self):
        return False

    def get_ami_task(self):
        return self.ami_task

    def get_ami_process(self):
        return None

    def get_sched_task(self):
        return self.sched_task

    def get_code(self):
        return self.code

    def get_stack(self):
        return self.stack

    @classmethod
    def from_native_code(cls, task_ctx, name, code, stack_size=4096, **kw_args):
        alloc = task_ctx.alloc
        stack = Stack.alloc(alloc, stack_size)
        sched_task = NativeTask(name, task_ctx.machine, stack, code)
        return cls.from_sched_task(task_ctx, name, sched_task, code=code, **kw_args)

    @classmethod
    def from_python_code(cls, task_ctx, name, run_func, stack_size=4096, **kw_args):
        alloc = task_ctx.alloc
        stack = Stack.alloc(alloc, stack_size)

        def adapter(task):
            return run_func(task_ctx, task)

        sched_task = PythonTask(name, task_ctx.machine, stack, adapter)
        return cls.from_sched_task(task_ctx, name, sched_task, **kw_args)

    @classmethod
    def from_sched_task(cls, task_ctx, name, sched_task, **kw_args):
        return cls(task_ctx, sched_task, **kw_args)
