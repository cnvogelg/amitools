########
hunktool
########

*load and dump Amiga Hunk executables, libraries, object files and overlays*

************
Introduction
************

The ``hunktool`` is the Swiss-army knife for the Amiga Hunk file format -- the
format of Amiga executables, shared libraries, object files and overlays. It can
validate a file, print its structure, relocate a program that can be loaded with
``LoadSeg()`` to a base address and disassemble its code segments. It also reads
ELF files to help porting code between the two formats.

Input files are scanned like the other amitools: in addition to plain files,
``hunktool`` looks inside ADFS (``.adf``/``.hdf``) images and ``.lha``/``.zip``
archives for Hunk files.

*****
Usage
*****

::

  hunktool <command> [options] <file> [file2 ...]

The available commands are ``validate``, ``info``, ``elfinfo`` and
``relocate``.

********
Commands
********

``validate``
  Read every file and report its type and any parse errors, without printing
  the full structure. This is the quick "is this a valid Hunk file?" check::

    > hunktool validate myprog

``info``
  Print the file structure. The verbose output lists the hunks, the built
  segments, overlays, required libraries and units::

    > hunktool -v info myprog
    > hunktool info -A -x myprog      # disassemble and hexdump segments

``elfinfo``
  Read an ELF file and dump its sections, symbols and relocations::

    > hunktool elfinfo myprog.elf

``relocate``
  Relocate a program that can be loaded with ``LoadSeg()`` to a base address and
  print the segment base addresses, sizes and relocated data::

    > hunktool relocate -B 0x10000 myprog
    > hunktool relocate -B 0x10000 -x myprog   # also hexdump the result

*******
Options
*******

* ``-d`` / ``--dump``: dump the raw hunk structure
* ``-v`` / ``--verbose``: be more verbose
* ``-s`` / ``--stop``: stop on the first error instead of continuing
* ``-R`` / ``--show-relocs``: show relocation entries
* ``-D`` / ``--show-debug``: show debug info entries
* ``-A`` / ``--disassemble``: disassemble code segments
* ``-S`` / ``--disassemble-start ADDR``: start address for the disassembly
* ``-x`` / ``--hexdump``: dump segments in hex
* ``-b`` / ``--brief``: show only brief information
* ``-B`` / ``--base-address ADDR``: base address for relocation
* ``-c`` / ``--cpu CPU``: disassemble for the given CPU (default ``68000``)

For each processed file the tool prints the file name, the parse time and the
recognized file type, and at the end a summary of the results per error code.
