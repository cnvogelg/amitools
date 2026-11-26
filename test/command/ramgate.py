#!/usr/bin/env python3
"""sample command: exercise the non-hostfs command gate.

Writes a small Python command to ``RAM:`` (optionally with the Amiga ``s``
script bit) and then runs it through ``SystemTagList()``. SystemTagList()
resolves a bare name through the command path (which includes the current
dir), so the executable gate applies: on a non-hostfs volume a Python command
is only picked up with the ``s`` bit.

Run this command itself as a binary (not from the Amiga shell) so that
SystemTagList() does not forward to the shell, which would bypass the gate.
"""

# FIBF_SCRIPT: the Amiga script bit, which marks a command executable on a
# non-hostfs volume
FIBF_SCRIPT = 64

# MODE_NEWFILE
MODE_NEWFILE = 1006

SRC = (
    "#!/usr/bin/env python3\n"
    "def main(ctx, arg_line, prog_name):\n"
    "    ctx.stdout.writeln('ram command ran')\n"
    "    return 0\n"
)


def _write_ram(ctx, path, data):
    fh = ctx.dos.Open(path, MODE_NEWFILE)
    if not fh:
        return False
    buf = ctx.alloc.alloc_memory(len(data))
    try:
        ctx.mem.w_block(buf.addr, data)
        ctx.dos.Write(fh, buf.addr, len(data))
    finally:
        ctx.alloc.free_memory(buf)
        ctx.dos.Close(fh)
    return True


def main(ctx, arg_line, prog_name):
    args = arg_line.split()
    if len(args) != 2 or args[1] not in ("script", "plain"):
        ctx.stdout.writeln("usage: ramgate <name> <script|plain>")
        return 5
    name, kind = args
    path = "RAM:" + name
    if not _write_ram(ctx, path, SRC.encode("latin-1")):
        ctx.stdout.writeln("open failed: %s" % path)
        return 1
    if kind == "script":
        ctx.dos.SetProtection(path, FIBF_SCRIPT)
    # a bare name is resolved through the command path and gated
    rc = ctx.dos.SystemTagList(name, None)
    ctx.stdout.writeln("rc=%d" % rc)
    return 0
