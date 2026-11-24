from .base import BaseMode
from amitools.vamos.lib.dos import Var
from amitools.vamos.lib.dos.Process import BinProcess, ShellProcess
from amitools.vamos.log import log_proc


class ProcMode(BaseMode):
    def __init__(self):
        def gen_task_list(mode_ctx):
            main_proc = self.create_proc(mode_ctx)
            if not main_proc:
                return None
            return [main_proc]

        super().__init__("proc", gen_task_list)

    def create_proc(self, mode_ctx):
        proc_cfg = mode_ctx.proc_cfg
        cmd_cfg = proc_cfg.command
        # make sure a command is given
        if len(cmd_cfg.args) == 0:
            log_proc.error("No command and args given!")
            return None

        # split command into binary and args
        cmd_arg = mode_ctx.proc_args.make_cmd_args(cmd_cfg)
        if cmd_arg is None:
            return None
        cmd, arg_str = cmd_arg
        log_proc.info("binary: %r", cmd)
        log_proc.info("args:   %r", arg_str)

        # fetch stack
        stack_size = proc_cfg.stack * 1024
        log_proc.info("stack:  %d", stack_size)
        shell = proc_cfg.command.shell
        log_proc.info("shell:  %r", shell)

        # cwd
        dos_ctx = mode_ctx.dos_ctx
        cwd = str(dos_ctx.path_mgr.get_cwd())
        log_proc.info("cwd:    %s", cwd)

        # setup main proc
        if shell:
            # -x runs a shell seg; step 6 turns this into its own mode
            proc = ShellProcess(dos_ctx, cmd, arg_str, stack_size=stack_size, cwd=cwd)
        else:
            proc = BinProcess(dos_ctx, cmd, arg_str, stack_size=stack_size, cwd=cwd)
        if not proc.ok:
            return None
        self.setup_vars(dos_ctx, proc, proc_cfg.vars)
        return proc

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
