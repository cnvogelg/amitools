Configuration
=============

While some simple CLI programs run out of the box, typical applications need
some setup. vamos accepts that setup either on the command line or from a
configuration file, and command-line values override file values.

The emulated environment is made up of:

* **DOS setup** -- volume mappings, assigns and the command path
* **Exec setup** -- library settings and the stack size
* **Hardware settings** -- CPU selection, memory size and hardware access
* **vamos settings** -- emulation settings, logging, tracing and profiling

Each part is described in :doc:`options`, where every option is listed with a
small example. This chapter explains the general mechanism.

By file
-------

vamos reads a configuration file, usually named ``.vamosrc``. Without an
explicit file it looks in the current directory first and then in your
``$HOME`` directory, and loads the first one it finds. Use ``-c FILE`` to load a
specific file and ``-S`` to skip configuration files entirely (useful for tests
that need a clean setup).

INI format
~~~~~~~~~~

The traditional ``.vamosrc`` is a ``.ini`` file: sections in brackets followed
by ``key=value`` lines. For example:

.. code-block:: ini

    [volumes]
    sys=$HOME/amiga/system
    work=$HOME/amiga/work

    [assigns]
    c=sys:c

    [path]
    path=c:,work:bin
    cwd=work:src

    [vamos]
    cpu=68020
    ram_size=8192
    stack_size=32
    logging=dos:info,exec:debug

    [icon.library]
    mode=off

See ``config/sample_vamosrc`` in the source archive for a complete example.

JSON format
~~~~~~~~~~~

The same configuration can be written as a JSON file, which maps the sections
and keys onto nested objects. Select it explicitly with ``-c``:

.. code-block:: json

    {
      "volumes": {
        "sys": "$HOME/amiga/system",
        "work": "$HOME/amiga/work"
      },
      "vamos": {
        "cpu": "68020",
        "ram_size": 8192
      },
      "profile": {
        "enabled": true,
        "libs": {
          "names": ["exec.library", "dos.library"],
          "calls": true
        }
      }
    }

.. code-block:: text

    vamos -c ./vamos.json myprog

By command line
---------------

Options normally precede the Amiga program and override any value from a
configuration file:

.. code-block:: text

    vamos -V work:~/amiga/work -C 68020 myprog

If the program name or one of its arguments begins with a dash, end the vamos
option list with a double dash ``--`` first:

.. code-block:: text

    vamos -V work:~ -- myprog -verbose

Use ``--config-debug`` to log how the configuration was parsed and
``--config-dump`` to print the final merged configuration.

Environment variables
---------------------

vamos does not read general option values from the environment. A few special
variables exist:

* ``AMITOOLS_CONFIG_DEBUG`` -- any set value enables configuration-parser debug
  logging.
* ``VAMOS_PROFILE`` -- enable Python ``cProfile`` profiling of the run; set it to
  a filename to write cProfile data and print a summary, or to ``dump`` to print
  the summary only.

Host environment variables and ``~`` are expanded inside the host part of a
volume mapping, for example ``sys=$HOME/amiga/system``. They expand to host
paths; they do not set vamos options.
