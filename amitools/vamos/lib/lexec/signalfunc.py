from amitools.vamos.astructs import BYTE
from amitools.vamos.log import log_exec

from .funcbase import FuncBaseMixin


# private ExecBase->SysFlags bits, see exec/execbase.inc
SFF_QuantumOver = 1 << 14
SFF_AttnSwitch = 1 << 15
SFF_RESCHEDULE = SFF_QuantumOver | SFF_AttnSwitch


class SignalMixin(FuncBaseMixin):
    """exec.library signal LVOs (fd banner: tasks / signals)."""

    def AllocSignal(self, ctx, signal_num: BYTE):
        return self.alloc_signal(signal_num.val)

    def FreeSignal(self, ctx, signal_num: BYTE):
        return self.free_signal(signal_num.val)

    def SetSignal(self, ctx, new_signals, signal_mask):
        return self.set_signal(new_signals, signal_mask)

    def Signal(self, ctx, task, signals):
        self.signal(task, signals)

    def Wait(self, ctx, signal_set):
        return self.wait(signal_set)

    # ----- internal -----

    def alloc_signal(self, sig_num):
        task = self.get_my_ami_task()
        old_mask = task.sig_alloc.val
        new_signal = sig_num
        if new_signal == -1:
            # find a free signal slot
            for bit in range(32):
                new_mask = 1 << bit
                if (old_mask & new_mask) == 0:
                    new_signal = bit
                    break
        else:
            # is pre selected signal free?
            new_mask = 1 << new_signal
            if (old_mask & new_mask) != 0:
                new_signal = -1
        # signal is ok. set it
        if new_signal != -1:
            task.sig_alloc.val |= 1 << new_signal
            final_mask = task.sig_alloc.val
        else:
            final_mask = old_mask
        log_exec.info(
            "AllocSignal(%d) for task %s -> %d (sig_mask %08x)",
            sig_num,
            task,
            new_signal,
            final_mask,
        )
        return new_signal

    def free_signal(self, sig_num):
        task = self.get_my_ami_task()
        # invalid signal?
        if sig_num == -1:
            log_exec.warning("FreeSignal(%d) for task %s?!", sig_num, task)
            return
        # check if signal is really set?
        old_mask = task.sig_alloc.val
        sig_mask = 1 << sig_num
        if (sig_mask & old_mask) == 0:
            log_exec.warning(
                "FreeSignal(%d) for task %s not set: sig_mask=%08x!",
                sig_num,
                task,
                old_mask,
            )
            return
        # ok, signal can be cleared
        task.sig_alloc.val = old_mask & ~sig_mask
        new_mask = task.sig_alloc.val
        log_exec.info(
            "FreeSignal(%d) for task %s -> sig_mask=%08x",
            sig_num,
            task,
            new_mask,
        )

    def set_signal(self, new_signals, signal_mask):
        # set signals via the scheduler task
        sched_task = self.get_my_sched_task()
        old_signals = sched_task.set_signal(new_signals, signal_mask)
        # just to be sure dump task val
        task = self.get_my_ami_task()
        real_mask = task.sig_recvd.val
        log_exec.info(
            "SetSignals: new_signals=%08x signal_mask=%08x "
            "old_signals=%08x real_mask=%08x",
            new_signals,
            signal_mask,
            old_signals,
            real_mask,
        )
        return old_signals

    def signal(self, task_addr, signals):
        def pred_func(task):
            return task.map_task.get_ami_task().addr == task_addr

        sched_task = self.get_my_sched_task()
        if sched_task is not None:
            other_task = sched_task.find_task_pred_func(pred_func)
        else:
            # no task is currently running (e.g. a handler is started from
            # Python): search the scheduler directly
            scheduler = getattr(self.ctx, "scheduler", None)
            other_task = scheduler.find_task_pred_func(pred_func) if scheduler else None
        if other_task:
            log_exec.info(
                "Signal(task=%08x, signals=%08x) -> task=%s",
                task_addr,
                signals,
                other_task,
            )
            other_task.set_signal(signals, signals)
        else:
            log_exec.info(
                "Signal(task=%08x, signals=%08x) -> not found!", task_addr, signals
            )

    def wait(self, signal_set):
        sched_task = self.get_my_sched_task()
        log_exec.info("Wait(%08x): enter", signal_set)
        got_signals = sched_task.wait(signal_set)
        log_exec.info("Wait(%08x): left -> %08x", signal_set, got_signals)
        return got_signals

    def forbid(self):
        sched_task = self.get_my_sched_task()
        cnt = sched_task.forbid()
        log_exec.info("Forbid (cnt=%d)", cnt)

    def permit(self):
        sched_task = self.get_my_sched_task()
        # a reschedule request in ExecBase->SysFlags, e.g. from sched_yield(),
        # is honored when the forbidden state ends, like an expired time slice
        if sched_task.forbid_cnt == 1:
            sys_flags = self.exec_lib.sys_flags.val
            if sys_flags & SFF_AttnSwitch:
                self.exec_lib.sys_flags.val = sys_flags & ~SFF_RESCHEDULE
                sched_task.request_reschedule()
        cnt = sched_task.permit()
        log_exec.info("Permit (cnt=%d)", cnt)
