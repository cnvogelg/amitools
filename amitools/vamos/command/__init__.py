"""Built-in internal commands for the Amiga shell.

Every top-level ``*.py`` in this package (except ``__init__.py`` and
``_``-prefixed helpers) is published as a resident command named after the
file without ``.py``. See :func:`get_command_dir`.
"""

import os


def get_command_dir():
    """return the directory holding the built-in command modules"""
    return os.path.dirname(os.path.abspath(__file__))
