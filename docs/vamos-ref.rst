vamos command-line reference
============================

``vamos`` runs an AmigaOS m68k command on the host. This page documents the
options accepted by the current command-line parser. For background and
configuration concepts, see :doc:`vamos`.

Command form
------------

::

    vamos [options] [--] <program> [program-arguments ...]

Options normally precede the Amiga program. Use ``--`` to end option parsing
when the program name or its arguments begin with ``-``::

    vamos -V work:/path/to/amiga -- myprog -verbose

The program and its remaining arguments are passed to the Amiga program. With
``-R``, give one quoted Amiga-style command line instead; vamos parses its
program name and arguments as a single string::

    vamos -R -- 'myprog "argument with spaces"'

Run ``vamos --help`` to display the same options directly in the terminal.

Configuration and help
----------------------

* ``-h``, ``--help``: Show help and exit: ``vamos --help``.
* ``-c FILE``, ``--config-file FILE``: Read configuration from a specific INI
  or JSON file: ``vamos -c ./vamosrc myprog``.
* ``-S``, ``--skip-configs``: Do not load configuration files:
  ``vamos -S myprog``.
* ``--config-debug``: Log configuration parsing details:
  ``vamos --config-debug myprog``.
* ``--config-dump``: Print the final configuration:
  ``vamos --config-dump myprog``.

Without ``-c`` or ``-S``, vamos loads the first existing ``.vamosrc`` from the
current directory, then the home directory. Command-line values are applied
after file configuration.

Configure with a file
~~~~~~~~~~~~~~~~~~~~~

The default ``.vamosrc`` is an INI file. Use ``-c FILE`` to load a different
INI or JSON file. For example, this INI configures host volumes, assigns,
paths, the CPU, memory, stack, and logging::

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

Save it as ``./vamosrc`` to have vamos discover it automatically, or specify
it explicitly::

    vamos -c ./vamosrc myprog

JSON configuration uses nested objects. For example, enable the library
profiler and expose a disk image with ``./vamos.json``::

    {
      "profile": {
        "enabled": true,
        "libs": {
          "names": ["exec.library", "dos.library"],
          "calls": true
        },
        "output": {
          "file": "profile.json",
          "append": false,
          "dump": true
        }
      },
      "disks": ["work.hdf"]
    }

::

    vamos -c ./vamos.json myprog

Environment variables
~~~~~~~~~~~~~~~~~~~~~

Environment variables do not provide general overrides for command-line
options or configuration values. The supported special variables are:

* ``AMITOOLS_CONFIG_DEBUG``: Any set value enables configuration-parser debug
  logging: ``AMITOOLS_CONFIG_DEBUG=1 vamos myprog``.
* ``VAMOS_PROFILE``: Enable Python ``cProfile`` profiling of the vamos run.
  Set it to a filename to write cProfile data and print a summary:
  ``VAMOS_PROFILE=run.prof vamos myprog``. Set it to ``dump`` to print the
  summary without writing a profile file:
  ``VAMOS_PROFILE=dump vamos myprog``.

You can also use host environment variables in the host directory part of a
volume mapping in the config file, for example ``sys=$HOME/amiga/system``.
These expand to host paths; they do not set vamos options.

Paths, assigns, and volumes
---------------------------

Amiga paths and assigns use AmigaOS syntax. ``--volume`` maps an Amiga volume
name to a host directory; ``--assign`` maps an Amiga assign name to an Amiga
path. Options that accept lists can be repeated or, where noted, take
comma-separated values.

* ``-V NAME:HOST-PATH``, ``--volume NAME:HOST-PATH``: Map a host directory to
  an Amiga volume. Repeat for more volumes::

      vamos -V sys:$HOME/amiga/system -V work:$HOME/amiga/work myprog

* ``-a NAME:AMIGA-PATH``, ``--assign NAME:AMIGA-PATH``: Define an Amiga
  assign. Use ``+`` to add paths to a multi-assign::

      vamos -a c:sys:c -a include:sys:include myprog

* ``-p PATH``, ``--path PATH``: Set the command search path; comma-separate
  Amiga paths: ``vamos -p sys:c,work:bin myprog``.
* ``--cwd AMIGA-PATH``: Set the Amiga current working directory:
  ``vamos --cwd work:src myprog``. By default it is derived from the host
  working directory.
* ``--vols-base-dir HOST-PATH``: Set the host directory used for local
  volumes: ``vamos --vols-base-dir ./vamos-volumes myprog``.
* ``--auto-volumes NAME,...``: Select automatically created volumes (``root``
  and ``ram`` by default); use ``off`` to disable them:
  ``vamos --auto-volumes root,ram myprog``.
* ``-A NAME,...``, ``--auto-assigns NAME,...``: Select automatically created
  assigns (``c``, ``s``, ``libs``, ``devs``, and ``t`` by default); use
  ``off`` to disable them: ``vamos -A c,libs myprog``.

Program and process
-------------------

* ``-x``, ``--shell``: Run an Amiga Shell instead of a binary:
  ``vamos -x Shell-Seg``.
* ``-P``, ``--pure-ami-paths``: Do not interpret the program name as a
  host-system path: ``vamos -P sys:c/myprog``.
* ``-R``, ``--raw-arg``: Parse the single positional string as an Amiga
  command line, preserving Amiga-style quoting:
  ``vamos -R -- 'myprog "argument with spaces"'``.
* ``-M MODE``, ``--mode MODE``: Select an execution mode. Available modes are
  ``proc`` and ``test``; ``list`` prints the available modes:
  ``vamos -M list``.
* ``-s KIB``, ``--stack-size KIB``: Set the program stack size in KiB
  (default: 8): ``vamos -s 32 myprog``.
* ``--set-var NAME=VALUE``: Set an AmigaDOS local variable before execution;
  repeat as needed: ``vamos --set-var MODE=fast --set-var DEST=ram: myprog``.
* ``PROGRAM [ARG ...]``: The positional program name and arguments:
  ``vamos myprog input.dat``.

Machine and hardware
--------------------

* ``-b CONFIG``, ``--backend CONFIG``: Select the machine backend. For
  example, select the remote backend:
  ``vamos -b name:rmachine68k,host:localhost,port:18861 myprog``. The default
  backend is ``machine68k``.
* ``-C CPU``, ``--cpu CPU``: Select the CPU (``68000``, ``68020``, ``68030``,
  or ``68040``; short forms such as ``00``, ``20``, ``30``, and ``40`` are
  also accepted): ``vamos -C 68020 myprog``.
* ``-m KIB``, ``--ram-size KIB``: Set emulated RAM in KiB (default: 1024):
  ``vamos -m 8192 myprog``.
* ``-e EXCEPTION:MODE,...``, ``--hw-exception EXCEPTION:MODE,...``: Choose
  ``ignore``, ``log``, or ``abort`` handling for CPU exceptions. For example:
  ``vamos -e zero_div:abort,bus:log myprog``.
* ``-H MODE``, ``--hw-access MODE``: Handle direct hardware-address access
  with ``emu``, ``ignore``, ``abort``, or ``disable``:
  ``vamos -H abort myprog``.
* ``--old-dos-guard``: Reserve memory used to detect access to BCPL addresses:
  ``vamos --old-dos-guard myprog``.

Exception names accepted by ``--hw-exception`` are ``bus``, ``address``,
``illegal``, ``zero_div``, ``chk``, ``trapv``, ``priv``, ``trace``, ``line_a``,
``line_f``, ``irqs``, and ``traps``.

Disks, libraries, and devices
-----------------------------

* ``--disk IMAGE``: Expose an RDB disk image through ``scsi.device``; repeat
  to add units in order: ``vamos --disk work.hdf myprog``. The command-line
  disk image is read-only.
* ``-O OPTIONS``, ``--lib-options OPTIONS``: Configure a library or device as
  ``<name>=<key>:<value>``. Separate settings with commas, libraries/devices
  with ``+``, or repeat ``-O``:
  ``vamos -O icon.library=mode:off,version:40 myprog``. Supported modes
  include ``auto``, ``vamos``, ``amiga``, ``fake``, and ``off``.

Logging
-------

* ``-l SETTINGS``, ``--logging SETTINGS``: Set channel levels as
  comma-separated ``<channel>:<level>`` pairs:
  ``vamos -l dos:info,exec:debug myprog``. Use ``all:debug`` for every
  channel.
* ``-L FILE``, ``--log-file FILE``: Write log messages to a file:
  ``vamos -L vamos.log myprog``.
* ``-v``, ``--verbose``: Enable more verbose main logging:
  ``vamos -v myprog``.
* ``-q``, ``--quiet``: Reduce logging output: ``vamos -q myprog``.
* ``--no-ts``: Omit timestamps from log messages: ``vamos --no-ts myprog``.

Logging levels are ``debug``, ``info``, ``warn``, ``error``, ``fatal``, and
``off``. Channels include ``main``, ``mode``, ``mem``, ``mem_map``,
``mem_alloc``, ``mem_int``, ``instr``, ``lib``, ``libmgr``, ``path``, ``file``,
``lock``, ``doslist``, ``segload``, ``dos``, ``exec``, ``proc``, ``prof``,
``tp``, ``utility``, ``hw``, ``math``, ``machine``, ``schedule``, ``intuition``,
and ``timer``.

Tracing
-------

* ``-I``, ``--instr-trace``: Trace executed instructions:
  ``vamos -I myprog``.
* ``-t``, ``--memory-trace``: Trace CPU memory accesses; this can be slow:
  ``vamos -t -l mem:info myprog``.
* ``-T``, ``--vamos-ram-trace``: Also trace vamos's internal RAM accesses:
  ``vamos -T -l mem:info myprog``.
* ``-r``, ``--reg-dump``: Include register dumps in instruction traces:
  ``vamos -I -r myprog``.
* ``-B``, ``--labels``: Add memory labels to tracing output:
  ``vamos -t -B -l mem:info myprog``.

Profiling and scheduling
------------------------

* ``--profile``: Enable vamos profiling: ``vamos --profile myprog``.
* ``--profile-libs NAMES``: Profile named libraries/devices or ``all``; may be
  repeated: ``vamos --profile --profile-libs exec.library,dos.library myprog``.
* ``--profile-lib-calls``: Record individual library calls:
  ``vamos --profile --profile-lib-calls myprog``.
* ``--profile-file FILE``: Save profile data to a file:
  ``vamos --profile --profile-file profile.json myprog``.
* ``--profile-file-append``: Append profile data to an existing profile file:
  ``vamos --profile --profile-file profile.json --profile-file-append myprog``.
* ``--profile-dump``: Dump profile results to the log:
  ``vamos --profile --profile-dump myprog``.
* ``--slice-cycles N``: Set the duration of a scheduler slice in m68k cycles
  (default: 100000): ``vamos --slice-cycles 50000 myprog``. This sets the
  scheduling quantum; it is not a maximum execution-cycle limit.
