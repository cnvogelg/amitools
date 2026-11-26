#!/usr/bin/env python3
"""sample command: greet and return 0"""


def main(ctx, arg_line, prog_name):
    ctx.stdout.writeln("hello from %s" % prog_name)
    return 0
