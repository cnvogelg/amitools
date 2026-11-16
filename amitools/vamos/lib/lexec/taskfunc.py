from amitools.vamos.libtypes import Task
from amitools.vamos.log import log_exec
from .funcbase import FuncBase


class TaskFunc(FuncBase):
    def set_task_pri(self, task, priority):
        if task is None:
            log_exec.warning("SetTaskPri: NULL task")
            return 0
        old_pri = task.pri.val
        # tc_Node.ln_Pri is a signed byte: store the low byte of the
        # given priority sign-extended again
        new_pri = priority & 0xFF
        if new_pri >= 0x80:
            new_pri -= 0x100
        task.pri.val = new_pri
        log_exec.info(
            "SetTaskPri: task=%s priority=%d -> old=%d", task, new_pri, old_pri
        )
        return old_pri

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
