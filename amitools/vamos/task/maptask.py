from amitools.vamos.schedule import NativeTask, PythonTask
from amitools.vamos.libtypes import Task


class MappedTask:
    """the mapped task combines a scheduler task with an in-memory ami Task structure

    the scheduler task is needed to add a task to scheduling while the ami Task
    structure represents the task in Amiga memory for the OS and the applications.

    the main purpose of this class is to interlink both types of tasks and
    also establish an automatic sync of scheduling relevant parameteres
    like sigmask or task state.
    """

    def __init__(self, sched_task, ami_task, ami_proc=None):
        self.sched_task = sched_task
        self.ami_task = ami_task
        self.ami_proc = ami_proc

        # install back refs
        self.sched_task.map_task = self
        self.ami_task.map_task = self
        if self.ami_proc:
            self.ami_proc.map_task = self

        self._setup_state_sync()
        self._setup_sigmask_sync()

    def __repr__(self):
        return f"[MappedTask(sched_task={self.sched_task}, ami_task={self.ami_task}, ami_proc={self.ami_proc})]"

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

    def is_process(self):
        return self.ami_proc is not None

    def get_ami_task(self):
        return self.ami_task

    def get_ami_process(self):
        return self.ami_proc

    def get_sched_task(self):
        return self.sched_task
