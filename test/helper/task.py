from amitools.vamos.main import main_run
from amitools.vamos.maptask import MappedTask
from amitools.vamos.schedule import PythonTask


class VamosTask:
    def run(self, func_list):
        def task_gen(cfg, task_ctx):
            result = []
            for func in func_list:
                name = str(func)
                task = MappedTask.from_python_code(task_ctx, name, func)
                result.append(task)
            return result

        exit_codes = main_run(task_gen, args=["foo"])
        assert exit_codes is not None
        return exit_codes
