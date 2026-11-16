from amitools.vamos.libtypes import Task


def pytask_exec_task_yield_sysflags_test(vamos_task):
    order = []

    def task1(ctx, task):
        exec_lib = ctx.proxies.get_exec_lib_proxy()
        vlib = ctx.lib_mgr.get_vlib_by_name("exec.library")
        sys_flags = vlib.get_impl().exec_lib.sys_flags

        # a sched_yield() style reschedule request while forbidden
        exec_lib.Forbid()
        sys_flags.val |= (1 << 15) | (1 << 14)
        exec_lib.Permit()

        # Permit() handled the request and let task2 run first
        assert sys_flags.val & ((1 << 15) | (1 << 14)) == 0
        order.append(1)
        return 0

    def task2(ctx, task):
        order.append(2)
        return 0

    exit_codes = vamos_task.run([task1, task2])
    assert exit_codes == [0, 0]
    assert order == [2, 1]


def pytask_exec_task_yield_sysflags_nested_forbid_test(vamos_task):
    order = []
    reschedule = (1 << 15) | (1 << 14)

    def task1(ctx, task):
        exec_lib = ctx.proxies.get_exec_lib_proxy()
        vlib = ctx.lib_mgr.get_vlib_by_name("exec.library")
        sys_flags = vlib.get_impl().exec_lib.sys_flags

        # keep the request pending until the last nested Forbid() ends
        exec_lib.Forbid()
        exec_lib.Forbid()
        sys_flags.val |= reschedule
        exec_lib.Permit()
        assert sys_flags.val & reschedule == reschedule

        exec_lib.Permit()
        assert sys_flags.val & reschedule == 0
        order.append(1)
        return 0

    def task2(ctx, task):
        order.append(2)
        return 0

    exit_codes = vamos_task.run([task1, task2])
    assert exit_codes == [0, 0]
    assert order == [2, 1]


def pytask_exec_task_find_task_test(vamos_task):
    def task(ctx, task):
        ami_task = task.map_task.get_ami_task()

        # get exec library
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        # find myself
        addr = exec_lib.FindTask(None)
        assert ami_task.addr == addr

        # find myself by name
        addr = exec_lib.FindTask("task")
        assert ami_task.addr == addr

        # find other task
        addr = exec_lib.FindTask("other_task")
        assert type(addr) is Task

        # find waiting task
        addr = exec_lib.FindTask("wait_task")
        assert type(addr) is Task
        sched_task = task.find_task("wait_task")
        assert sched_task is not None
        sched_task.set_signal(1, 1)

        return 0

    def other_task(ctx, task):
        ami_task = task.map_task.get_ami_task()

        # get exec library
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        while True:
            addr = exec_lib.FindTask("task")
            if addr is None:
                break

        return 0

    def wait_task(ctx, task):
        task.wait(1)
        return 0

    exit_codes = vamos_task.run([task, other_task, wait_task], args="-lexec:info")
    assert exit_codes == [0, 0, 0]
