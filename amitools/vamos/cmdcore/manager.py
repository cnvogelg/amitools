import os

from amitools.vamos.loader import SegList
from amitools.vamos.machine import REG_A0, REG_D0
from amitools.vamos.machine.opcodes import op_rts, op_trap
from amitools.vamos.log import log_cmd

from .ctx import CommandContext
from .pycmd import PyCommand, RETURN_ERROR, strip_py_ext

#: payload size of a stub seglist: TRAP (2) + RTS (2)
STUB_SIZE = 4


class CommandManager:
    """Manages Python commands that are presented to the m68k side as a
    minimal stub.

    A stub is a tiny in-memory DOS seglist holding ``TRAP #tid`` followed by
    ``RTS``. The ``TRAP`` selects a Python handler allocated for the command;
    the handler reads the argument line from ``A0``/``D0``, runs the command
    and writes the exit code back to ``D0``. The ``RTS`` then returns to
    whoever started the program.

    The manager owns the trap and stub seglist lifecycle, the command
    registry and the per-path module cache.
    """

    def __init__(self, machine, alloc, runner=None, proxies=None):
        self.machine = machine
        self.alloc = alloc
        self.runner = runner
        # optional LibProxyManager used to expose exec/dos to commands
        self.proxies = proxies
        self.mem = machine.get_mem()
        self.traps = machine.get_traps()
        # name -> PyCommand
        self.commands = {}
        # Amiga/host path -> loaded PyCommand (module cache)
        self.loaded = {}
        # commands with a live stub seglist
        self.stubs = []

    # ----- registry -----

    def make_command(self, name, main=None, source=None, path=None):
        """Create and register a command (does not load it yet)."""
        cmd = PyCommand(name, main=main, source=source, path=path)
        self.commands[name] = cmd
        return cmd

    def load_command(self, name=None, source=None, path=None, cache_key=None):
        """Load a command module and cache it per path.

        The module is loaded on first use; a second call for the same path
        returns the cached command. When ``name`` is not given it is derived
        from the file name with a trailing ``.py`` stripped.
        """
        key = cache_key if cache_key is not None else path
        if key is not None and key in self.loaded:
            return self.loaded[key]
        if name is None:
            if path is None:
                raise ValueError("load_command needs a name or a path")
            name = strip_py_ext(os.path.basename(path))
        cmd = self.make_command(name, source=source, path=path)
        cmd.ensure_loaded()
        if key is not None:
            self.loaded[key] = cmd
        return cmd

    def get_command(self, name):
        return self.commands.get(name)

    # ----- stub / trap lifecycle -----

    def make_stub(self, cmd):
        """Allocate a stub seglist for the command and return it."""
        if cmd.seglist is not None:
            raise ValueError("command '%s' already has a stub" % cmd.name)
        # one trap per command
        cmd.tid = self.traps.alloc(self._make_trap_handler(cmd))
        # minimal seglist: payload is just TRAP + RTS
        seglist = SegList.alloc(self.alloc, [STUB_SIZE])
        start = seglist.get_start_pc()
        self.mem.w16(start, op_trap | cmd.tid)
        self.mem.w16(start + 2, op_rts)
        cmd.seglist = seglist
        self.stubs.append(cmd)
        log_cmd.info("stub for '%s' at @%06x trap=%d", cmd.name, start, cmd.tid)
        return seglist

    def free_stub(self, cmd):
        """Free the stub seglist and trap of a command."""
        if cmd.seglist is not None:
            cmd.seglist.free()
            cmd.seglist = None
        if cmd.tid is not None:
            self.traps.free(cmd.tid)
            cmd.tid = None
        if cmd in self.stubs:
            self.stubs.remove(cmd)

    def shutdown(self):
        """Free every live stub and trap."""
        log_cmd.info("shutdown")
        for cmd in list(self.stubs):
            self.free_stub(cmd)

    # ----- context / execution -----

    def make_context(self, cmd):
        exec_lib = None
        dos_lib = None
        out_fh = None
        err_fh = None
        if self.proxies is not None:
            exec_lib = self.proxies.get_exec_lib_proxy()
            dos_lib = self.proxies.get_dos_lib_proxy()
            out_fh, err_fh = self._get_output_handles(dos_lib)
        return CommandContext(
            self.machine,
            self.alloc,
            self.runner,
            cmd,
            exec_lib=exec_lib,
            dos_lib=dos_lib,
            out_fh=out_fh,
            err_fh=err_fh,
        )

    def _get_output_handles(self, dos_lib):
        # prefer the running process's output handle, fall back to the
        # file manager's default output
        process = getattr(getattr(dos_lib, "ctx", None), "process", None)
        if process is not None:
            out_fh = process.get_output()
        else:
            out_fh = dos_lib.file_mgr.get_output()
        # AmigaDOS has a single console: no separate error handle
        return out_fh, out_fh

    def _read_arg_line(self):
        # a program receives its argument string as (A0=ptr, D0=len)
        a0 = self.machine.cpu.r_reg(REG_A0)
        d0 = self.machine.cpu.r_reg(REG_D0)
        if a0 == 0 or d0 == 0:
            return ""
        return self.mem.r_block(a0, d0).decode("latin-1")

    def _make_trap_handler(self, cmd):
        def handler(opcode, pc):
            self._run_command(cmd, pc)

        return handler

    def _run_command(self, cmd, pc):
        arg_line = self._read_arg_line()
        log_cmd.info("run '%s' pc=@%06x args=%r", cmd.name, pc, arg_line)
        try:
            cmd.ensure_loaded()
        except Exception:
            log_cmd.error("command '%s' not loadable:", cmd.name, exc_info=True)
            self.machine.cpu.w_reg(REG_D0, RETURN_ERROR)
            return
        ctx = self.make_context(cmd)
        ret = cmd.run(ctx, arg_line)
        # hand the exit code back to the m68k side (RTS follows)
        self.machine.cpu.w_reg(REG_D0, ret & 0xFFFFFFFF)
