#######
romtool
#######

*A tool to inspect, dissect, and build Amiga Kickstart ROM images to be
used with emulators, run with soft kickers or burned into flash ROMs*

********
Features
********

* show detailed infos on a Kickstart ROM
* dump ROM as hex
* diff to ROM images
* split a ROM into modules with split data from `Remus/Romsplit`_
* build a new ROM from modules
* concatenate a Kickstart and Ext ROM to a 1 Meg ROM
* patch a ROM
* scan a ROM for residents
* copy a ROM

.. _Remus/Romsplit: http://www.doobreynet.co.uk/

****************
General Commands
****************

``romtool`` is run from the command line typically as follows::

  romtool [-v] [-q] [-k rom.key] <sub_command> <sub_options> ...

romtool always requires a sub command with arbitrary options.

Use ``romtool -h`` to see a list of available commands.

Use ``romtool <sub_cmd> -h`` to see help on the given command.

The following options are available for all sub commands and must precede
the sub command switch:

* ``-v`` be verbose and show processing steps of the tool
* ``-q`` be really quiet and do not print error messages
* ``-k rom.key`` if you want to decrypt encrypted ROMs you have to specify the
  ``rom.key`` file.

*************
Inspect a ROM
*************

``info`` command
================

Show detailed information of a Kickstart ROM::

  $ romtool info amiga-os-310-a500.rom
  size                  ok
  header                ok
  footer                ok
  size_field            ok
  chk_sum               ok
  kickety_split         ok
  magic_reset           ok
  is_kick               ok
  check_sum             9fdeeef6
  base_addr             00f80000
  boot_pc               00f800d2
  rom_rev               40.63
  exec_rev              40.10

The command checks various fields of a Kickstart ROM:

* ``size`` checks if the ROM size is correct: 256 or 512 KiB
* ``header`` checks if the ROM header was found
* ``footer`` checks if a ROM footer was found
* ``size_field`` checks if the size field in the footer was found
* ``chk_sum`` checks if the KickSum is correct
* ``kickety_split`` checks if an extra 256 KiB signature was found
* ``magic_reset`` checks if magic reset opcode was found
* ``is_kick`` checks if all kickstart tests were passed
* ``check_sum`` shows KickSum
* ``base_addr`` start address of ROM
* ``boot_pc`` program counter to start ROM
* ``rom_rev`` ROM revision
* ``exec_rev`` Exec revision


``dump`` command
================

Print the ROM contents as a hex dump::

  $ romtool dump amiga-os-310-a500.rom
  00000000: 11 14 4e f9 00 f8 00 d2 00 00 ff ff 00 28 00 3f  ..N..........(.?
  00000010: 00 28 00 0a ff ff ff ff 00 41 4d 49 47 41 20 52  .(.......AMIGA R
  00000020: 4f 4d 20 4f 70 65 72 61 74 69 6e 67 20 53 79 73  OM Operating Sys
  ...

Options:

* ``-a`` show address of ROM (otherwise image file offset is shown)
* ``-b`` set ROM address to be shown
* ``-c <n>`` how many bytes are shown per line


``diff`` command
================

Compare two ROM images and show the differences as a hex dump::

  $ romtool diff a.rom b.rom
  00000368: -- -- -- -- -- -- -- f8         . | -- -- -- -- -- -- -- f0         .
  00000370: -- -- -- -- -- -- -- f0         . | -- -- -- -- -- -- -- e0         .
  00000378: -- -- -- f8 -- -- -- --     .     | -- -- -- e8 -- -- -- --     .
  ...

Options:

* ``-a`` show address of ROM (otherwise image file offset is shown)
* ``-b`` set ROM address to be shown
* ``-c <n>`` how many bytes are shown per line
* ``-f`` show diff even if ROM sizes differ
* ``-s`` also show same bytes of two ROMs (otherwise only differences)


``scan`` command
================

Scan the ROM for resident entries and show them::

  romtool scan rom.img
  @000000b6  +00003706  NT_LIBRARY    +105  exec.library  exec 40.10 (15.7.93)
  @00003706  +000037b8  NT_UNKNOWN     -55  alert.hook  alert.hook
  @000037b8  +00004740  NT_DEVICE     -120  audio.device  audio 37.10 (26.4.91)
  ...

Details:

* ``@000000b6`` offset of resident in ROM
* ``+00003706`` skip range given in resident
* ``NT_LIBRARY`` node type of resident
* ``+105`` priority of resident
* ``name`` name and id_string of resident

You can also show more infos with the ``-i`` switch::

  romtool scan rom.img -i
  @000000b6  name:       exec.library
            id_string:  exec 40.10 (15.7.93)
            node_type:  NT_LIBRARY
            flags:      RTF_SINGLETASK
            version:    40
            priority:   105
            init off:   000004d4
            skip off:   00003706
  ...


************************
Split a ROM into modules
************************

Splitting a ROM into modules is a pre-processing step that is necessary to
build new ROMs: The libraries and devices are extracted as relocatable
binaries that can be placed into a new ROM.

Splitting a ROM is a difficult process as the borders of the modules are
not clearly marked in the ROM and furthermore the code positions that require
relocation are not marked at all. Therefore splitting is done with the help
of a split data catalog that describes the modules. A catalog is matched with
a ROM by its KickSum.

romtool currently uses the split data that is shipped with Doobrey's fantastic
Amiga tools `Remus/Romsplit`_.


``list`` command
================

Show a list of all ROMs that can be split, i.e. split data is available::

  $ romtool list
  @00e00000  +00080000  sum=9ea68bc4  sum_off=0007ffe8  CD32 Extended ROM
  @00200000  +00040000  sum=34377fe8  sum_off=ffffffff  CD32 MPEG ROM 40.30
  ...

Details:

* ``@00e00000`` base address of ROM
* ``+00080000`` size of ROM (here 512 KiB)
* ``sum=`` KickSum of ROM
* ``sum_off=`` offset in ROM where KickSum is stored (ffffffff means that no
  KickSum is stored inside ROM)

You can filter the list of ROMs by specifying a query that supports wildcards
(* or ?)::

  $ romtool list -r Kick*
  @00fc0000  +00040000  sum=15267db3  sum_off=0003ffe8  Kickstart 34.5 (A500/A2000/A1000)
  @00f80000  +00080000  sum=54876dab  sum_off=0007ffe8  Kickstart 37.175(A3000)
  ...

A list of the contained module entries is shown with the ``-m`` switch::

  $ romtool list -r Kick*40.60* -m
  @00f80000  +00080000  sum=8f4549a5  sum_off=0007ffe8  Kickstart 40.60 (CD32 Main)
    @000000  +003804  =003804  relocs=#   62  exec_40.9(CD32)
    @003804  +000ad8  =0042dc  relocs=#   12  expansion_40.2(A1200)
    @0042dc  +000ea4  =005180  relocs=#   11  mathieeesingbas.lib_40.4(020)
  ...

Details:

* ``@000000`` offset of module in ROM
* ``+003804`` size of module
* ``=003804`` end address of module in ROM
* ``relocs=#`` number of relocations found in module


``query`` command
=================

Check if a given ROM image can be split with the available split data::

  $ romtool query amiga-os-310-a500.rom
  @00f80000  +00080000  sum=9fdeeef6  sum_off=0007ffe8  Kickstart 40.63 (A500/A600/A2000)
    @000000  +0037b8  =0037b8  relocs=#   61  exec_40.10(A500-A600-A2000)
    @0037b8  +0010a0  =004858  relocs=#   28  audio.device_37.10
    @004858  +001634  =005e8c  relocs=#  101  input_40.1
  ...

You can filter the modules shown with a wildcard given in ``-m <wildcard>``::

  $ romtool query amiga-os-310-a500.rom -m int*
  @00f80000  +00080000  sum=9fdeeef6  sum_off=0007ffe8  Kickstart 40.63 (A500/A600/A2000)
    @04f0c4  +0199a0  =068a64  relocs=# 2405  intuition.library_40.85


``split`` command
=================

Perform the ROM split and extract the modules as LoadSeg()able binary files.
A directory named by the ROM is created and next to the modules an index file
called `index.txt` is created that contains an ordered list of the modules
taken from the ROM image::

  $ romtool split amiga-os-310-a500.rom -o .

This call will create a directory called ``40.63(A500-2000)`` named after the
ROM in the current directory and fill it with the ROM's modules. Additionally,
the ``index.txt`` file will be created.

Options:

* ``-o <out_dir>`` output directory where the ROM sub directory will be
  created If omitted no output will be generated!
* ``-m <wildcard>`` do not export all modules but only those that match the
  given wildcard
* ``--no-version-dir`` do not create an extra sub directory with the ROM name
* ``--no-index`` omit creating the ``index.txt`` file


***************
Build a new ROM
***************

``build`` command
=================

Create a new ROM by combining a set of LoadSeg()able binary files. You can
either use modules created by the split command or add your own modules.

You can either give all modules on the command line or you use and index file.
An index file is a simple text file with ``.txt`` extension that gives in each
line a module path::

  $ romtool build -o my.rom -t kick -s 512 index.txt my.library my.device

This command creates a new 512 KiB Kickstart ROM called ``my.rom`` with all
modules given in ``index.txt``.

Options:

* ``-o <out_img>`` write generated ROM to given file. Do not forget to specify
  this switch otherwise no output will be generated!
* ``-t <rom_type>`` what type of ROM to create: either ``kick`` or ``ext``
* ``-s <rom_size>`` size of ROM in KiB (either 256 or 512)
* ``-a <kick_addr>`` base address of Kick ROM in hex (default ``f80000``)
* ``-e <ext_addr>`` base address of Ext ROM in hex (default ``e00000``)
* ``-f`` add a footer to Ext ROM
* ``-r <rom_rev>`` set the ROM revision field, e.g. ``40.95``
* ``-k`` add the *kickety_split*, i.e. in a 512 KiB ROM add an extra ROM header
  after 256 KiB to be compatible with SW assuming 256 KiB ROM. Found in the
  Commodore original ROMs. Will create a small hole around the split.
* ``-b <hex>`` give the byte value to fill empty regions of the ROM


``patches`` command
===================

Show a list of available ROM patches in romtool::

  $ romtool patches
  1mb_rom     Patch Kickstart to support ext ROM with 512 KiB


``patch`` command
=================

Apply one or more patches to the given ROM file and write a patched ROM
image::

  $ romtool patch amiga-os-310-a500.rom 1mb_rom -o out.rom

Apply the ``1mb_rom`` patch to the given rom image and write a new ``out.rom``.

Options:

* ``-o <out_img>`` write generated ROM to given file. Do not forget to specify
  this switch otherwise no output will be generated!


``combine`` command
===================

Concatenate a 512 KiB Kickstart and a 512 KiB Ext ROM image to create a
1 MiB ROM suitable for soft kickers or maprom tools::

  $ romtool combine kick.rom ext.rom -o 1mb.rom

Create a ``1mb.rom`` from the Kickstart ``kick.rom`` and the Ext ROM
``ext.rom``.

Options:

* ``-o <out_img>`` write generated ROM to given file. Do not forget to specify
  this switch otherwise no output will be generated!


``copy`` command
================

Copy a rom to a new file.  In the future, additional transformations may be
possible::

  $ romtool copy kick.rom duplicate.rom

Copy ``kick.rom`` to a new ``duplicate.rom`` file.

Options:

* ``-c``, ``--fix-checksum`` after the copy fix the checksum of the written
image.  For example, if the source rom has been modified with a hex editor or
a find/replace operation, then this option can be used to correct the checksum.
