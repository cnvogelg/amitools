import pytest


@pytest.mark.parametrize("signal", [-1, 24])
def pytask_exec_signal_alloc_free_any_test(vamos_task, signal):
    def task(ctx, task):
        ami_task = task.map_task.get_ami_task()

        # get exec library
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        # alloc any signal
        sig = exec_lib.AllocSignal(signal)
        assert sig > 15 and sig < 32
        if signal != -1:
            assert sig == signal

        # check that mask is set
        mask = 1 << sig
        assert (ami_task.sig_alloc.val & mask) == mask

        # try to set signal
        assert exec_lib.SetSignal(mask, mask) == 0
        assert exec_lib.SetSignal(0, 0) == mask
        assert ami_task.sig_recvd.val == mask

        assert exec_lib.SetSignal(0, mask) == mask
        assert exec_lib.SetSignal(0, 0) == 0
        assert ami_task.sig_recvd.val == 0

        exec_lib.FreeSignal(sig)

        # check that mask is cleared
        mask = 1 << sig
        assert (ami_task.sig_alloc.val & mask) == 0

        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_exec_signal_wait_test(vamos_task):
    def task1(ctx, task):
        # get exec library
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        # simply wait for signal
        got_signals = exec_lib.Wait(3)
        assert got_signals == 1

        return 0

    def task2(ctx, task):
        # get exec library
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        # find task by name
        addr = exec_lib.FindTask("task1")
        assert addr != 0

        # set signal
        exec_lib.Signal(addr, 1)

        return 0

    exit_codes = vamos_task.run([task1, task2])
    assert exit_codes == [0, 0]
