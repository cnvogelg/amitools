from .funcbase import FuncBase
from amitools.vamos.log import log_exec


class SignalFunc(FuncBase):
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
            "SetSignals: new_signals=%08x signal_mask=%08x old_signals=%08x real_mask=%08x",
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
        other_task = sched_task.find_task_pred_func(pred_func)
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
        cnt = sched_task.permit()
        log_exec.info("Permit (cnt=%d)", cnt)
