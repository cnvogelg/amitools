#!/usr/bin/env python3
"""sample command: use the exec.library proxy"""


def main(ctx, arg_line, prog_name):
    size = 64
    mem = ctx.exec.AllocMem(size, 0)
    ctx.stdout.writeln("alloc=%s" % ("ok" if mem else "fail"))
    if mem:
        ctx.exec.FreeMem(mem, size)
    return 0
