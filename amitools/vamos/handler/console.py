"""CONSOLE: device handler.

``CONSOLE:`` (and its alias ``*``) is the AmigaDOS console device. In vamos
the console is the host's standard input/output, so an opened console handle
wraps ``sys.stdin``/``sys.stdout`` exactly like the default DOS handles. The
DOS layer redirects reads and writes between them (see
``FileManager.get_by_b_addr``).
"""

import sys

from .base import (
    Handler,
    HandlerFile,
    MODE_NEWFILE,
)


class ConsoleFile(HandlerFile):
    """open ``CONSOLE:`` handle backed by a host standard stream"""

    need_close = False

    def __init__(self, fobj, name):
        super().__init__(key=name.lower())
        self.fobj = fobj
        self.name = name


class ConsoleHandler(Handler):
    """device handler for ``CONSOLE:`` / ``*``"""

    def __init__(self, name):
        super().__init__(name, is_filesystem=False)

    def _stdout_file(self):
        fh = ConsoleFile(sys.stdout.buffer, "<STDOUT>")
        fh.auto_flush = True
        return fh

    # every console open yields the standard output stream; the DOS layer
    # redirects a read on it to the standard input (see FileManager)
    def find_input(self, ami_path):
        return self._stdout_file()

    def find_output(self, ami_path, mode=MODE_NEWFILE):
        return self._stdout_file()

    def find_update(self, ami_path):
        return self._stdout_file()
