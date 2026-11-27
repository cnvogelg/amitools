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


def pytask_exec_task_forbid_wait_test(vamos_task):
    order = []

    def task1(ctx, task):
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        # sleeping on a signal in Forbid() must let task2 run and wake us
        exec_lib.Forbid()
        got = exec_lib.Wait(1)
        assert got == 1
        # the forbid state is restored when the task runs again
        assert task.is_forbidden()
        order.append(1)
        exec_lib.Permit()
        assert not task.is_forbidden()
        return 0

    def task2(ctx, task):
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        addr = exec_lib.FindTask("task1")
        assert addr != 0
        order.append(2)
        exec_lib.Signal(addr, 1)
        return 0

    exit_codes = vamos_task.run([task1, task2])
    assert exit_codes == [0, 0]
    assert order == [2, 1]


def pytask_exec_task_set_task_pri_test(vamos_task):
    def task(ctx, task):
        ami_task = task.map_task.get_ami_task()

        # get exec library
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        # changing the priority returns the old value
        assert ami_task.pri.val == 0
        old = exec_lib.SetTaskPri(ami_task, -5)
        assert old == 0
        assert ami_task.pri.val == -5

        # only the low byte is stored and returned sign-extended
        old = exec_lib.SetTaskPri(ami_task, 200)
        assert old == 0xFFFFFFFB
        assert ami_task.pri.val == -56

        old = exec_lib.SetTaskPri(ami_task, 0)
        assert old == 0xFFFFFFC8
        assert ami_task.pri.val == 0

        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_exec_task_set_except_trap_test(vamos_task):
    def task(ctx, task):
        ami_task = task.map_task.get_ami_task()
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        # SetExcept returns the old mask and updates the affected bits
        ami_task.sig_except.val = 0x0F
        old = exec_lib.SetExcept(0x30, 0x3C)
        assert old == 0x0F
        assert ami_task.sig_except.val == 0x33

        # traps are bits in tc_TrapAlloc
        assert ami_task.trap_alloc.val == 0
        assert exec_lib.AllocTrap(4) == 4
        assert ami_task.trap_alloc.val == 1 << 4
        # a specific trap already in use fails (-1 -> 0xFFFFFFFF in D0)
        assert exec_lib.AllocTrap(4) == 0xFFFFFFFF
        # -1 picks the first free trap
        assert exec_lib.AllocTrap(-1) == 0
        assert ami_task.trap_alloc.val == (1 << 4) | 1
        exec_lib.FreeTrap(4)
        assert ami_task.trap_alloc.val == 1

        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


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
        task.map_task.get_ami_task()

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
