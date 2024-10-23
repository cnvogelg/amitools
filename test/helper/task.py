from amitools.vamos.main import main_run
from amitools.vamos.maptask import MappedTask, MappedProcess
from amitools.vamos.schedule import PythonTask


class VamosTask:
    def run(self, func_list, process=False):
        def task_gen(cfg, task_ctx):
            result = []
            for func in func_list:
                name = str(func)
                if process:
                    task = MappedTask.from_python_code(task_ctx, name, func)
                    result.append(task)
                else:
                    proc = MappedProcess.from_python_code(task_ctx, name, func)
                    result.append(proc)
            return result

        exit_codes = main_run(task_gen, args=["foo"])
        assert exit_codes is not None
        return exit_codes
