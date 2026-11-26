"""Register Python commands as DOS resident segments.

A resident command is a stub seglist (see
:class:`~amitools.vamos.cmdcore.manager.CommandManager`) linked into the DOS
resident list with ``AddSegment``. The Amiga shell resolves it with
``FindSegment`` and runs it with ``RunCommand``, which passes the command line
in ``A0``/``D0`` exactly like the direct-binary path.

The :class:`ResidentCommands` helper owns the DOS-side bookkeeping: it books
each stub with ``AddSegment`` and, on shutdown, unlinks and frees the resident
nodes before ``DosLibrary.finish_lib`` walks the resident list.
"""

import os

from amitools.vamos.log import log_cmd

#: ``seg_UC`` use count of a user resident command. The stock shell looks up
#: user commands with ``FindSegment(name, system=0)``, which matches ``seg_UC > 0``.
USER_FLAG = 1

#: label of the temporary name buffer passed to ``AddSegment``
NAME_LABEL = "ResidentName"


class ResidentCommands:
    """book Python commands as resident segments in the DOS resident list"""

    def __init__(self, cmd_mgr):
        self.cmd_mgr = cmd_mgr
        self.dos = None
        self.ctx = None
        # (name, seg_addr, b_addr) of every registered resident command
        self.entries = []

    def setup(self, dos_impl, dos_ctx):
        """remember the live dos.library and its context (post-setup)"""
        self.dos = dos_impl
        self.ctx = dos_ctx

    # ----- registration -----

    def add_source(self, name, source):
        """register a command from Python source as a resident segment"""
        if self.dos is None:
            raise RuntimeError("ResidentCommands.setup() was not called")
        cmd = self.cmd_mgr.make_command(name, source=source)
        seglist = self.cmd_mgr.make_stub(cmd)
        b_addr = seglist.get_baddr()
        name_addr = self._write_name(name)
        try:
            self.dos.AddSegment(self.ctx, name_addr, b_addr, USER_FLAG)
        except Exception:
            # roll the half-built registration back
            self.cmd_mgr.free_stub(cmd)
            raise
        finally:
            self.dos._free_mem(name_addr)
        # AddSegment appends the new node to dos.resident
        seg_addr = self.dos.resident[-1]
        self.entries.append((name, seg_addr, b_addr))
        log_cmd.info(
            "resident command '%s' seg=@%06x seglist=%06x", name, seg_addr, b_addr
        )
        return cmd

    def add_dir(self, host_dir):
        """register every top-level ``*.py`` in a host directory.

        Returns the number of commands registered. Files whose name starts
        with ``_`` (``__init__.py`` and private helpers) are skipped.
        """
        try:
            entries = sorted(os.listdir(host_dir))
        except OSError as e:
            log_cmd.error("can't scan resident dir '%s': %s", host_dir, e)
            return 0
        count = 0
        for entry in entries:
            if not entry.lower().endswith(".py") or entry.startswith("_"):
                continue
            path = os.path.join(host_dir, entry)
            if not os.path.isfile(path):
                continue
            with open(path, "rb") as f:
                source = f.read()
            self.add_source(entry[:-3], source)
            count += 1
        return count

    def _write_name(self, name):
        data = name.encode("latin-1")
        name_addr = self.dos._alloc_mem(NAME_LABEL, len(data) + 1)
        self.ctx.mem.w_cstr(name_addr, name)
        return name_addr

    # ----- cleanup -----

    def shutdown(self):
        """unlink and free every resident command registered here"""
        if self.dos is None:
            self.entries = []
            return
        # imported lazily: the dos.library module is heavy and only needed here
        from amitools.vamos.lib.dos.Segments import rem_segment

        for name, seg_addr, b_addr in self.entries:
            rem_segment(self.dos, self.ctx, seg_addr)
            self.dos.seg_lists.pop(b_addr, None)
            log_cmd.info("unregistered resident command '%s'", name)
        self.entries = []


def register_commands(resident, cmd_cfg):
    """publish the built-in and configured resident command dirs.

    The built-in ``vamos.command`` directory is scanned first (unless
    ``--no-internal-commands`` is set), then every ``--resident-dir`` in order,
    so a user command with the same name as a built-in wins.
    """
    if not cmd_cfg.no_internal_commands:
        # imported lazily to keep the package import order simple
        from amitools.vamos.command import get_command_dir

        resident.add_dir(get_command_dir())
    for host_dir in cmd_cfg.resident_dir or []:
        resident.add_dir(host_dir)
