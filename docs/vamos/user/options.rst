Command-line reference
======================

``vamos`` runs an AmigaOS m68k command on the host. This page documents every
option accepted by the current command-line parser, grouped into logical
sections. For the configuration concept behind the file keys, see
:doc:`config`; for background and examples see :doc:`running`.

.. code-block:: text

    vamos [options] [--] <program> [program-arguments ...]

Options normally precede the Amiga program. Use ``--`` to end option parsing
when the program name or its arguments begin with ``-``. Run ``vamos --help``
to display the same options in the terminal.

Configuration and help
----------------------

``-h``, ``--help``
    Show help and exit.

    .. code-block:: text

        vamos --help

``-c FILE``, ``--config-file FILE``
    Read configuration from a specific INI or JSON file instead of the default
    ``.vamosrc`` discovery.

    .. code-block:: text

        vamos -c ./vamosrc myprog

``-S``, ``--skip-configs``
    Do not load any configuration file. Useful for a clean, reproducible setup.

    .. code-block:: text

        vamos -S myprog

``--config-debug``
    Log configuration-parser details.

    .. code-block:: text

        vamos --config-debug myprog

``--config-dump``
    Print the final merged configuration and exit.

    .. code-block:: text

        vamos --config-dump myprog

Paths, assigns and volumes
--------------------------

Amiga paths and assigns use AmigaOS syntax. ``--volume`` maps an Amiga volume
name to a host directory; ``--assign`` maps an Amiga assign name to an Amiga
path. Options that accept lists can be repeated or take comma-separated values.

``-V NAME:HOST-PATH``, ``--volume NAME:HOST-PATH``
    Map a host directory to an Amiga volume. Repeat for more volumes.

    .. code-block:: text

        vamos -V sys:$HOME/amiga/system -V work:$HOME/amiga/work myprog

    A volume spec may carry options after ``?``, such as ``?create`` (create
    the host directory). The ``handler`` option selects the handler that backs
    the volume: ``hostfs`` (a host directory, the default), ``ram`` (an
    in-memory file system), ``adfs`` (an AmigaDOS file system inside an image
    file), or the ``nil``/``console`` devices. A non-host volume needs no host
    path, and ``ram`` accepts a nominal size in KiB.

    .. code-block:: text

        vamos -V work:/abs/path?handler=hostfs -V scratch:?handler=ram,size=2048 myprog

    A volume whose source is a *file* is an ADFS image volume: the handler
    defaults to ``adfs`` and the file is not mapped to the host file system.
    The image is a raw floppy image (``.adf``), a hardfile (``.hdf``) or one
    RDB partition (``.rdb``); the type is auto-detected, ``?img=`` forces it
    (``adf``/``adf_hd``/``hdf``/``rdb``, or ``xdf`` for "raw image, detect")
    and ``?part=`` selects the RDB partition.

    .. code-block:: text

        vamos -V work:disk.adf myprog
        vamos -V work:disk.rdb?part=1 myprog

    See :doc:`../dev/handler` for the handler layer and how to write your own.

``-a NAME:AMIGA-PATH``, ``--assign NAME:AMIGA-PATH``
    Define an Amiga assign. Use ``+`` to add paths to a multi-assign.

    .. code-block:: text

        vamos -a c:sys:c -a include:sys:include myprog

``-p PATH``, ``--path PATH``
    Set the command search path; comma-separate Amiga paths.

    .. code-block:: text

        vamos -p sys:c,work:bin myprog

``--cwd AMIGA-PATH``
    Set the Amiga current working directory. By default it is derived from the
    host working directory.

    .. code-block:: text

        vamos --cwd work:src myprog

``--vols-base-dir HOST-PATH``
    Set the host directory used for local volumes.

    .. code-block:: text

        vamos --vols-base-dir ./vamos-volumes myprog

``--auto-volumes NAME,...``
    Select the automatically created volumes (``root`` and ``ram`` by default);
    use ``off`` to disable them. ``root`` is a host directory (the host ``/``)
    and ``ram`` is the in-memory ``ram`` handler.

    .. code-block:: text

        vamos --auto-volumes root,ram myprog

``-A NAME,...``, ``--auto-assigns NAME,...``
    Select the automatically created assigns (``c``, ``s``, ``libs``, ``devs``
    and ``t`` by default); use ``off`` to disable them.

    .. code-block:: text

        vamos -A c,libs myprog

Disks
-----

``-D IMAGE``, ``--disk IMAGE``
    Expose a disk image through ``scsi.device``; repeat to add units in order.
    An RDB image publishes its partitions as DOS devices; a raw ADF/HDF (or
    gzipped ``.adz``/``.hdz``) is exposed as one whole-disk device.

    .. code-block:: text

        vamos --disk work.hdf myprog
        vamos -D work.hdf -D floppy.adf myprog

    A value may carry per-image options as ``IMAGE?key=val,key=val``:
    ``rw``/``ro`` select the read/write mode, ``part=<NAME|INDEX>`` exposes a
    single RDB partition instead of all of them, ``name=<NAME>`` sets the raw
    device name, and ``type=``/``bs=``/``chs=``/``algo=`` override the raw
    geometry.

    .. code-block:: text

        vamos --disk floppy.adf?name=DF0 myprog
        vamos --disk work.hdf?rw,bs=512 myprog
        vamos --disk big.hdf?part=DH1 myprog

``--disk-read-write``
    Open every ``--disk`` image read-write instead of read-only, so a native
    file system handler can write through to it. A gzipped floppy (``.adz``) is
    decompressed into memory and re-compressed when it is closed; a gzipped HDF
    stays read-only.

    .. code-block:: text

        vamos --disk work.hdf --disk-read-write myprog

Program and process
-------------------

``-x``, ``--shell``
    Run an Amiga Shell instead of a binary.

    .. code-block:: text

        vamos -x Shell-Seg

``-P``, ``--pure-ami-paths``
    Do not interpret the program name as a host-system path.

    .. code-block:: text

        vamos -P sys:c/myprog

``-R``, ``--raw-arg``
    Parse the single positional string as an Amiga command line, preserving
    Amiga-style quoting.

    .. code-block:: text

        vamos -R -- 'myprog "argument with spaces"'

``-M MODE``, ``--mode MODE``
    Select an execution mode. Available modes are ``proc`` and ``test``;
    ``list`` prints the available modes.

    .. code-block:: text

        vamos -M list

``-s KIB``, ``--stack-size KIB``
    Set the program stack size in KiB (default: 8).

    .. code-block:: text

        vamos -s 32 myprog

``--set-var NAME=VALUE``
    Set an AmigaDOS local variable before execution; repeat as needed.

    .. code-block:: text

        vamos --set-var MODE=fast --set-var DEST=ram: myprog

``PROGRAM [ARG ...]``
    The positional program name and its arguments.

    .. code-block:: text

        vamos myprog input.dat

Machine and hardware
--------------------

``-b CONFIG``, ``--backend CONFIG``
    Select the machine backend. The default backend is ``machine68k``.

    .. code-block:: text

        vamos -b name:rmachine68k,host:localhost,port:18861 myprog

``-C CPU``, ``--cpu CPU``
    Select the CPU (``68000``, ``68020``, ``68030`` or ``68040``; short forms
    such as ``00``, ``20``, ``30`` and ``40`` are also accepted).

    .. code-block:: text

        vamos -C 68020 myprog

``-m KIB``, ``--ram-size KIB``
    Set emulated RAM in KiB (default: 1024). Exec publishes this allocator as
    Fast RAM through its memory list, with live free chunks. Allocations are
    rounded to eight bytes; this is not chipset DMA memory.

    .. code-block:: text

        vamos -m 8192 myprog

``-e EXCEPTION:MODE,...``, ``--hw-exception EXCEPTION:MODE,...``
    Choose ``ignore``, ``log`` or ``abort`` handling for CPU exceptions.

    .. code-block:: text

        vamos -e zero_div:abort,bus:log myprog

    Accepted exception names are ``bus``, ``address``, ``illegal``,
    ``zero_div``, ``chk``, ``trapv``, ``priv``, ``trace``, ``line_a``,
    ``line_f``, ``irqs`` and ``traps``.

``-H MODE``, ``--hw-access MODE``
    Handle direct hardware-address access with ``emu``, ``ignore``, ``abort``
    or ``disable``. In ``emu`` mode, absent motherboard devices at
    $DA0000-$DEFFFF read as all ones and ignore writes; the absent Kickstart
    image at $F80000-$FFFFFF reads as zero. These are probe defaults, not
    chipset emulation. ``abort`` rejects these accesses and ``ignore`` reads
    zero.

    .. code-block:: text

        vamos -H abort myprog

``--old-dos-guard``
    Reserve memory used to detect access to BCPL addresses.

    .. code-block:: text

        vamos --old-dos-guard myprog

The synthetic system reports PAL timing with 50 Hz vertical and supply
frequencies. The E-clock frequency is 709,379 Hz, matching the counter returned
by ``timer.device/ReadEClock``. The counter advances from host monotonic time;
vamos does not emulate the CIA oscillator.

Libraries and devices
---------------------

``-O OPTIONS``, ``--lib-options OPTIONS``
    Configure a library or device as ``<name>=<key>:<value>``. Separate settings
    with commas, libraries/devices with ``+``, or repeat ``-O``. Supported modes
    include ``auto``, ``vamos``, ``amiga``, ``fake`` and ``off``.

    .. code-block:: text

        vamos -O icon.library=mode:off,version:40 myprog

    See :doc:`../dev/lib` for the library modes and the config-file sections.

Every handler is reachable through its own packet port, so every file system
volume -- a host directory or an in-memory ``ram`` volume -- has a DOS device
entry with a matching handler port. Their capacity comes from the backing file
system (the host filesystem, or the ``ram`` handler's nominal size), so host
mounts on the same filesystem report overlapping space. The ``NIL:`` and
``CONSOLE:`` devices get a device entry backed by their own handler port too
(the ``NIL:`` sink and the console), with no startup message. None of these
entries represent physical block devices and they have no block geometry.

Logging
-------

``-l SETTINGS``, ``--logging SETTINGS``
    Set channel levels as comma-separated ``<channel>:<level>`` pairs. Use
    ``all:debug`` for every channel.

    .. code-block:: text

        vamos -l dos:info,exec:debug myprog

``-L FILE``, ``--log-file FILE``
    Write log messages to a file instead of standard output.

    .. code-block:: text

        vamos -L vamos.log myprog

``-v``, ``--verbose``
    Enable more verbose main logging.

    .. code-block:: text

        vamos -v myprog

``-q``, ``--quiet``
    Reduce logging output.

    .. code-block:: text

        vamos -q myprog

``--no-ts``
    Omit timestamps from log messages.

    .. code-block:: text

        vamos --no-ts myprog

Logging levels are ``debug``, ``info``, ``warn``, ``error``, ``fatal`` and
``off``. Channels include ``main``, ``mode``, ``mem``, ``mem_map``,
``mem_alloc``, ``mem_int``, ``instr``, ``lib``, ``libmgr``, ``path``, ``file``,
``lock``, ``doslist``, ``handler``, ``segload``, ``dos``, ``exec``, ``proc``,
``prof``, ``tp``, ``utility``, ``hw``, ``math``, ``machine``, ``schedule``,
``intuition`` and ``timer``. See :doc:`debugging` for how to use them.

Tracing
-------

``-I``, ``--instr-trace``
    Trace executed instructions.

    .. code-block:: text

        vamos -I myprog

``-t``, ``--memory-trace``
    Trace CPU memory accesses; this can be slow.

    .. code-block:: text

        vamos -t -l mem:info myprog

``-T``, ``--vamos-ram-trace``
    Also trace vamos's internal RAM accesses.

    .. code-block:: text

        vamos -T -l mem:info myprog

``-r``, ``--reg-dump``
    Include register dumps in instruction traces.

    .. code-block:: text

        vamos -I -r myprog

``-B``, ``--labels``
    Add memory labels to tracing output.

    .. code-block:: text

        vamos -t -B -l mem:info myprog

See :doc:`debugging` for the trace output format and the label manager.

Profiling and scheduling
------------------------

``--profile``
    Enable vamos profiling.

    .. code-block:: text

        vamos --profile myprog

``--profile-libs NAMES``
    Profile named libraries/devices or ``all``; may be repeated.

    .. code-block:: text

        vamos --profile --profile-libs exec.library,dos.library myprog

``--profile-lib-calls``
    Record individual library calls.

    .. code-block:: text

        vamos --profile --profile-lib-calls myprog

``--profile-file FILE``
    Save profile data to a file.

    .. code-block:: text

        vamos --profile --profile-file profile.json myprog

``--profile-file-append``
    Append profile data to an existing profile file.

    .. code-block:: text

        vamos --profile --profile-file profile.json --profile-file-append myprog

``--profile-dump``
    Dump profile results to the log.

    .. code-block:: text

        vamos --profile --profile-dump myprog

``--slice-cycles N``
    Set the duration of a scheduler slice in m68k cycles (default: 100000).
    This sets the scheduling quantum; it is not a maximum execution-cycle
    limit.

    .. code-block:: text

        vamos --slice-cycles 50000 myprog

See :doc:`debugging` for the profile file format and the ``vamostool libprof``
post-processing commands.
