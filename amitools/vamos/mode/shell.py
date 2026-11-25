from .proc import ProcessModeBase
from amitools.vamos.lib.dos.Process import ShellProcess
from amitools.vamos.log import log_proc


SHELL_SEG_DEFAULT = "L:shell-seg"


class ShellMode(ProcessModeBase):
    """run a shell seg (the ``shell`` mode, also selected by ``-x``).

    The shell seg is named by ``command.shell_bin`` (default
    ``L:shell-seg``).  Positional arguments are ignored: the shell gets its
    command stream from ``S:Vamos-Startup`` or the console, not from the
    command line.
    """

    def __init__(self):
        super().__init__("shell")

    def make_process_args(self, mode_ctx, cmd_cfg):
        shell_bin = cmd_cfg.shell_bin or SHELL_SEG_DEFAULT
        binary = mode_ctx.proc_args.make_bin_path(cmd_cfg, shell_bin)
        if binary is None:
            return None
        log_proc.info("shell seg: %r", binary)
        return binary, ""

    def make_process(self, dos_ctx, binary, arg_str, stack_size, cwd):
        return ShellProcess(dos_ctx, binary, arg_str, stack_size=stack_size, cwd=cwd)
