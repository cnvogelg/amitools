from .base import BaseMode
from amitools.vamos.lib.dos import Var
from amitools.vamos.lib.dos.Process import BinProcess
from amitools.vamos.log import log_proc


class ProcessModeBase(BaseMode):
    """shared logic for the modes that run a single DOS process.

    A concrete mode names itself and provides two hooks: ``make_process_args``
    turns the command config into a ``(binary, arg_str)`` pair (or ``None``)
    and ``make_process`` builds the process class it wants to run.
    """

    def __init__(self, name):
        def gen_task_list(mode_ctx):
            main_proc = self.create_proc(mode_ctx)
            if not main_proc:
                return None
            return [main_proc]

        super().__init__(name, gen_task_list)

    def create_proc(self, mode_ctx):
        proc_cfg = mode_ctx.proc_cfg
        cmd_cfg = proc_cfg.command

        # split the command config into binary and args
        proc_args = self.make_process_args(mode_ctx, cmd_cfg)
        if proc_args is None:
            return None
        binary, arg_str = proc_args
        log_proc.info("binary: %r", binary)
        log_proc.info("args:   %r", arg_str)

        # fetch stack
        stack_size = proc_cfg.stack * 1024
        log_proc.info("stack:  %d", stack_size)

        # cwd
        dos_ctx = mode_ctx.dos_ctx
        cwd = str(dos_ctx.path_mgr.get_cwd())
        log_proc.info("cwd:    %s", cwd)

        # setup main proc
        proc = self.make_process(dos_ctx, binary, arg_str, stack_size, cwd)
        if not proc.ok:
            return None
        self.setup_vars(dos_ctx, proc, proc_cfg.vars)
        return proc

    def make_process_args(self, mode_ctx, cmd_cfg):
        raise NotImplementedError

    def make_process(self, dos_ctx, binary, arg_str, stack_size, cwd):
        raise NotImplementedError

    def setup_vars(self, dos_ctx, proc, var_specs):
        """seed the process with AmigaDOS local variables.

        The emulated program starts with an empty variable table, so a
        program that expects one set by the shell, e.g. with "Set NAME
        value", has no way of seeing it.  Variables named here are put in
        place before the program runs, as that Set would have done.
        """
        if not var_specs:
            return
        dos_lib = dos_ctx.dos_lib
        # create_var() works on the current process, which is only set
        # once the task is scheduled, so point at ours for the duration
        old_proc = dos_ctx.process
        dos_ctx.set_cur_process(proc)
        try:
            for spec in var_specs:
                if "=" in spec:
                    name, value = spec.split("=", 1)
                else:
                    name, value = spec, ""
                node = Var.create_var_node(dos_lib, dos_ctx, name, 0)
                Var.set_var_node(dos_lib, dos_ctx, node, 0, len(value) + 1, value, 0)
                log_proc.info("set var: %s='%s'", name, value)
        finally:
            dos_ctx.set_cur_process(old_proc)


class ProcMode(ProcessModeBase):
    """run a single binary with a minimal CLI (the default ``proc`` mode)."""

    def __init__(self):
        super().__init__("proc")

    def make_process_args(self, mode_ctx, cmd_cfg):
        # make sure a command is given
        if len(cmd_cfg.args) == 0:
            log_proc.error("No command and args given!")
            return None
        return mode_ctx.proc_args.make_cmd_args(cmd_cfg)

    def make_process(self, dos_ctx, binary, arg_str, stack_size, cwd):
        return BinProcess(dos_ctx, binary, arg_str, stack_size=stack_size, cwd=cwd)
