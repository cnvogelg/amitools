Debugging and analysis
======================

vamos ships several mechanisms to see what a program does, why it fails and
where it spends its time. This chapter describes them; the matching
command-line options are listed in :doc:`options`.

Logging
-------

Everything vamos reports goes through named **logging channels**. Each channel
has a **level**; a message is only shown if the channel's level is high enough.
You control the channels with ``-l CHANNEL:LEVEL`` (repeatable, comma-separated)
and write to a file with ``-L FILE``:

.. code-block:: text

    vamos -l dos:info,exec:debug -L vamos.log myprog

Levels are ``debug``, ``info``, ``warn``, ``error``, ``fatal`` and ``off``. Use
``all:debug`` to enable every channel. The channels are:

* **machine**: ``main``, ``mode``, ``mem``, ``mem_map``, ``mem_alloc``,
  ``mem_int``, ``instr``, ``machine``, ``schedule``, ``hw``
* **libraries**: ``lib``, ``libmgr``, ``segload``, ``dos``, ``exec``,
  ``utility``, ``math``, ``intuition``, ``timer``
* **file systems**: ``path``, ``file``, ``lock``, ``doslist``, ``handler``
* **run control**: ``proc``, ``prof``, ``tp``

``-v`` raises the main logging to be more verbose, ``-q`` reduces it, and
``--no-ts`` omits the timestamps. In a configuration file the same setting is
``logging=dos:info,exec:debug`` in the ``[vamos]`` section. The profiler channel
``prof`` is preset to ``info``.

Instruction and memory tracing
------------------------------

Tracing shows the code that runs and the memory it touches.

* ``-I`` (**instruction trace**) logs every executed instruction. Each line is
  disassembled and shown with its address:

  .. code-block:: text

      vamos -I -l instr:info myprog

  Add ``-r`` to dump the CPU registers before each traced instruction.

* ``-t`` (**memory trace**) logs every CPU memory access. Because it traps each
  read and write it is very slow, so enable it only for debugging:

  .. code-block:: text

      vamos -t -l mem:info myprog

* ``-T`` (**vamos RAM trace**) additionally traces vamos' *own* internal memory
  accesses during a library trap, which is useful to see how a trap modifies
  the emulated structures.

* ``-B`` (**labels**) attaches memory labels to the trace output (see below).

The traces are written to the ``instr`` and ``mem``/``mem_int`` channels, so you
combine the switches with ``-l`` to choose the level. ``mem:info`` shows
trapped library calls and structure accesses; ``mem:debug`` logs *every* access:

.. code-block:: text

    > ./vamos -t -T -l mem:info a68k
    19:23:36.033  mem: INFO:  R(2): 00f7c6: 4e70   TRAP   [@00f5bc +00020a exec.library] -306 [51]
    19:23:36.035  mem: INFO:  R(4): 00fa0c: 0000f4d8  Struct [@00f5bc +000450 exec.library] ExecLibrary+276 = ThisTask(Task*)+0
    19:23:36.035  mem: INFO:  R(4): 00f570: 00000000  Struct [@00f4d8 +000098 ThisTask] Process+152 = pr_CurrentDir(BPTR)+0

Each line labels the accessed address with its source (a library or a code
segment) and shows symbolic names of structure fields.

Label manager
-------------

The names in the trace output come from the **label manager**. A label describes
a memory range and gives it a name. Labels are created automatically while the
emulation is set up:

* ``LabelRange`` -- a plain named range.
* ``LabelSegment`` -- a loaded code segment, named after the binary and segment
  index (``a68k:0:code``).
* ``LabelStruct`` -- a known in-memory structure, so accesses are shown as
  ``Process+152 = pr_CurrentDir``.
* ``LabelLib`` -- a library base, shown with its negative/positive offsets
  (``exec.library base=... -N+M``).

The memory map, the loader (segments) and the library types register these
labels as memory is set up. When ``-B`` is enabled, the trace manager asks the
label manager for the label covering an address and prints its name and offset
instead of a bare address. Without labels, the traces still show the raw
address and value.

Disassembly
-----------

Instruction tracing disassembles each executed instruction on the fly. The
disassembler is the small ``DisAsm`` helper around the CPU core. It can also be
used directly to disassemble raw memory or a block of code:

.. code-block:: python

    from amitools.vamos.machine import DisAsm

    dasm = DisAsm.create("68020")
    num_bytes, text = dasm.disassemble(0x2000)
    code = dasm.disassemble_block(data, start_pc=0x2000)
    dasm.dump_block(code)  # print "<addr>: <words>  <mnemonic>"

A library trap is shown as a Python trap: the ``dc.w $a...`` opcode is replaced
by ``PyTrap #$<id> ; <function name>``, so the trace names the trapped function
instead of an opaque word.

For a *static* disassembly of a binary (not a live run), use the ``hunktool``
command:

.. code-block:: text

    hunktool --disassemble --disassemble-start 0 myprog

See the ``hunktool`` help for the CPU selection and the other analysis commands.

Profiling and performance
-------------------------

The **profiler** measures how much time is spent inside the Python library
replacements. Enable it with ``--profile`` and choose what to record:

.. code-block:: text

    vamos --profile --profile-libs exec.library,dos.library --profile-dump myprog

* ``--profile-libs NAMES`` -- profile the named libraries/devices or ``all``.
* ``--profile-lib-calls`` -- record individual library calls.
* ``--profile-file FILE`` / ``--profile-file-append`` -- write the profile to a
  JSON file, optionally appending to an existing one.
* ``--profile-dump`` -- print the result to the ``prof`` log channel.

The profile file is JSON with a version header and a ``libs`` section:

.. code-block:: json

    {
      "vamos_profile": "1.0",
      "libs": { "...": {} }
    }

Post-process a saved profile with the ``vamostool libprof`` commands:

.. code-block:: text

    vamostool libprof dump     profile.json   # per-library/function timing
    vamostool libprof missing  profile.json   # library functions not implemented
    vamostool libprof coverage profile.json   # implementation/call coverage
    vamostool libprof coverage -f profile.json  # also list uncovered functions

For Python-level profiling of vamos itself, set ``VAMOS_PROFILE`` to a filename
(write ``cProfile`` data and print a summary) or to ``dump`` (print the summary
only).

**Reading the performance.** With ``-v`` vamos prints a summary line with the
emulated speed, for example:

.. code-block:: text

    done (284836 cycles in 0.0025s -> 114.19 MHz, trap time 0.0083s)

The cycle count and MHz describe the m68k core; ``trap time`` is the time spent
in the Python library emulation. ``--slice-cycles`` sets the scheduler quantum
(in m68k cycles) that determines how long a task runs before vamos can switch to
another -- it is not a maximum execution-cycle limit.

The repository contains a benchmark suite under ``test/benchmark`` (run with
`pytest-benchmark <https://pytest-benchmark.readthedocs.io/>`_) that measures the
library stub both plain and with profiling/logging enabled, so changes to the
trap path can be compared.
