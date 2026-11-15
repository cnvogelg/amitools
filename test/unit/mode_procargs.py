from amitools.vamos.cfgcore import ConfigDict
from amitools.vamos.mode.procargs import ProcArgs
from amitools.vamos.path import AmiPath


class HostFS:
    def __init__(self, files=None):
        self.files = set(files) if files else set()

    def is_file(self, path):
        return path in self.files


def make_cfg(args, pure_ami_path=False, raw_arg=False):
    return ConfigDict(
        {
            "args": args,
            "pure_ami_path": pure_ami_path,
            "raw_arg": raw_arg,
        }
    )


def proc_args_raw_test():
    adapter = ProcArgs(HostFS(), lambda path: None)
    result = adapter.make_cmd_args(make_cfg(['program "two words"'], raw_arg=True))
    assert result == ("program", '"two words"\n')


def proc_args_raw_two_args_test():
    adapter = ProcArgs(HostFS(), lambda path: None)
    assert adapter.make_cmd_args(make_cfg(["a", "b"], raw_arg=True)) is None


def proc_args_ami_binary_test():
    mapped = []

    def sys_to_ami(path):
        mapped.append(path)
        return AmiPath("root:bin/hello")

    adapter = ProcArgs(HostFS(), sys_to_ami)
    result = adapter.make_cmd_args(make_cfg(["C:hello", "world"]))
    assert result == ("C:hello", "world\n")
    assert mapped == []


def proc_args_host_binary_test():
    mapped = []

    def sys_to_ami(path):
        mapped.append(path)
        return AmiPath("root:bin/hello")

    adapter = ProcArgs(HostFS(["/host/bin/hello"]), sys_to_ami)
    result = adapter.make_cmd_args(make_cfg(["/host/bin/hello", "a b"]))
    assert result == ("root:bin/hello", '"a b"\n')
    assert mapped == ["/host/bin/hello"]


def proc_args_host_binary_unmappable_test():
    adapter = ProcArgs(HostFS(["/host/bin/hello"]), lambda path: None)
    assert adapter.make_cmd_args(make_cfg(["/host/bin/hello"])) is None


def proc_args_pure_ami_path_test():
    mapped = []

    def sys_to_ami(path):
        mapped.append(path)
        return AmiPath("root:bin/hello")

    adapter = ProcArgs(HostFS(["/host/bin/hello"]), sys_to_ami)
    result = adapter.make_cmd_args(make_cfg(["/host/bin/hello"], pure_ami_path=True))
    assert result == ("/host/bin/hello", "\n")
    assert mapped == []
