"""Unit tests for the executable gate of the Python command search.

When a bare command name is looked up on the command path, a Python command
is only picked up when it is marked executable: the host execute bit on a
host-backed volume, the Amiga ``s`` (script) protection bit on any other
volume. These tests drive ``ProcessBase._command_allowed`` with fakes so the
non-hostfs branch (RAM:/ADF) is covered without a full DOS setup; the hostfs
branch is additionally covered end to end by ``test/extra/command.py``.
"""

from amitools.vamos.handler import (
    DosProtection,
    HandlerError,
    HandlerFileInfo,
    HostFileSysHandler,
)
from amitools.vamos.lib.dos.Process import ProcessBase


class FakeSegLoader:
    def __init__(self, is_py=True):
        self.is_py = is_py

    def is_python_command(self, ami_path, lock=None):
        return self.is_py


class FakeHandler:
    """a non-hostfs handler (e.g. RAM:) with a fixed protection mask"""

    def __init__(self, protection=0, examine_error=None):
        self.protection = protection
        self.examine_error = examine_error
        self.freed = []

    def examine_object(self, lock):
        if self.examine_error is not None:
            raise self.examine_error
        return HandlerFileInfo(
            name="cmd.py", entry_type=HandlerFileInfo.FILE, protection=self.protection
        )

    def free_lock(self, lock):
        self.freed.append(lock)


class FakeHandlerMgr:
    def __init__(self, handler=None, error=None):
        self.handler = handler
        self.error = error
        self.locate_calls = []

    def locate_object(self, ami_path, exclusive=False, env=None, cwd=None):
        self.locate_calls.append((ami_path, cwd))
        if self.error is not None:
            raise self.error
        return self.handler, "lock"


class Ctx:
    def __init__(self, seg_loader=None, handler_mgr=None):
        if seg_loader is not None:
            self.seg_loader = seg_loader
        if handler_mgr is not None:
            self.handler_mgr = handler_mgr


class FakeProc(ProcessBase):
    """a ProcessBase with only the pieces the gate needs"""

    def __init__(self, ctx):
        self.ctx = ctx


def _proc(seg_loader=None, handler_mgr=None):
    return FakeProc(Ctx(seg_loader=seg_loader, handler_mgr=handler_mgr))


# ----- gate entry -----


def command_gate_native_binary_allowed_test():
    """a native binary (not a Python command) is never gated"""
    proc = _proc(FakeSegLoader(is_py=False), FakeHandlerMgr(FakeHandler()))
    assert proc._command_allowed("cmds/prog", None)


def command_gate_no_seg_loader_allowed_test():
    """without a segment loader there is nothing to gate"""
    proc = _proc(None, FakeHandlerMgr(FakeHandler()))
    assert proc._command_allowed("cmds/prog", None)


def command_gate_no_handler_mgr_allowed_test():
    """without a handler layer a Python command is not blocked"""
    proc = _proc(FakeSegLoader(is_py=True), None)
    assert proc._command_allowed("cmds/prog", None)


# ----- non-hostfs volume (RAM:, ADF, ...) -----


def command_gate_ram_script_allowed_test():
    """on a non-hostfs volume the Amiga script bit marks it executable"""
    handler = FakeHandler(protection=DosProtection.FIBF_SCRIPT)
    proc = _proc(FakeSegLoader(is_py=True), FakeHandlerMgr(handler))
    assert proc._command_allowed("cmds/prog", None)
    assert handler.freed == ["lock"]


def command_gate_ram_not_script_blocked_test():
    """without the script bit a non-hostfs Python command is blocked"""
    handler = FakeHandler(protection=0)
    proc = _proc(FakeSegLoader(is_py=True), FakeHandlerMgr(handler))
    assert not proc._command_allowed("cmds/prog", None)
    assert handler.freed == ["lock"]


# ----- hostfs volume -----


def command_gate_hostfs_exec_allowed_test():
    """on hostfs the host execute bit (active low) marks it executable"""
    handler = HostFileSysHandler("root", "/")
    handler.examine_object = lambda lock: HandlerFileInfo(
        name="prog.py", entry_type=HandlerFileInfo.FILE, protection=0
    )
    handler.free_lock = lambda lock: None
    proc = _proc(FakeSegLoader(is_py=True), FakeHandlerMgr(handler))
    assert proc._command_allowed("cmds/prog", None)


def command_gate_hostfs_not_exec_blocked_test():
    """without the host execute bit a hostfs Python command is blocked"""
    handler = HostFileSysHandler("root", "/")
    handler.examine_object = lambda lock: HandlerFileInfo(
        name="prog.py",
        entry_type=HandlerFileInfo.FILE,
        protection=DosProtection.FIBF_EXECUTE,
    )
    handler.free_lock = lambda lock: None
    proc = _proc(FakeSegLoader(is_py=True), FakeHandlerMgr(handler))
    assert not proc._command_allowed("cmds/prog", None)


# ----- error paths -----


def command_gate_locate_error_blocked_test():
    """a file that cannot be located is blocked"""
    err = HandlerError(0)
    proc = _proc(FakeSegLoader(is_py=True), FakeHandlerMgr(error=err))
    assert not proc._command_allowed("cmds/prog", None)


def command_gate_examine_error_blocked_test():
    """a file that cannot be examined is blocked, its lock still freed"""
    handler = FakeHandler(examine_error=HandlerError(0))
    proc = _proc(FakeSegLoader(is_py=True), FakeHandlerMgr(handler))
    assert not proc._command_allowed("cmds/prog", None)
    assert handler.freed == ["lock"]


def command_gate_cwd_passed_test():
    """the current dir of the lock is handed to the handler layer"""
    handler = FakeHandler(protection=DosProtection.FIBF_SCRIPT)
    mgr = FakeHandlerMgr(handler)
    proc = _proc(FakeSegLoader(is_py=True), mgr)

    class Lock:
        ami_path = "cmds:"

    assert proc._command_allowed("cmds/prog", Lock())
    assert mgr.locate_calls == [("cmds/prog", "cmds:")]
