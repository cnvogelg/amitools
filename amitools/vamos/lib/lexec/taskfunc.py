from amitools.vamos.astructs import CSTR, LONG
from amitools.vamos.libstructs import StackSwapStruct
from amitools.vamos.libtypes import Task
from amitools.vamos.log import log_exec
from amitools.vamos.machine import Code
from amitools.vamos.machine.regs import REG_A7
from amitools.vamos.schedule import NativeTask
from amitools.vamos.task.maptask import MappedTask

from .funcbase import FuncBaseMixin


class TaskMixin(FuncBaseMixin):
    """exec.library task LVOs (fd banner: tasks)."""

    def FindTask(self, ctx, task_name: CSTR) -> Task:
        return self.find_task(task_name.str)

    def SetTaskPri(self, ctx, task: Task, priority: LONG):
        return self.set_task_pri(task, int(priority))

    def SetExcept(self, ctx, newSignals, signalSet):
        """change the mask of signals that raise a task exception."""
        task = self.get_my_ami_task()
        old = task.sig_except.val
        task.sig_except.val = (old & ~signalSet) | (newSignals & signalSet)
        log_exec.info(
            "SetExcept(new=%08x, mask=%08x) -> old=%08x",
            newSignals,
            signalSet,
            old,
        )
        return old

    def AllocTrap(self, ctx, trapNum: LONG):
        return self.alloc_trap(int(trapNum))

    def FreeTrap(self, ctx, trapNum: LONG):
        self.free_trap(int(trapNum))

    def AddTask(self, ctx, task: Task, initPC, finalPC):
        """add an externally built Task to the scheduler.

        Only the simple case is supported: the task already owns a stack
        (tc_SPLower/tc_SPUpper/tc_SPReg) and runs native m68k code. The
        final PC is pushed as the initial return address, as exec does.
        """
        mapped = self.add_task(ctx, task, initPC, finalPC)
        if mapped is None:
            return 0
        return task.addr

    def RemTask(self, ctx, task: Task):
        """remove a task; NULL removes the current task."""
        if task is not None:
            task_addr = task.addr
        else:
            task_addr = self.exec_lib.this_task.aptr
        scheduler = getattr(ctx, "scheduler", None)
        sched_task = self.find_sched_task(scheduler, task_addr)
        if sched_task is None:
            log_exec.warning("RemTask(%06x): no scheduler task", task_addr)
            return
        if scheduler.get_running_task() is sched_task:
            # removing the current task: stop it right away
            scheduler.rem_task(sched_task)
        else:
            scheduler.terminate_task(sched_task)
        log_exec.info("RemTask(%06x)", task_addr)

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

    def alloc_trap(self, trap_num):
        task = self.get_my_ami_task()
        old = task.trap_alloc.val
        if trap_num < 0:
            # pick the first free trap bit
            new_trap = -1
            for bit in range(16):
                if (old & (1 << bit)) == 0:
                    new_trap = bit
                    break
            if new_trap == -1:
                log_exec.info("AllocTrap(-1) -> -1 (none free)")
                return -1
        else:
            mask = 1 << trap_num
            if old & mask:
                log_exec.info("AllocTrap(%d) -> -1 (in use)", trap_num)
                return -1
            new_trap = trap_num
        task.trap_alloc.val = old | (1 << new_trap)
        log_exec.info(
            "AllocTrap(%d) -> %d (mask=%04x)", trap_num, new_trap, task.trap_alloc.val
        )
        return new_trap

    def free_trap(self, trap_num):
        if trap_num == -1:
            return
        task = self.get_my_ami_task()
        task.trap_alloc.val = task.trap_alloc.val & ~(1 << trap_num)
        log_exec.info("FreeTrap(%d) -> mask=%04x", trap_num, task.trap_alloc.val)

    def add_task(self, ctx, task, init_pc, final_pc):
        scheduler = getattr(ctx, "scheduler", None)
        if scheduler is None:
            log_exec.warning("AddTask: no scheduler available")
            return None
        name = task.node.name.str or "Task"
        sp = task.sp_reg.aptr
        # exec makes the final PC the initial return address of the task
        if final_pc and sp:
            sp -= 4
            ctx.mem.w32(sp, final_pc)
            task.sp_reg.aptr = sp
        code = Code(init_pc, sp)
        sched_task = NativeTask(name, ctx.machine, code)
        mapped = MappedTask(sched_task, task)
        self._added_tasks.append(mapped)
        scheduler.add_task(sched_task)
        log_exec.info(
            "AddTask(%06x, initPC=%06x, finalPC=%06x) name=%s",
            task.addr,
            init_pc,
            final_pc,
            name,
        )
        return mapped

    def find_sched_task(self, scheduler, task_addr):
        if scheduler is None:
            return None

        def pred_func(sched_task):
            mapped = getattr(sched_task, "map_task", None)
            return mapped is not None and mapped.ami_task.addr == task_addr

        return scheduler.find_task_pred_func(pred_func)

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
