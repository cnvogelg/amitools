from amitools.vamos.schedule import SchedulerEvent


class ExecScheduler:
    """The ExecScheduler syns the scheduler state into the ExecLibrary"""

    def __init__(self, scheduler, exec_lib):
        self.scheduler = scheduler
        self.exec_lib = exec_lib
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

        if ev == SchedulerEvent.Type.ACTIVE_TASK:
            # remove from task_ready
            if ami_task:
                ami_task.node.remove()
            # store in ThisTask
            self.exec_lib.this_task.ref = ami_task
        elif ev == SchedulerEvent.Type.READY_TASK:
            # add to task_ready
            self.exec_lib.task_ready.add_head(ami_task.node)
        elif ev == SchedulerEvent.Type.WAITING_TASK:
            # add to task_wait
            self.exec_lib.task_wait.add_head(ami_task.node)
        elif ev == SchedulerEvent.Type.WAKE_UP_TASK:
            # remove from task_wait and add to ready
            ami_task.node.remove()
            self.exec_lib.task_ready.add_head(ami_task.node)
        elif ev == SchedulerEvent.Type.ADD_TASK:
            self.exec_lib.task_ready.add_tail(ami_task.node)
