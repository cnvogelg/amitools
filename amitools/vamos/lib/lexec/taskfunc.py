from amitools.vamos.astructs import CSTR, LONG
from amitools.vamos.libstructs import StackSwapStruct
from amitools.vamos.libtypes import Task
from amitools.vamos.log import log_exec
from amitools.vamos.machine.regs import REG_A7

from .funcbase import FuncBaseMixin


class TaskMixin(FuncBaseMixin):
    """exec.library task LVOs (fd banner: tasks)."""

    def FindTask(self, ctx, task_name: CSTR) -> Task:
        return self.find_task(task_name.str)

    def SetTaskPri(self, ctx, task: Task, priority: LONG):
        return self.set_task_pri(task, int(priority))

    def StackSwap(self, ctx, new_stack: StackSwapStruct):
        stsw = new_stack
        # get new stack values
        new_lower = stsw.stk_Lower.aptr
        new_upper = stsw.stk_Upper.val
        new_pointer = stsw.stk_Pointer.aptr
        # retrieve current (old) stack
        stack = ctx.task.get_stack()
        old_lower = stack.get_lower()
        old_upper = stack.get_upper()
        old_pointer = ctx.cpu.r_reg(REG_A7)  # addr of sys call return
        # get adress of callee
        callee = ctx.mem.r32(old_pointer)
        # is a label attached to new addr
        if ctx.label_mgr:
            label = ctx.label_mgr.get_label(new_lower)
            if label is not None:
                label.name = label.name + "=Stack"
        # we report the old stack befor callee
        old_pointer += 4
        log_exec.info(
            "StackSwap: old(lower=%06x,upper=%06x,ptr=%06x) "
            "new(lower=%06x,upper=%06x,ptr=%06x)"
            % (old_lower, old_upper, old_pointer, new_lower, new_upper, new_pointer)
        )
        stsw.stk_Lower.aptr = old_lower
        stsw.stk_Upper.val = old_upper
        stsw.stk_Pointer.aptr = old_pointer
        # only owerwrite stack object but keep mem allocated (if any)
        stack.lower = new_lower
        stack.upper = new_upper
        stack.initial_sp = new_pointer
        # put callee's address on new stack
        new_pointer -= 4
        ctx.mem.w32(new_pointer, callee)
        # activate new stack
        ctx.cpu.w_reg(REG_A7, new_pointer)

    # ----- internal -----

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
