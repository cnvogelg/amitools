from amitools.vamos.log import log_proc
from amitools.vamos.schedule import Stack, Task
from amitools.vamos.machine.regs import *


def run_sub_process(scheduler, proc):
    log_proc.info("start sub process: %s", proc)

    task = proc.get_task()

    scheduler.add_task(task)

    # return value
    run_state = task.get_run_state()
    ret_code = run_state.regs[REG_D0]
    log_proc.info("return from sub process: ret_code=%d", ret_code)

    # cleanup proc
    proc.free()

    return ret_code


def run_command(scheduler, process, start_pc, args_ptr, args_len, stack_size, reg_d1=0):
    ctx = process.ctx
    alloc = ctx.alloc
    new_stack = Stack.alloc(alloc, stack_size)
    # save old stack
    oldstack_upper = process.this_task.access.r_s("pr_Task.tc_SPLower")
    oldstack_lower = process.this_task.access.r_s("pr_Task.tc_SPUpper")
    # activate new stack
    process.this_task.access.w_s("pr_Task.tc_SPLower", new_stack.get_upper())
    process.this_task.access.w_s("pr_Task.tc_SPUpper", new_stack.get_lower())
    # NOTE: the Manx fexec and BPCL mess is not (yet) setup here.

    # setup sub task
    sp = new_stack.get_initial_sp()

    # new proc registers: d0=arg_len a0=arg_cptr
    # d2=stack_size.  this value is also in 4(sp) (see Process.init_stack), but
    # various C programs rely on it being present (1.3-3.1 at least have it).
    set_regs = {
        REG_D0: args_len,
        REG_D1: reg_d1,
        REG_A0: args_ptr,
        REG_D2: stack_size,
        REG_A2: ctx.odg_base,
        REG_A5: ctx.odg_base,
        REG_A6: ctx.odg_base,
    }
    get_regs = [REG_D0]
    task = Task("RunCommand", start_pc, new_stack, set_regs, get_regs)

    # run sub task
    scheduler.run_sub_task(task)

    # return value
    run_state = task.get_run_state()
    ret_code = run_state.regs[REG_D0]
    log_proc.info("return from RunCommand: ret_code=%d", ret_code)

    # restore stack values
    process.this_task.access.w_s("pr_Task.tc_SPLower", oldstack_lower)
    process.this_task.access.w_s("pr_Task.tc_SPUpper", oldstack_upper)

    # result code
    return ret_code
