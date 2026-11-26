"""The internal ``vamos`` command.

Controls and inspects a running vamos from the Amiga shell. This first
version implements a single ``version`` subcommand; further subcommands plug
into the dispatch table below without any new plumbing.
"""

from amitools.vamos.cmdcore.version import get_amitools_version

USAGE = [
    "usage: vamos <subcommand>",
    "subcommands:",
    "  version   print the amitools version",
]


def _version(ctx, args):
    ctx.stdout.writeln(get_amitools_version())
    return 0


#: subcommand name -> handler(ctx, args) -> exit code
SUBCOMMANDS = {
    "version": _version,
}


def _usage(ctx, error=False):
    out = ctx.stderr if error else ctx.stdout
    for line in USAGE:
        out.writeln(line)
    return 5 if error else 0


def main(ctx, arg_line, prog_name):
    args = arg_line.split()
    if not args:
        return _usage(ctx)
    handler = SUBCOMMANDS.get(args[0].lower())
    if handler is None:
        ctx.stderr.writeln("vamos: unknown subcommand '%s'" % args[0])
        return _usage(ctx, error=True)
    return handler(ctx, args[1:])
