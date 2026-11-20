#########
vamospath
#########

*convert between AmigaOS and host paths using a vamos configuration*

************
Introduction
************

The ``vamospath`` converts a path between the AmigaOS world and the host file
system using the same volume and assign configuration as ``vamos`` itself. It
reads the ``.vamosrc`` configuration file (or one given with ``-c``) to learn
the volume mappings and assigns, so an Amiga path such as ``work:src/main.c``
resolves to the host file that ``vamos`` would use -- and vice versa.

This is handy in build scripts and Makefiles that need to translate between the
two worlds.

*****
Usage
*****

::

  vamospath <command> <path>

********
Commands
********

``ami2sys <path>``
  Convert an AmigaOS path to a host (system) path::

    > vamospath ami2sys work:src/main.c
    /home/user/amiga/work/src/main.c

``sys2ami <path>``
  Convert a host (system) path back to an AmigaOS path::

    > vamospath sys2ami /home/user/amiga/work/src/main.c
    work:src/main.c

If the path cannot be resolved, the tool prints an error and returns a non-zero
exit code. The configuration is discovered like for ``vamos`` (``.vamosrc`` in
the current directory, then ``$HOME``); see the
:doc:`../vamos/user/config` for the file format.
