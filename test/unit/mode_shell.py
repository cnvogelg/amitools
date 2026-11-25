"""``ShellMode``: the shell mode and the ``-x`` shortcut.

Step 6 of the shell refactor added the ``shell`` mode: ``-x``/``--shell`` and
``-M shell`` both select it, it runs the seg named by ``command.shell_bin``
(default ``L:shell-seg``) and it ignores positional arguments.
"""

from types import SimpleNamespace

from amitools.vamos.mode.proc import ProcMode
from amitools.vamos.mode.setup import ModeSetup
from amitools.vamos.mode.shell import SHELL_SEG_DEFAULT, ShellMode


class _FakeProcArgs:
    def __init__(self, resolved):
        self.resolved = resolved
        self.calls = []

    def make_bin_path(self, cmd_cfg, path):
        self.calls.append(path)
        return self.resolved


# ----- mode selection -----


def mode_shell_select_x_test():
    # -x/--shell is a boolean shortcut for the shell mode
    cmd_cfg = SimpleNamespace(shell=True, mode="proc")
    assert isinstance(ModeSetup.select(cmd_cfg), ShellMode)


def mode_shell_select_mode_test():
    # -M shell selects the same mode without -x
    cmd_cfg = SimpleNamespace(shell=False, mode="shell")
    assert isinstance(ModeSetup.select(cmd_cfg), ShellMode)


def mode_shell_select_proc_test():
    # no -x and no -M shell keeps the default proc mode
    cmd_cfg = SimpleNamespace(shell=False, mode="proc")
    assert isinstance(ModeSetup.select(cmd_cfg), ProcMode)


# ----- shell seg resolution -----


def mode_shell_process_args_default_test():
    mode = ShellMode()
    proc_args = _FakeProcArgs("wb:l/Shell-Seg")
    cmd_cfg = SimpleNamespace(shell_bin=None, pure_ami_path=False)
    mode_ctx = SimpleNamespace(proc_args=proc_args)
    # the default seg is used and the arg string is empty
    assert mode.make_process_args(mode_ctx, cmd_cfg) == ("wb:l/Shell-Seg", "")
    assert proc_args.calls == [SHELL_SEG_DEFAULT]


def mode_shell_process_args_configured_test():
    mode = ShellMode()
    proc_args = _FakeProcArgs("wb:l/Shell-Seg")
    cmd_cfg = SimpleNamespace(shell_bin="wb:l/Shell-Seg", pure_ami_path=False)
    mode_ctx = SimpleNamespace(proc_args=proc_args)
    assert mode.make_process_args(mode_ctx, cmd_cfg) == ("wb:l/Shell-Seg", "")
    assert proc_args.calls == ["wb:l/Shell-Seg"]


def mode_shell_process_args_unmappable_test():
    mode = ShellMode()
    proc_args = _FakeProcArgs(None)
    cmd_cfg = SimpleNamespace(shell_bin="/host/Shell-Seg", pure_ami_path=False)
    mode_ctx = SimpleNamespace(proc_args=proc_args)
    assert mode.make_process_args(mode_ctx, cmd_cfg) is None


# ----- process construction -----


def mode_shell_make_process_test(monkeypatch):
    built = []

    class _FakeShellProcess:
        def __init__(self, dos_ctx, binary, arg_str, stack_size=None, cwd=None):
            built.append((dos_ctx, binary, arg_str, stack_size, cwd))

    monkeypatch.setattr("amitools.vamos.mode.shell.ShellProcess", _FakeShellProcess)
    mode = ShellMode()
    dos_ctx = SimpleNamespace()
    proc = mode.make_process(dos_ctx, "wb:l/Shell-Seg", "", 8192, "root:")
    assert isinstance(proc, _FakeShellProcess)
    assert built == [(dos_ctx, "wb:l/Shell-Seg", "", 8192, "root:")]
