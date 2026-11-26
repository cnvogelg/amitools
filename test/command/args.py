#!/usr/bin/env python3
"""sample command: echo the program name and argument line"""


def main(ctx, arg_line, prog_name):
    ctx.stdout.writeln("prog=%s" % prog_name)
    ctx.stdout.writeln("args=%s" % arg_line.rstrip())
    return 0
