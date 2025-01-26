from .funcbase import FuncBase
from amitools.vamos.log import log_exec


class SignalFunc(FuncBase):
    def alloc_signal(self, sig_num):
        task = self.get_my_task()
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
        task = self.get_my_task()
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
        task = self.get_my_task()
        real_mask = task.sig_recvd.val
        log_exec.info(
            "SetSignals: new_signals=%08x signal_mask=%08x old_signals=%08x real_mask=%08x",
            new_signals,
            signal_mask,
            old_signals,
            real_mask,
        )
        return old_signals
