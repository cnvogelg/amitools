"""Unit tests for the built-in ``vamos`` command and version lookup."""

from amitools.vamos.cmdcore.version import get_amitools_version
from amitools.vamos.command import get_command_dir
from amitools.vamos.command.vamos import main


class _Stream:
    def __init__(self):
        self.lines = []

    def writeln(self, text):
        self.lines.append(text)


class _Ctx:
    def __init__(self):
        self.stdout = _Stream()
        self.stderr = _Stream()


def command_vamos_version_test():
    ctx = _Ctx()
    ret = main(ctx, "version\n", "vamos")
    assert ret == 0
    assert ctx.stdout.lines == [get_amitools_version()]
    assert ctx.stderr.lines == []


def command_vamos_no_args_test():
    ctx = _Ctx()
    ret = main(ctx, "", "vamos")
    assert ret == 0
    assert ctx.stdout.lines[0].startswith("usage: vamos")
    assert ctx.stderr.lines == []


def command_vamos_unknown_test():
    ctx = _Ctx()
    ret = main(ctx, "bogus\n", "vamos")
    assert ret != 0
    assert ctx.stderr.lines[0] == "vamos: unknown subcommand 'bogus'"
    assert ctx.stdout.lines == []


def command_vamos_case_insensitive_test():
    ctx = _Ctx()
    assert main(ctx, "VERSION\n", "vamos") == 0


def command_vamos_version_lookup_test():
    version = get_amitools_version()
    assert isinstance(version, str)
    assert version


def command_vamos_command_dir_test():
    import os

    d = get_command_dir()
    assert os.path.isdir(d)
    assert os.path.isfile(os.path.join(d, "vamos.py"))
    # the package's own __init__.py is not published as a command
    assert os.path.isfile(os.path.join(d, "__init__.py"))
