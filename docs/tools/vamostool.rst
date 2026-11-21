#########
vamostool
#########

*helpers around vamos: path conversion, type inspection, library profile dumps and state file info*

************
Introduction
************

The ``vamostool`` bundles the small helper tools that ship with ``vamos`` into
a single command with sub-commands. The individual helpers are also available as
standalone tools (``vamospath``, ``typetool``); ``vamostool`` simply groups them
so they share one configuration and command line.

*****
Usage
*****

::

  vamostool <tool> <command> [args]

The available tools are ``path``, ``type``, ``libprof`` and ``state``.

*****
Tools
*****

``path``
  Convert between AmigaOS and host paths using the vamos configuration. Same as
  the standalone ``vamospath`` (see :doc:`vamospath`)::

    > vamostool path ami2sys work:src/main.c
    > vamostool path sys2ami /home/user/amiga/work/src/main.c

``type``
  Inspect the AmigaOS structures vamos uses. Same as the standalone ``typetool``
  (see :doc:`typetool`)::

    > vamostool type list
    > vamostool type dump -O Process
    > vamostool type lookup Process pr_CurrentDir
    > vamostool type offset Process 0x98

``libprof``
  Post-process a library profile written by ``vamos --profile``. The commands
  read the JSON profile file::

    > vamostool libprof dump profile.json       # per-library/function timing
    > vamostool libprof missing profile.json    # library functions not implemented
    > vamostool libprof coverage profile.json   # implementation/call coverage

  ``coverage`` accepts ``-f`` / ``--functions`` to also list the functions that
  were never called. See :doc:`../vamos/user/debugging` for how to create the
  profile file.

``state``
  Inspect a UAE save state file (``.uss``). This can show the RAM and ROM layout
  of a running emulator and even dump AmigaOS structures from the captured
  memory::

    > vamostool state info run.uss
    > vamostool state info -d run.uss             # also dump the state file chunks
    > vamostool state info -s ram run.uss         # save RAM to files with prefix "ram"
    > vamostool state show run.uss ThisTask       # show a structure from the state
    > vamostool state show -r kick.rom run.uss    # provide the ROMs to resolve pointers

  ``state show`` reads the ExecBase from the state, optionally resolves the
  dotted path given as ``what`` and dumps the object (or walks it if it is a
  list). A ROM file must be supplied for each ROM the state references.
