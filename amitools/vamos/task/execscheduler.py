from amitools.vamos.schedule import SchedulerEvent
from amitools.vamos.libstructs import ExecLibraryStruct, TaskStruct
from amitools.vamos.libtypes.list_ import list_add_head, list_add_tail
from amitools.vamos.libtypes.node import remove_node


def _offset(struct, name):
    return struct.sdef.find_field_def_by_name(name).offset


# every task switch moves a task between exec's lists: do it in memory
_THIS_TASK = _offset(ExecLibraryStruct, "ThisTask")
_TASK_READY = _offset(ExecLibraryStruct, "TaskReady")
_TASK_WAIT = _offset(ExecLibraryStruct, "TaskWait")
_TC_NODE = _offset(TaskStruct, "tc_Node")


class ExecScheduler:
    """The ExecScheduler syns the scheduler state into the ExecLibrary"""

    def __init__(self, scheduler, exec_lib):
        self.scheduler = scheduler
        self.exec_lib = exec_lib
        self._mem = exec_lib._mem
        self._this_task = exec_lib.addr + _THIS_TASK
        self._task_ready = exec_lib.addr + _TASK_READY
        self._task_wait = exec_lib.addr + _TASK_WAIT
        # handle scheduler events
        self.old_task = None
        self.scheduler.set_event_callback(self.event_handler)

    def event_handler(self, event):
        ev = event.type
        # lookup scheduler and ami task
        sched_task = event.task
        if sched_task:
            ami_task = sched_task.map_task.ami_task
        else:
            ami_task = None

        mem = self._mem
        if ev == SchedulerEvent.Type.ACTIVE_TASK:
            # remove from task_ready
            if ami_task:
                remove_node(mem, ami_task.addr + _TC_NODE)
            # store in ThisTask
            mem.w32(self._this_task, ami_task.addr if ami_task is not None else 0)
        elif ev == SchedulerEvent.Type.READY_TASK:
            # add to task_ready
            list_add_head(mem, self._task_ready, ami_task.addr + _TC_NODE)
        elif ev == SchedulerEvent.Type.WAITING_TASK:
            # add to task_wait
            list_add_head(mem, self._task_wait, ami_task.addr + _TC_NODE)
        elif ev == SchedulerEvent.Type.WAKE_UP_TASK:
            # remove from task_wait and add to ready
            remove_node(mem, ami_task.addr + _TC_NODE)
            list_add_head(mem, self._task_ready, ami_task.addr + _TC_NODE)
        elif ev == SchedulerEvent.Type.ADD_TASK:
            list_add_tail(mem, self._task_ready, ami_task.addr + _TC_NODE)
