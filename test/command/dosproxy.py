#!/usr/bin/env python3
"""sample command: use the dos.library proxy"""


def main(ctx, arg_line, prog_name):
    ctx.dos.SetIoErr(123)
    ctx.stdout.writeln("ioerr=%d" % ctx.dos.IoErr())
    out = ctx.dos.Output()
    ctx.stdout.writeln("output=%s" % ("ok" if out else "none"))
    return 0
