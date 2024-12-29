import time
from amitools.vamos.libstructs import TimeValStruct, TimeRequestStruct
from amitools.vamos.lib.TimerDevice import TimerDevice


def pytask_timer_eclock_test(vamos_task):
    """check GetEClock of Python"""

    def task(ctx, task):
        # get exec library
        exec_proxy = ctx.proxies.get_exec_lib_proxy()

        # alloc time struct
        tv = TimeValStruct.alloc(ctx.alloc)
        assert tv is not None

        # alloc timer io req
        req = TimeRequestStruct.alloc(ctx.alloc)
        assert req is not None

        prox = ctx.proxies.open_lib_proxy("timer.device")
        print(f"prox: addr={prox.base_addr:08x}")

        # open timer device
        res = exec_proxy.OpenDevice("timer.device", 0, req.addr, 0)
        assert res == 0

        # get proxy for device
        base_addr = req.node.device.aptr
        tdev = ctx.proxies.open_lib_proxy_addr(base_addr)
        assert tdev is not None

        # call lib func
        res = tdev.ReadEClock(tv.addr)
        assert res == TimerDevice.ECLOCK_HZ
        ts_last = tv.secs.val << 32 | tv.micro.val

        for i in range(100):
            # call lib func
            res = tdev.ReadEClock(tv.addr)
            assert res == TimerDevice.ECLOCK_HZ
            ts = tv.secs.val << 32 | tv.micro.val

            # assert monotonic time stamp
            assert ts > ts_last

            ts_last = ts

        # free proxy
        ctx.proxies.close_lib_proxy(tdev)

        # close device
        exec_proxy.CloseDevice(req.addr)

        # free req
        req.free()

        # free timeval
        tv.free()

        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]
