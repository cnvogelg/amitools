from amitools.vamos.lib.dos.CommandLine import CommandLine
from amitools.vamos.lib.dos.SysArgs import sys_args_to_ami_arg_str
from amitools.vamos.log import log_proc


class ProcArgs(object):
    """prepare host CLI command arguments for the Amiga process mode.

    This is the only place where a host path passed on the command line may
    be translated into an Amiga path. The process mode itself only sees
    Amiga paths.
    """

    def __init__(self, host_fs, sys_to_ami_path):
        self.host_fs = host_fs
        self.sys_to_ami_path = sys_to_ami_path

    def make_cmd_args(self, cmd_cfg):
        """return (binary, arg_str) for the configured command or None"""
        # a single Amiga-like raw arg was passed
        if cmd_cfg.raw_arg:
            return self._raw_cmd_args(cmd_cfg.args)
        # map a host binary path to an Amiga path
        binary = self._to_ami_binary(cmd_cfg)
        if binary is None:
            return None
        # combine remaining args to arg_str
        arg_str = sys_args_to_ami_arg_str(cmd_cfg.args[1:])
        return binary, arg_str

    def _raw_cmd_args(self, args):
        if len(args) > 1:
            log_proc.error("raw arg only allows a single argument!")
            return None
        # parse raw arg
        cl = CommandLine()
        res = cl.parse_line(args[0])
        if res != cl.LINE_OK:
            log_proc.error("raw arg is invalid! (error %d)", res)
            return None
        return cl.get_cmd(), cl.get_arg_str()

    def make_bin_path(self, cmd_cfg, path):
        """resolve a single binary path (host or Amiga) to an Amiga path"""
        return self._resolve_binary(path, cmd_cfg.pure_ami_path)

    def _to_ami_binary(self, cmd_cfg):
        return self._resolve_binary(cmd_cfg.args[0], cmd_cfg.pure_ami_path)

    def _resolve_binary(self, binary, pure_ami_path):
        if pure_ami_path:
            return binary
        # if the argument is an existing host file then convert it
        if not self.host_fs.is_file(binary):
            return binary
        ami_path = self.sys_to_ami_path(binary)
        if ami_path is None:
            log_proc.error("can't map binary: %s", binary)
            return None
        return str(ami_path)
