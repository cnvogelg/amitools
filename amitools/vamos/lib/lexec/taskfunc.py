from amitools.vamos.libtypes import Task
from amitools.vamos.log import log_exec
from .funcbase import FuncBase


class TaskFunc(FuncBase):
    def find_task(self, task_name):
        if task_name is None:
            addr = self.exec_lib.this_task.aptr
            log_exec.info("FindTask: me=%08x", addr)
            return Task(self.ctx.mem, addr)
        else:
            # this task?
            my_task = self.get_my_ami_task()
            if my_task.node.name.str == task_name:
                addr = my_task.addr
                log_exec.info("Find Task '%s': me=%08x", task_name, addr)
                return Task(self.ctx.mem, addr)
            # ready list?
            ready_list = self.exec_lib.task_ready
            for node in ready_list:
                if node.name.str == task_name:
                    addr = node.addr
                    log_exec.info("Find Task '%s': ready=%08x", task_name, addr)
                    return Task(self.ctx.mem, addr)
            # wait list?
            wait_list = self.exec_lib.task_wait
            for node in wait_list:
                if node.name.str == task_name:
                    addr = node.addr
                    log_exec.info("Find Task '%s': wait=%08x", task_name, addr)
                    return Task(self.ctx.mem, addr)
            log_exec.info("Find Task '%s': not found!")
            return None
