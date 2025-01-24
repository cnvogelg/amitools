import time
from amitools.vamos.astructs import LONG
from amitools.vamos.libstructs import TimeRequestStruct
from amitools.vamos.libtypes import TimeVal
from amitools.vamos.lib.TimerDevice import TimerDevice


def gen_timer_task(timer_func):
    def task(ctx, task):
        # get exec library
        exec_proxy = ctx.proxies.get_exec_lib_proxy()

        # alloc timer io req
        req = TimeRequestStruct.alloc(ctx.alloc)
        assert req is not None

        # open timer device
        res = exec_proxy.OpenDevice("timer.device", 0, req.addr, 0)
        assert res == 0

        # get proxy for device
        base_addr = req.node.device.aptr
        tdev = ctx.proxies.open_lib_proxy_addr(base_addr)
        assert tdev is not None

        # now run func using timer
        timer_func(ctx, tdev, req)

        # free proxy
        ctx.proxies.close_lib_proxy(tdev)

        # close device
        exec_proxy.CloseDevice(req.addr)

        # free req
        req.free()

        return 0

    return task


def pytask_timer_read_eclock_test(vamos_task):
    """check GetEClock via Python"""

    def timer_func(ctx, timer_dev, io_req):
        # alloc time struct
        tv = TimeVal.alloc(ctx.alloc)
        assert tv is not None

        # call lib func
        res = timer_dev.ReadEClock(tv)
        assert res == TimerDevice.ECLOCK_HZ
        secs, micro = tv.get_time_val()
        ts_last = secs << 32 | micro

        for i in range(100):
            # call lib func
            res = timer_dev.ReadEClock(tv)
            assert res == TimerDevice.ECLOCK_HZ
            secs, micro = tv.get_time_val()
            ts = secs << 32 | micro

            # assert monotonic time stamp
            assert ts > ts_last

            ts_last = ts

        # free timeval
        tv.free()

    task = gen_timer_task(timer_func)
    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_timer_get_sys_time_test(vamos_task):
    """check GetSysTime via Python"""

    def timer_func(ctx, timer_dev, io_req):
        # alloc time struct
        tv = TimeVal.alloc(ctx.alloc)
        assert tv is not None

        # call lib func
        timer_dev.GetSysTime(tv)
        secs, micro = tv.get_time_val()
        ts_last = secs + (micro / 1_000_000)

        for i in range(100):
            # call lib func
            timer_dev.GetSysTime(tv)
            secs, micro = tv.get_time_val()
            ts = secs + (micro / 1_000_000)

            # assert monotonic time stamp
            assert ts > ts_last

            ts_last = ts

        # free timeval
        tv.free()

    task = gen_timer_task(timer_func)
    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_timer_add_time_test(vamos_task):
    """check AddTime via Python"""

    def timer_func(ctx, timer_dev, io_req):
        # alloc time struct
        dest = TimeVal.alloc(ctx.alloc)
        assert dest is not None
        src = TimeVal.alloc(ctx.alloc)
        assert src is not None

        # without overflow
        dest.set_time_val(21, 1234)
        src.set_time_val(42, 4567)
        timer_dev.AddTime(dest, src)
        assert dest.get_time_val() == (21 + 42, 1234 + 4567)

        # with overflow
        dest.set_time_val(21, 500_000)
        src.set_time_val(42, 500_000)
        timer_dev.AddTime(dest, src)
        assert dest.get_time_val() == (21 + 42 + 1, 0)

        # free timeval
        src.free()
        dest.free()

    task = gen_timer_task(timer_func)
    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_timer_sub_time_test(vamos_task):
    """check SubTime via Python"""

    def timer_func(ctx, timer_dev, io_req):
        # alloc time struct
        dest = TimeVal.alloc(ctx.alloc)
        assert dest is not None
        src = TimeVal.alloc(ctx.alloc)
        assert src is not None

        # without underflow
        dest.set_time_val(42, 4567)
        src.set_time_val(21, 1234)
        timer_dev.SubTime(dest, src)
        assert dest.get_time_val() == (42 - 21, 4567 - 1234)

        # with underflow
        dest.set_time_val(42, 1234)
        src.set_time_val(21, 4567)
        timer_dev.SubTime(dest, src)
        assert dest.get_time_val() == (42 - 21 - 1, 1234 + 1_000_000 - 4567)

        # free timeval
        src.free()
        dest.free()

    task = gen_timer_task(timer_func)
    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_timer_cmp_time_test(vamos_task):
    """check CmpTime via Python"""

    def timer_func(ctx, timer_dev, io_req):
        # alloc time struct
        dest = TimeVal.alloc(ctx.alloc)
        assert dest is not None
        src = TimeVal.alloc(ctx.alloc)
        assert src is not None

        # dest>src -> -1
        dest.set_time_val(42, 4567)
        src.set_time_val(21, 1234)
        res = timer_dev.CmpTime(dest, src)
        assert res == 0xFFFFFFFF

        # dest>src -> -1
        dest.set_time_val(21, 4567)
        src.set_time_val(21, 1234)
        res = timer_dev.CmpTime(dest, src)
        assert res == 0xFFFFFFFF

        # dest<src -> 1
        dest.set_time_val(21, 1234)
        src.set_time_val(42, 4567)
        res = timer_dev.CmpTime(dest, src)
        assert res == 1

        # dest<src -> 1
        dest.set_time_val(42, 1234)
        src.set_time_val(42, 4567)
        res = timer_dev.CmpTime(dest, src)
        assert res == 1

        # dest==src -> 0
        dest.set_time_val(21, 1234)
        src.set_time_val(21, 1234)
        res = timer_dev.CmpTime(dest, src)
        assert res == 0

        # free timeval
        src.free()
        dest.free()

    task = gen_timer_task(timer_func)
    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]
