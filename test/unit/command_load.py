import sys

import pytest

from amitools.vamos.machine import Machine, Runtime, Code, REG_D0
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.cmdcore import (
    CommandContext,
    CommandLoadError,
    CommandManager,
    CommandStream,
    PyCommand,
    RETURN_ERROR,
    strip_py_ext,
)


class Context:
    def __init__(self):
        self.mach = Machine()
        self.cpu = self.mach.get_cpu()
        self.mem = self.mach.get_mem()
        self.stack = self.mach.get_scratch_top()
        self.alloc = MemoryAlloc(self.mem, label_mgr=self.mach.get_label_mgr())
        self.rt = Runtime(self.mach)
        self.mgr = CommandManager(self.mach, self.alloc, self.rt.run)

    def run_cmd(self, cmd, set_regs=None):
        seglist = self.mgr.make_stub(cmd)
        code = Code(seglist.get_start_pc(), self.stack, set_regs=set_regs)
        return self.rt.start(code)

    def cleanup(self):
        self.mgr.shutdown()
        self.mach.cleanup()


@pytest.fixture
def ctx():
    return Context()


# ----- name helpers -----


def command_load_strip_py_ext_test():
    assert strip_py_ext("hello.py") == "hello"
    assert strip_py_ext("hello.PY") == "hello"
    assert strip_py_ext("hello") == "hello"
    assert strip_py_ext("hello.txt") == "hello.txt"
    assert strip_py_ext(None) is None


# ----- PyCommand.load -----


def command_load_from_source_test():
    source = "def main(ctx, arg_line, prog_name):\n    return 3\n"
    cmd = PyCommand("src", source=source)
    assert not cmd.has_main()
    cmd.load()
    assert cmd.has_main()
    assert cmd.run(None, "") == 3


def command_load_from_file_test(tmp_path):
    p = tmp_path / "hello.py"
    p.write_text("def main(ctx, arg_line, prog_name):\n    return 5\n")
    cmd = PyCommand("hello", path=str(p))
    cmd.load()
    assert cmd.module.__file__ == str(p)
    assert cmd.run(None, "") == 5


def command_load_missing_main_test():
    cmd = PyCommand("nomain", source="x = 1\n")
    with pytest.raises(CommandLoadError):
        cmd.load()


def command_load_syntax_error_test():
    cmd = PyCommand("broken", source="def main(:\n")
    with pytest.raises(CommandLoadError):
        cmd.load()


def command_load_import_error_test():
    cmd = PyCommand("boom", source="raise ValueError('nope')\n")
    with pytest.raises(CommandLoadError):
        cmd.load()


def command_load_no_source_test():
    cmd = PyCommand("empty")
    with pytest.raises(CommandLoadError):
        cmd.load()


def command_load_run_error_test():
    """run() turns a load error into RETURN_ERROR"""

    def main(ctx, arg_line, prog_name):
        return 0

    cmd = PyCommand("broken", source="def main(:\n")
    assert cmd.run(None, "") == RETURN_ERROR
    # a module without main() is also a load error at run time
    cmd = PyCommand("nomain", source="x = 1\n")
    assert cmd.run(None, "") == RETURN_ERROR


def command_load_run_exception_test():
    source = "def main(ctx, arg_line, prog_name):\n    raise ValueError('x')\n"
    cmd = PyCommand("boom", source=source)
    assert cmd.run(None, "") == RETURN_ERROR


def command_load_sys_path_test(tmp_path):
    """a command can import a sibling helper module from its own directory"""
    (tmp_path / "cmdhelper.py").write_text("VALUE = 7\n")
    p = tmp_path / "usefiend.py"
    p.write_text(
        "import cmdhelper\n"
        "def main(ctx, arg_line, prog_name):\n"
        "    return cmdhelper.VALUE\n"
    )
    cmd = PyCommand("usefiend", path=str(p))
    cmd.load()
    assert cmd.run(None, "") == 7
    assert str(tmp_path) in sys.path


# ----- CommandManager loading / caching -----


def command_load_manager_load_test(ctx, tmp_path):
    p = tmp_path / "hello.py"
    p.write_text("def main(ctx, arg_line, prog_name):\n    return 4\n")
    cmd = ctx.mgr.load_command(path=str(p))
    # name is derived from the file name with .py stripped
    assert cmd.name == "hello"
    assert cmd.has_main()
    assert ctx.mgr.get_command("hello") is cmd
    ctx.cleanup()


def command_load_manager_cache_test(ctx, tmp_path):
    p = tmp_path / "hello.py"
    p.write_text("def main(ctx, arg_line, prog_name):\n    return 0\n")
    cmd1 = ctx.mgr.load_command(path=str(p))
    cmd2 = ctx.mgr.load_command(path=str(p))
    assert cmd1 is cmd2
    ctx.cleanup()


def command_load_manager_lazy_test(ctx, tmp_path):
    """a command created with make_command loads lazily on first run"""
    p = tmp_path / "lazy.py"
    p.write_text("def main(ctx, arg_line, prog_name):\n    return 9\n")
    cmd = ctx.mgr.make_command("lazy", path=str(p))
    assert not cmd.has_main()
    rs = ctx.run_cmd(cmd)
    assert rs.exit
    assert ctx.cpu.r_reg(REG_D0) == 9
    assert cmd.has_main()
    ctx.cleanup()


def command_load_manager_run_source_test(ctx):
    source = (
        "def main(ctx, arg_line, prog_name):\n"
        "    ctx.stdout.writeln('hi %s' % prog_name)\n"
        "    return 0\n"
    )
    cmd = ctx.mgr.make_command("greet", source=source)
    rs = ctx.run_cmd(cmd)
    assert rs.exit
    ctx.cleanup()


def command_load_manager_missing_main_test(ctx, tmp_path):
    p = tmp_path / "nomain.py"
    p.write_text("x = 1\n")
    cmd = ctx.mgr.make_command("nomain", path=str(p))
    rs = ctx.run_cmd(cmd)
    assert rs.exit
    assert ctx.cpu.r_reg(REG_D0) == RETURN_ERROR
    ctx.cleanup()


def command_load_manager_prog_name_test(ctx, tmp_path, capsys):
    p = tmp_path / "who.py"
    p.write_text(
        "def main(ctx, arg_line, prog_name):\n"
        "    ctx.stdout.writeln(prog_name)\n"
        "    return 0\n"
    )
    cmd = ctx.mgr.load_command(path=str(p))
    assert cmd.name == "who"
    ctx.run_cmd(cmd)
    assert capsys.readouterr().out == "who\n"
    ctx.cleanup()


# ----- context output routing -----


def command_load_stdout_test(ctx, tmp_path, capsys):
    p = tmp_path / "hello.py"
    p.write_text(
        "def main(ctx, arg_line, prog_name):\n"
        "    ctx.stdout.writeln('hello %s' % prog_name)\n"
        "    return 0\n"
    )
    cmd = ctx.mgr.load_command(path=str(p))
    ctx.run_cmd(cmd)
    out = capsys.readouterr().out
    assert "hello hello\n" in out
    ctx.cleanup()


def command_load_stderr_test(ctx, tmp_path, capsys):
    p = tmp_path / "err.py"
    p.write_text(
        "def main(ctx, arg_line, prog_name):\n"
        "    ctx.stderr.writeln('oops')\n"
        "    return 0\n"
    )
    cmd = ctx.mgr.load_command(path=str(p))
    ctx.run_cmd(cmd)
    err = capsys.readouterr().err
    assert "oops\n" in err
    ctx.cleanup()


def command_load_print_helper_test(ctx, tmp_path, capsys):
    p = tmp_path / "pr.py"
    p.write_text(
        "def main(ctx, arg_line, prog_name):\n    ctx.print('a', 1)\n    return 0\n"
    )
    cmd = ctx.mgr.load_command(path=str(p))
    ctx.run_cmd(cmd)
    out = capsys.readouterr().out
    assert "a 1\n" in out
    ctx.cleanup()


# ----- DOS-backed output routing (with lightweight fakes) -----


class FakeFileHandle:
    def __init__(self, b_addr):
        self.b_addr = b_addr


class FakeDos:
    def __init__(self):
        self.writes = []
        self.flushes = []

    def Write(self, fh_b_addr, buf_ptr, size):
        self.writes.append((fh_b_addr, buf_ptr, size))
        return size

    def Flush(self, fh_b_addr):
        self.flushes.append(fh_b_addr)
        return 0


class FakeProcess:
    def __init__(self, fh):
        self._fh = fh

    def get_output(self):
        return self._fh


class FakeDosLib:
    def __init__(self, fh, process=None):
        self.file_mgr = self
        self.ctx = type("Ctx", (), {"process": process})()
        self._fh = fh

    def get_output(self):
        return self._fh


class FakeProxies:
    def __init__(self, exec_lib, dos_lib):
        self._exec = exec_lib
        self._dos = dos_lib

    def get_exec_lib_proxy(self):
        return self._exec

    def get_dos_lib_proxy(self):
        return self._dos


def command_load_stream_dos_test(ctx):
    """CommandStream routes output through dos.Write with a BPTR"""
    dos = FakeDos()
    fh = FakeFileHandle(0x1234)
    stream = CommandStream(dos_lib=dos, file_handle=fh, alloc=ctx.alloc)
    assert stream.write("abc") == 3
    assert len(dos.writes) == 1
    fh_b, ptr, size = dos.writes[0]
    assert fh_b == 0x1234
    assert size == 3
    assert ctx.mem.r_block(ptr, size) == b"abc"
    stream.flush()
    assert dos.flushes == [0x1234]
    ctx.cleanup()


def command_load_stream_dos_int_handle_test(ctx):
    """a plain BPTR is accepted as the file handle"""
    dos = FakeDos()
    stream = CommandStream(dos_lib=dos, file_handle=0x42, alloc=ctx.alloc)
    stream.write("x")
    assert dos.writes[0][0] == 0x42
    ctx.cleanup()


def command_load_stream_host_fallback_test(ctx):
    """without DOS the stream falls back to the host stream"""
    import io

    buf = io.StringIO()
    stream = CommandStream(host_stream=buf)
    stream.writeln("hello")
    assert buf.getvalue() == "hello\n"
    ctx.cleanup()


def command_load_context_dos_routing_test(ctx):
    """make_context picks up the process output handle from the proxies"""
    fh = FakeFileHandle(0x99)
    dos_lib = FakeDosLib(fh, process=FakeProcess(fh))
    mgr = CommandManager(
        ctx.mach, ctx.alloc, ctx.rt.run, proxies=FakeProxies("EXEC", dos_lib)
    )
    cmd = mgr.make_command("t", main=lambda c, a, n: 0)
    c = mgr.make_context(cmd)
    assert isinstance(c, CommandContext)
    assert c.exec == "EXEC"
    assert c.dos is dos_lib
    assert c.stdout.file_handle is fh
    assert c.stderr.file_handle is fh
    ctx.cleanup()


def command_load_context_dos_no_process_test(ctx):
    """without a process the file manager's default output is used"""
    fh = FakeFileHandle(0x77)
    dos_lib = FakeDosLib(fh, process=None)
    mgr = CommandManager(
        ctx.mach, ctx.alloc, ctx.rt.run, proxies=FakeProxies("EXEC", dos_lib)
    )
    cmd = mgr.make_command("t", main=lambda c, a, n: 0)
    c = mgr.make_context(cmd)
    assert c.stdout.file_handle is fh
    ctx.cleanup()
