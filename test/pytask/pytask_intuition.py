import time
from amitools.vamos.libstructs import TimeValStruct
from amitools.vamos.lib.TimerDevice import TimerDevice


def gen_intuition_task(intuition_func):
    def task(ctx, task):
        # get exec library
        intuition_proxy = ctx.proxies.open_lib_proxy("intuition.library")
        assert intuition_proxy is not None

        # now run func using timer
        intuition_func(ctx, intuition_proxy)

        # free proxy
        ctx.proxies.close_lib_proxy(intuition_proxy)

        return 0

    return task


def pytask_intuition_current_time_test(vamos_task):
    def intuition_func(ctx, intuition_lib):
        # alloc time struct
        tv = TimeValStruct.alloc(ctx.alloc)
        assert tv is not None
        addr = tv.addr

        # call lib func
        intuition_lib.CurrentTime(addr, addr + 4)
        ts_last = tv.secs.val + (tv.micro.val / 1_000_000)

        for i in range(100):
            # call lib func
            intuition_lib.CurrentTime(addr, addr + 4)
            ts = tv.secs.val + (tv.micro.val / 1_000_000)

            # assert monotonic time stamp
            assert ts >= ts_last

            ts_last = ts

        # free timeval
        tv.free()

    task = gen_intuition_task(intuition_func)
    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]
