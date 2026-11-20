########
typetool
########

*inspect the AmigaOS C structure definitions vamos uses*

************
Introduction
************

The ``typetool`` exposes the AmigaOS structure definitions that vamos uses
internally. It can list all known types, dump a single structure, look up a
field by its dotted path and find the field at a given byte offset. This is
useful when reading a memory dump or when writing code that accesses emulated
structures.

*****
Usage
*****

::

  typetool <command> [options] <args>

********
Commands
********

``list``
  List the names of all known types::

    > typetool list

``dump <type>``
  Dump a single type with all its fields. ``-O`` / ``--show-offsets`` also
  prints the byte offsets::

    > typetool dump ExecLibrary
    > typetool dump -O Process

``lookup <type> <field.path>``
  Look up a field by its dotted path inside the type::

    > typetool lookup Process pr_CurrentDir
    > typetool lookup ExecLibrary ThisTask

``offset <type> <offset>``
  Find the field that lies at the given byte offset (the offset may be given in
  hex with a ``0x`` prefix)::

    > typetool offset Process 0x98
    > typetool offset ExecLibrary 0x114

Each command prints the matching field(s) or a message on standard error if the
type, field or offset is not found.
