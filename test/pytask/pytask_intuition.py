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


def pytask_intuition_easy_request_args_test(vamos_task):
    def intuition_func(ctx, intuition_lib):
        text = ctx.alloc.alloc_cstr("sfs startup")
        easy = ctx.alloc.alloc_memory(20)
        ctx.mem.w32(easy.addr + 12, text.addr)
        ctx.mem.w32(easy.addr + 16, 0)

        assert intuition_lib.EasyRequestArgs(0, easy.addr, 0, 0) == 1

        ctx.alloc.free_memory(easy)
        ctx.alloc.free_cstr(text)

    task = gen_intuition_task(intuition_func)
    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_intuition_easy_request_retry_does_not_loop_test(vamos_task):
    def intuition_func(ctx, intuition_lib):
        retry = ctx.alloc.alloc_cstr("Read %ld Error %lu on block %lu + %lu%s")
        other = ctx.alloc.alloc_cstr("Disk is full")
        gadgets = ctx.alloc.alloc_cstr("RETRY|CANCEL")
        easy = ctx.alloc.alloc_memory(20)
        ctx.mem.w32(easy.addr + 16, gadgets.addr)

        # The first requester selects RETRY, a repeat of it CANCEL.
        ctx.mem.w32(easy.addr + 12, retry.addr)
        assert intuition_lib.EasyRequestArgs(0, easy.addr, 0, 0) == 1
        assert intuition_lib.EasyRequestArgs(0, easy.addr, 0, 0) == 0
        assert intuition_lib.EasyRequestArgs(0, easy.addr, 0, 0) == 0

        # A different requester gets its first gadget once again.
        ctx.mem.w32(easy.addr + 12, other.addr)
        assert intuition_lib.EasyRequestArgs(0, easy.addr, 0, 0) == 1
        ctx.mem.w32(easy.addr + 12, retry.addr)
        assert intuition_lib.EasyRequestArgs(0, easy.addr, 0, 0) == 1

        ctx.alloc.free_memory(easy)
        ctx.alloc.free_cstr(gadgets)
        ctx.alloc.free_cstr(other)
        ctx.alloc.free_cstr(retry)

    task = gen_intuition_task(intuition_func)
    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]
