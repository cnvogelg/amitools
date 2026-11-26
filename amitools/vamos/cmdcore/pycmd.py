from amitools.vamos.log import log_cmd

#: exit code returned when a command raises an exception
RETURN_ERROR = 20


class PyCommand:
    """A Python command.

    A command is a name plus a ``main(ctx, arg_line, prog_name)`` callable.
    The callable is either provided directly (built-in internal commands,
    tests) or loaded from a Python source file (see :meth:`load`).

    The runtime state (``tid``/``seglist``) is managed by the
    :class:`~amitools.vamos.cmdcore.manager.CommandManager`.
    """

    def __init__(self, name, main=None, source=None, path=None):
        self.name = name
        self.main = main
        self.source = source
        self.path = path
        self.module = None
        # runtime state set by the CommandManager
        self.tid = None
        self.seglist = None

    def __repr__(self):
        return "[PyCommand:%s]" % self.name

    def has_main(self):
        return self.main is not None

    def run(self, ctx, arg_line):
        """Run the command and return its exit code.

        A Python exception is logged with its traceback and turned into a
        non-zero exit code so the emulated program terminates cleanly.
        """
        try:
            ret = self.main(ctx, arg_line, self.name)
        except Exception:
            log_cmd.error("command '%s' failed:", self.name, exc_info=True)
            return RETURN_ERROR
        if ret is None:
            ret = 0
        return int(ret) & 0xFF
