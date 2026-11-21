vamos - virtual AmigaOS
=======================

.. toctree::
    :maxdepth: 2
    :hidden:

    user/index
    dev/index

Introduction: the virtual AmigaOS runtime (aka Wine for Amiga)
--------------------------------------------------------------

vamos runs AmigaOS m68k command line programs directly on your Mac or PC. It is
to AmigaOS roughly what `Wine <https://www.winehq.org/>`_ is to Windows: instead
of emulating a complete machine, it provides an implementation of the AmigaOS
*application programming interface* and runs the program's own m68k code on the
host.

vamos uses the Musashi m68k CPU emulator (written in C) for the program code.
Every call into a system library is trapped and handled by Python code that
emulates the behaviour of Exec and DOS. This is enough to run typical console
binaries -- compilers, assemblers and build tools -- and even to build complete
Amiga projects, including AmigaOS itself.

Because vamos emulates the API and not the hardware, it cannot run programs that
access the custom chips directly. A subset of graphics and Intuition APIs is
available through SDL windows or offline PNG output; see :doc:`user/graphics`.
Programs requiring chipset emulation or unsupported GUI APIs need a full machine
emulator such as FS-UAE or WinUAE. Remember:
vamos is an API-level emulator and will never be a full Amiga system emulator.

Features
--------

* Fast m68k CPU emulation with the Musashi CPU emulator
* Native library loading for application libraries (e.g. SAS ``sc1.library``)
* DOS library support: locks, files (open, read, write, seek, close)
* A handler-based file system layer: host directories, an in-memory volume,
  AmigaDOS file systems in image files (ADF/HDF/RDB), and the ``NIL:`` /
  ``CONSOLE:`` devices (see :doc:`dev/handler`)
* Exec library support: AllocMem/Vec, LoadLibrary
* A real Amiga Shell and many useful tracing, logging and profiling features

First run
---------

Install the ``vamos`` extra (see the project README) and run an Amiga binary:

.. code-block:: text

    vamos a68k

vamos loads the binary, runs it on the emulated CPU and forwards its output.
Many programs need a little setup first, for example a volume that maps a host
directory into the Amiga world:

.. code-block:: text

    vamos -V work:~/amiga/work myprog

See the :doc:`user/config` for the configuration concept and
:doc:`user/options` for the full option reference.

Documentation
-------------

**User's Manual**

* :doc:`user/config` -- the configuration concept (INI/JSON files and the command line)
* :doc:`user/options` -- every command-line option, grouped and with examples
* :doc:`user/running` -- running programs, the search path and the Amiga Shell
* :doc:`user/graphics` -- graphics support, SDL windows and offline PNG output
* :doc:`user/debugging` -- logging, tracing, disassembly and profiling

**Developer's Manual**

* :doc:`dev/architecture` -- how vamos is built and how the packages fit together
* :doc:`dev/handler` -- the file system handler layer and its API
* :doc:`dev/lib` -- library loading and configuration
* :doc:`dev/api` -- Python API reference and examples
