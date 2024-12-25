from amitools.vamos.main import main
from amitools.vamos.task import ExecTask, DosProcess
from amitools.vamos.mode import BaseMode


class VamosTask:
    def run(self, func_list, process=False):
        def wrap(ctx, func):
            def wrap_func(task):
                return func(ctx, task)

            return wrap_func

        def task_gen(mode_ctx):
            result = []
            for func in func_list:
                name = str(func)
                if process:
                    dos_ctx = mode_ctx.dos_ctx
                    wrap_func = wrap(dos_ctx, func)
                    proc = DosProcess(
                        dos_ctx.machine, dos_ctx.alloc, name, func=wrap_func
                    )
                    result.append(proc)
                else:
                    exec_ctx = mode_ctx.exec_ctx
                    wrap_func = wrap(exec_ctx, func)
                    task = ExecTask(
                        exec_ctx.machine, exec_ctx.alloc, name, func=wrap_func
                    )
                    result.append(task)

            return result

        mode = BaseMode("task", task_gen)
        exit_codes = main(args=[], mode=mode, single_return_code=False)
        assert exit_codes is not None
        return exit_codes
