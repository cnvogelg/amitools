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
        cmd_arg = self.get_cmd_args(cmd_cfg, args)
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
        return proc

    def get_cmd_args(self, cmd_cfg, args):
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
                    binary = dos_ctx.path_mgr.from_sys_path(binary)
                    if not binary:
                        log_proc.error("can't map binary: %s", sys_binary)
                        return None
            # combine remaining args to arg_str
            arg_str = sys_args_to_ami_arg_str(cmd_cfg.args[1:])
            return binary, arg_str
