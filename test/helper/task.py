from amitools.vamos.main import main_run
from amitools.vamos.task import ExecTask, DosProcess


class VamosTask:
    def run(self, func_list, process=False):
        def wrap(ctx, func):
            def wrap_func(task):
                return func(ctx, task)

            return wrap_func

        def task_gen(cfg, dos_ctx, exec_ctx):
            result = []
            for func in func_list:
                name = str(func)
                if process:
                    wrap_func = wrap(dos_ctx, func)
                    proc = DosProcess(
                        dos_ctx.machine, dos_ctx.alloc, name, func=wrap_func
                    )
                    result.append(proc)
                else:
                    wrap_func = wrap(exec_ctx, func)
                    task = ExecTask(
                        exec_ctx.machine, exec_ctx.alloc, name, func=wrap_func
                    )
                    result.append(task)

            return result

        exit_codes = main_run(task_gen, args=["foo"])
        assert exit_codes is not None
        return exit_codes
