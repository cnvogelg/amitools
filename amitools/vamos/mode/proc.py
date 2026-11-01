import os

from .base import BaseMode
from amitools.vamos.lib.dos.Process import Process
from amitools.vamos.log import log_proc
from amitools.vamos.lib.dos.SysArgs import sys_args_to_ami_arg_str


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
        args = cmd_cfg.args
        if len(args) == 0:
            log_proc.error("No command and args given!")
            return None

        # split command into binary and args
        cmd_arg = self.get_cmd_args(mode_ctx, cmd_cfg, args)
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
        proc = Process(
            dos_ctx, cmd, arg_str, stack_size=stack_size, shell=shell, cwd=cwd
        )
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
                node = dos_lib.create_var(dos_ctx, name, 0)
                dos_lib.set_var(dos_ctx, node, 0, len(value) + 1, value, 0)
                log_proc.info("set var: %s='%s'", name, value)
        finally:
            dos_ctx.set_cur_process(old_proc)

    def get_cmd_args(self, mode_ctx, cmd_cfg, args):
        # a single Amiga-like raw arg was passed
        if cmd_cfg.raw_arg:
            # check args
            if len(args) > 1:
                log_proc.error("raw arg only allows a single argument!")
                return None
            # parse raw arg
            cl = CommandLine()
            res = cl.parse_line(cmd_cfg.binary)
            if res != cl.LINE_OK:
                log_proc.error("raw arg is invalid! (error %d)", res)
                return None
            binary = cl.get_cmd()
            arg_str = cl.get_arg_str()
            return binary, arg_str
        else:
            # setup binary
            binary = cmd_cfg.args[0]
            if not cmd_cfg.pure_ami_path:
                # if path exists on host system then make an ami path
                if os.path.exists(binary):
                    sys_binary = binary
                    dos_ctx = mode_ctx.dos_ctx
                    binary = dos_ctx.path_mgr.from_sys_path(binary)
                    if not binary:
                        log_proc.error("can't map binary: %s", sys_binary)
                        return None
            # combine remaining args to arg_str
            arg_str = sys_args_to_ami_arg_str(cmd_cfg.args[1:])
            return binary, arg_str
