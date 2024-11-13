def pytask_self_simple_task_test(vamos_task):
    """check if pytask feature works"""

    def task1(ctx, task):
        return 11

    def task2(ctx, task):
        return 22

    exit_codes = vamos_task.run([task1, task2])
    assert exit_codes == [11, 22]


def pytask_self_simple_process_test(vamos_task):
    """check if pytask feature works"""

    def proc1(ctx, task):
        return 42

    def proc2(ctx, task):
        return 23

    exit_codes = vamos_task.run([proc1, proc2], process=True)
    assert exit_codes == [42, 23]


def pytask_self_exec_proxy_test(vamos_task):
    def task(ctx, task):
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        # allocate some memory
        size = 1024
        mem = exec_proxy.AllocMem(size, 0)
        assert mem != 0
        exec_proxy.FreeMem(mem, size)
        return 42

    exit_codes = vamos_task.run([task])
    assert exit_codes[0] == 42


def pytask_self_dos_proxy_test(vamos_task):
    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        # IoErr
        err = dos_proxy.IoErr()
        assert err == 0
        return 42

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes[0] == 42


def pytask_self_vlib_proxy_test(vamos_task):
    def task(ctx, task):
        # try to open vamos lib
        vlib = ctx.proxies.open_lib_proxy("vamostest.library")
        assert vlib is not None
        # call lib func
        result = vlib.Add(21, 42)
        assert result == 63
        # close lib
        ctx.proxies.close_lib_proxy(vlib)
        return 42

    exit_codes = vamos_task.run([task])
    assert exit_codes[0] == 42
