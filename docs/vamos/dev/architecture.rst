Architecture
============

Building blocks
---------------

vamos uses the native Musashi m68k CPU emulator (written in C) to emulate m68k
code. A simple memory interface provides RAM for the program code, and an
interface for Python to trap library calls and emulate their behaviour.

Every call to a library is trapped during execution and realized with our own
Python code, or simply ignored if no trap is defined. All public in-memory
structures (e.g. ``ExecBase``) are provided too. vamos implements a memory
handler to allocate and free the structures used in the heap of a program or for
library data exchange.

Data flow
---------

A library call runs from the emulated program, through the Python library
emulation, and -- for file systems -- through the handler layer down to a host
directory, an image file or an in-memory volume:

.. code-block:: text

        m68k program
             │  library call (trapped)
             ▼
        ExecLibrary / DosLibrary            Python emulation of the OS API
             │
        LibraryManager ──► native m68k libs / vamos libs / fake libs
             │
        dos.library ──► Handler API ──► HandlerManager
                                            ├── hostfs   (host directory)
                                            ├── ram      (in-memory volume)
                                            ├── nil / console (devices)
                                            ├── adfs     (image file: ADF/HDF/RDB)
                                            ├── packet   (real DOS packet port)
                                            └── native   (original 68k handler)

The handler layer is the boundary between ``dos.library`` and a file-system
implementation: the DOS layer only sees opaque handles and results, never a host
path. It is described in :doc:`handler`.

Packages
--------

The ``amitools.vamos`` package is split into the following sub-packages:

.. list-table::
   :header-rows: 1

   * - Package
     - Responsibility
   * - ``machine``
     - the m68k CPU, the memory interface, traps, registers and disassembly
   * - ``mem``
     - emulated RAM and the memory allocator
   * - ``lib``
     - the Python emulation of the Amiga libraries (Exec, DOS, ...)
   * - ``libcore``
     - the machinery behind a library: stub generation, function scanning,
       profiling and the fd-based dispatch
   * - ``libmgr``
     - library loading, opening, closing and expunging (the LibraryManager)
   * - ``libnative``
     - loading and using original m68k libraries
   * - ``libtypes`` / ``libstructs`` / ``astructs``
     - the in-memory structures and their Python wrappers
   * - ``dos``
     - the ``dos.library`` implementation, split into focused modules
   * - ``lexec``
     - the ``exec.library`` implementation, split into topic mixins
   * - ``handler``
     - the file-system handler API, the manager and the built-in handlers
   * - ``path``
     - Amiga path resolution: volumes, assigns and the command path
   * - ``disk``
     - disk images (RDB and raw ADF/HDF) exposed through ``scsi.device``
   * - ``loader``
     - loading Amiga binaries (hunks, segments, relocations)
   * - ``cfg`` / ``cfgcore``
     - the configuration model shared by the CLI, INI and JSON parsers
   * - ``profiler``
     - the profiling framework and the JSON profile data file
   * - ``trace``
     - instruction and memory tracing
   * - ``label``
     - the memory label manager used by traces
   * - ``task`` / ``schedule``
     - emulated tasks and the scheduler
   * - ``mode``
     - the execution modes (``proc``, ``shell``, ``test``)

See :doc:`api` for the Python reference and examples.
