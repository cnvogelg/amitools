"""Unit tests for the built-in internal command registration.

The built-in commands live in ``amitools/vamos/command`` and are published
through the same ``ResidentCommands``/``AddSegment`` path as ``--resident-dir``
(see :func:`amitools.vamos.cmdcore.resident.register_commands`).
"""

from types import SimpleNamespace

from amitools.vamos.cmdcore.resident import register_commands
from amitools.vamos.command import get_command_dir

from command_resident import PY_CMD, Context


def _cmd_cfg(no_internal=False, resident_dir=None):
    return SimpleNamespace(no_internal_commands=no_internal, resident_dir=resident_dir)


def command_builtin_discovered_test():
    """the built-in dir publishes vamos and skips __init__/_helpers"""
    ctx = Context()
    register_commands(ctx.resident, _cmd_cfg())
    # the built-in vamos command is registered as a resident command
    assert ctx.find("vamos") != 0
    # the package's __init__ is not a command
    assert ctx.find("__init__") == 0
    ctx.cleanup()
    assert ctx.alloc.is_all_free()


def command_builtin_suppressed_test():
    """--no-internal-commands skips the built-in dir entirely"""
    ctx = Context()
    register_commands(ctx.resident, _cmd_cfg(no_internal=True))
    assert ctx.resident.entries == []
    assert ctx.find("vamos") == 0
    ctx.cleanup()
    assert ctx.alloc.is_all_free()


def command_builtin_resident_dir_order_test(tmp_path):
    """--resident-dir is registered after the built-ins and wins a collision"""
    (tmp_path / "extra.py").write_bytes(PY_CMD)
    (tmp_path / "vamos.py").write_bytes(PY_CMD)
    ctx = Context()
    register_commands(ctx.resident, _cmd_cfg(resident_dir=[str(tmp_path)]))
    names = [name for name, _, _ in ctx.resident.entries]
    # built-in first, then the user dir (sorted); the user vamos is last
    assert names[0] == "vamos"
    assert names[-1] == "vamos"
    assert "extra" in names
    # the last registered command of a name wins the resident lookup
    assert ctx.find("vamos") == ctx.resident.entries[-1][1]
    ctx.cleanup()
    assert ctx.alloc.is_all_free()


def command_builtin_dir_exists_test():
    """get_command_dir points at the shipped package dir with vamos.py"""
    import os

    d = get_command_dir()
    assert os.path.isdir(d)
    assert os.path.isfile(os.path.join(d, "vamos.py"))
