Python commands
===============

A **Python command** is a plain ``*.py`` file that runs inside vamos like an
Amiga program. Its first line is a Python shebang; vamos recognizes the file,
presents it to the m68k side as a tiny stub and calls a Python function in the
host process. This lets you script an emulated AmigaOS environment, drive
libraries, or replace a Workbench command with Python code.

A command is not a host script: it runs in the middle of a vamos run and can
use the emulated ``dos.library`` and ``exec.library`` through the proxies handed
to it.

Running a command
-----------------

Run a command file directly, exactly like an Amiga binary:

.. code-block:: text

    vamos hello.py arg1 arg2

The command's ``main`` function receives the raw Amiga argument line and the
program name; its return value becomes the exit code:

.. code-block:: python

    # hello.py  ->  run with:  vamos hello.py world
    def main(ctx, arg_line, prog_name):
        ctx.stdout.writeln("Hello from %s!" % prog_name)
        if arg_line:
            ctx.stdout.writeln("args: %s" % arg_line.rstrip())
        return 0

``prog_name`` is the file name without the ``.py`` extension, so the same
command reports the same name whether it runs directly or from the shell. Like
a real AmigaDOS program the argument line ends with a newline; ``rstrip()`` it
before displaying it.

The ``ctx`` object
------------------

The first argument passed to ``main`` is a command context:

``ctx.stdout`` / ``ctx.stderr``
    Write-only text streams. Output is routed through the Amiga DOS console
    handles, so it shows up on the emulated console and is captured like any
    other program's output.

``ctx.dos`` / ``ctx.exec``
    The ``dos.library`` and ``exec.library`` proxies. Call them as normal
    library functions, e.g. ``ctx.dos.Output()``, ``ctx.dos.IoErr()`` or
    ``ctx.exec.AllocMem(64, 0)``.

``ctx.mem`` / ``ctx.alloc``
    The emulated memory and its allocator, for lower-level access.

``ctx.runner``
    The m68k code runner, to execute raw code if needed.

``ctx.name``
    The name of the running command.

Resident commands
-----------------

The Amiga shell finds commands in the DOS *resident* list and on its command
path. ``--resident-dir`` publishes a directory of Python files as resident
commands so the shell can run them by name:

.. code-block:: text

    vamos -x --resident-dir ./my-commands

Every top-level ``*.py`` in the directory becomes a command named after the
file without ``.py`` (``hello.py`` -> ``hello``). Files whose name starts with
``_`` and ``__init__.py`` are skipped, so a directory can also hold shared
helper modules. Inside the shell:

.. code-block:: text

    0.SYS:> hello world
    Hello from hello!
    args: world

The option may be repeated to publish several directories.

Executable commands
-------------------

A command file must look like a Python program (a ``#!`` shebang naming
``python``) and, when the shell searches for it by a bare name, it must be
marked executable:

* on a host directory volume the host *execute* permission is used (``chmod +x``),
* on any other volume (``ram:``, a disk image, ...) the Amiga ``s`` (script)
  protection bit is used.

Explicitly naming a file (``vamos ./hello.py`` or ``RAM:hello.py``) loads it
without the executable check, just as ``LoadSeg`` does not care about
protection. Commands published with ``--resident-dir`` are trusted and always
run.

Built-in commands
-----------------

vamos ships a few internal commands that are always registered, so the shell has
a small guaranteed set of helpers even without ``--resident-dir``. The first is
``vamos``:

.. code-block:: text

    0.SYS:> vamos version
    0.9.2

Use ``--no-internal-commands`` to skip them. The built-in commands are
registered first, so a ``--resident-dir`` command (or a file on the command
path) with the same name takes precedence; built-ins are a fallback, not an
override.

Writing an own command
----------------------

A command is any module that defines a ``main`` function:

.. code-block:: python

    # count.py  ->  run with:  vamos --resident-dir . count 3
    def main(ctx, arg_line, prog_name):
        try:
            count = int(arg_line.split()[0])
        except (IndexError, ValueError):
            ctx.stderr.writeln("usage: count <n>")
            return 5
        for i in range(count):
            ctx.stdout.writeln("%d" % i)
        return 0

Notes:

* Keep the first line a shebang, e.g. ``#!/usr/bin/env python3``, and make the
  file executable when the shell should find it by name.
* The return value is the exit code (``0``..``255``); ``None`` counts as ``0``.
  A command may also call ``sys.exit(code)``.
* A Python exception inside ``main`` is logged with its traceback and the
  command exits with the error code ``20`` instead of taking vamos down.
* The command's own directory is added to ``sys.path``, so it can ``import``
  sibling helper modules.
* Modules are loaded lazily on first use and cached per Amiga path, so repeated
  runs of a resident command do not re-import it.

The ``test/command`` directory in the source tree holds small, runnable examples
(``hello.py``, ``exit7.py``, ``args.py``, ``dosproxy.py``, ``execproxy.py``).
