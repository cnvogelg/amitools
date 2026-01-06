from amitools.vamos.log import log_mode


class BaseMode:
    """base class for all modes"""

    def __init__(self, name, gen_task_list_func):
        self.name = name
        self.gen_task_list_func = gen_task_list_func

    def run(self, ctx):
        log_mode.info("begin mode '%s'", self.name)

        # generate tasks
        task_list = self.gen_task_list_func(ctx)
        if task_list is None:
            return [255]

        # add tasks to scheduler
        for task in task_list:
            sched_task = task.get_sched_task()
            log_mode.info("add task '%s'", sched_task.get_name())
            ctx.scheduler.add_task(sched_task)

        # --- main loop ---
        # schedule tasks...
        ctx.scheduler.schedule()

        # pick up exit codes and free task
        exit_codes = []
        for task in task_list:
            # return code is limited to 0-255
            sched_task = task.get_sched_task()
            exit_code = sched_task.get_exit_code()
            error = sched_task.get_error()
            if error:
                log_mode.error(
                    "done task '%s'. failed with %s", sched_task.get_name(), error
                )
                exit_code = 255
            else:
                log_mode.info(
                    "done task '%s'. exit code=%d", sched_task.get_name(), exit_code
                )

            exit_codes.append(exit_code)
            run_state = sched_task.get_run_result()
            log_mode.debug("run result: %r", run_state)

            # free task
            task.free()

        # only return first code
        log_mode.info("done mode '%s'. exit_code=%r", self.name, exit_codes)
        return exit_codes
