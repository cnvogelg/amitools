from amitools.vamos.libtypes import Task


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
