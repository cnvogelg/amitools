import itertools
import os
import re
import sys

from amitools.vamos.log import log_cmd

#: exit code returned when a command raises an exception or fails to load
RETURN_ERROR = 20

# unique synthetic module names for loaded command modules
_module_counter = itertools.count()


class CommandLoadError(Exception):
    """raised when a command module cannot be loaded or has no main()"""


def strip_py_ext(name):
    """return the command name with a trailing ``.py`` stripped"""
    if name and name.lower().endswith(".py"):
        return name[:-3]
    return name


def _make_module_name(name):
    base = re.sub(r"[^0-9a-zA-Z_]", "_", name) or "cmd"
    return "vamos_cmd_%s_%d" % (base, next(_module_counter))


class PyCommand:
    """A Python command.

    A command is a name plus a ``main(ctx, arg_line, prog_name)`` callable.
    The callable is either provided directly (built-in internal commands,
    tests) or loaded from Python source (see :meth:`load`).

    The runtime state (``tid``/``seglist``) is managed by the
    :class:`~amitools.vamos.cmdcore.manager.CommandManager`.
    """

    def __init__(self, name, main=None, source=None, path=None, module_name=None):
        self.name = name
        self.main = main
        self.source = source
        self.path = path
        self.module_name = module_name or _make_module_name(name)
        self.module = None
        # runtime state set by the CommandManager
        self.tid = None
        self.seglist = None

    def __repr__(self):
        return "[PyCommand:%s]" % self.name

    def has_main(self):
        return self.main is not None

    def _read_source(self):
        if self.source is not None:
            return self.source
        if self.path is not None:
            with open(self.path, "rb") as f:
                return f.read()
        raise CommandLoadError("command '%s' has no source" % self.name)

    def _add_to_sys_path(self):
        # let a command import sibling helper modules from its own directory
        if not self.path:
            return
        dir_name = os.path.dirname(os.path.abspath(self.path))
        if dir_name and dir_name not in sys.path:
            log_cmd.debug("add command dir to sys.path: %s", dir_name)
            sys.path.insert(0, dir_name)

    def load(self):
        """Load the command module and resolve its ``main`` callable.

        Does nothing when ``main`` was already provided directly. Raises
        :class:`CommandLoadError` when the module has no ``main``.
        """
        if self.main is not None:
            return self.main
        source = self._read_source()
        self._add_to_sys_path()
        filename = self.path if self.path is not None else "<command:%s>" % self.name
        try:
            code = compile(source, filename, "exec")
        except (SyntaxError, ValueError) as e:
            raise CommandLoadError("command '%s': %s" % (self.name, e))
        module = type(sys)(self.module_name)
        module.__file__ = filename
        try:
            exec(code, module.__dict__)
        except SystemExit as e:
            raise CommandLoadError(
                "command '%s' exited during import: %s" % (self.name, e)
            )
        except Exception as e:
            raise CommandLoadError("command '%s' failed to import: %s" % (self.name, e))
        main = getattr(module, "main", None)
        if main is None:
            raise CommandLoadError("command '%s' has no main()" % self.name)
        self.module = module
        self.main = main
        log_cmd.info("loaded command '%s' from %s", self.name, filename)
        return main

    def ensure_loaded(self):
        if self.main is None:
            self.load()
        return self.main

    def run(self, ctx, arg_line):
        """Run the command and return its exit code.

        A load error or a Python exception inside ``main`` is logged and
        turned into a non-zero exit code so the emulated program terminates
        cleanly. A ``sys.exit()`` in the command is honored as its exit code.
        """
        try:
            self.ensure_loaded()
            ret = self.main(ctx, arg_line, self.name)
        except CommandLoadError:
            log_cmd.error("command '%s' failed to load:", self.name, exc_info=True)
            return RETURN_ERROR
        except SystemExit as e:
            # let a command end itself with sys.exit(code)
            if e.code is None:
                return 0
            if isinstance(e.code, int):
                return e.code & 0xFF
            return RETURN_ERROR
        except Exception:
            log_cmd.error("command '%s' failed:", self.name, exc_info=True)
            return RETURN_ERROR
        if ret is None:
            ret = 0
        return int(ret) & 0xFF
