#######
fdtool
#######

*read Commodore ``.fd`` function description files and dump or generate code from them*

************
Introduction
************

A ``.fd`` file is Commodore's plain-text description of an Amiga library: it
names the library base, lists every function with its LVO bias (the offset from
the library base) and documents the registers each function takes its arguments
in. The ``fdtool`` reads one or more of these files and either prints the
function table or generates code from it.

The generated output is used when building vamos libraries and m68k stubs, but
the tool is also handy to simply look up the vector number or argument layout of
a library function.

*****
Usage
*****

::

  fdtool [options] <file.fd> [file2.fd ...]

Without any generation option, ``fdtool`` prints the function table of each
file::

  > fdtool exec_lib.fd
  exec_lib.fd
    base: exec.library
    #0001     -552  0xfd48                   Supervisor UserData
    #0002     -540  0xfe94                      ExecPrivate1
    ...

The columns are the running function number, the LVO bias in decimal and hex,
the function name and its register arguments.

*******
Options
*******

* ``-P`` / ``--add-private``: also list functions marked as private in the
  ``.fd`` file. By default private functions are skipped.
* ``-p`` / ``--gen-python``: generate Python tuples ``(bias, name, args)`` for
  the vamos library stubs::

    > fdtool -p exec_lib.fd

* ``-f FILE`` / ``--gen-fd FILE``: write a new ``.fd`` file containing the
  functions read from the input (useful to filter or normalize a ``.fd``)::

    > fdtool -f new_exec.fd exec_lib.fd

* ``-c FILE`` / ``--gen-sasc FILE``: generate SAS/C function stubs (one empty
  ``__asm __saveds`` function per library entry)::

    > fdtool -c exec_stubs.c exec_lib.fd

* ``-E PREFIX`` / ``--prefix PREFIX``: prefix the generated C function names,
  for example to avoid clashes with the real library::

    > fdtool -c stubs.c -E MyLib_ exec_lib.fd

Any number of the generation options can be combined in one invocation.
