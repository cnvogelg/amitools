Python API reference
====================

vamos is a Python package, and its internals can be used directly. This page
documents the public packages and types with Sphinx autodoc and shows a couple
of short examples. For how the pieces fit together, see :doc:`architecture`.

Handler layer
-------------

The file system handler API. See :doc:`handler` for the concepts and a worked
handler example.

.. automodule:: amitools.vamos.handler
    :members:
    :show-inheritance:

.. automodule:: amitools.vamos.handler.mgr
    :members:
    :show-inheritance:

Library manager
---------------

.. automodule:: amitools.vamos.libmgr
    :members:
    :show-inheritance:

Machine and memory
------------------

.. automodule:: amitools.vamos.machine
    :members:
    :show-inheritance:

.. automodule:: amitools.vamos.mem
    :members:
    :show-inheritance:

Paths
-----

.. automodule:: amitools.vamos.path
    :members:
    :show-inheritance:

Configuration
-------------

.. automodule:: amitools.vamos.cfgcore
    :members:
    :show-inheritance:

Profiling
---------

.. automodule:: amitools.vamos.profiler
    :members:
    :show-inheritance:

Tracing and labels
------------------

.. automodule:: amitools.vamos.trace
    :members:
    :show-inheritance:

.. automodule:: amitools.vamos.label
    :members:
    :show-inheritance:

Disk images
-----------

.. automodule:: amitools.vamos.disk
    :members:
    :show-inheritance:

Examples
--------

Embedding a run
~~~~~~~~~~~~~~~

The top-level ``main`` entry point takes the configuration files to search and
the command-line arguments:

.. code-block:: python

    import os
    from amitools.vamos.main import main

    cfg_files = (
        os.path.join(os.getcwd(), ".vamosrc"),
        os.path.expanduser("~/.vamosrc"),
    )
    ret_code = main(cfg_files, args=["-V", "work:~/amiga/work", "myprog"])

Writing a handler
~~~~~~~~~~~~~~~~~

A file system handler subclasses ``Handler`` and implements the actions it
supports; the rest raise ``ERROR_ACTION_NOT_KNOWN``. Register a factory under a
type name and select it with ``?handler=<type>`` on a volume. See
:doc:`handler` for the full example and the list of actions.

.. code-block:: python

    from amitools.vamos.handler import Handler, HandlerError, HandlerLock, HandlerFileInfo
    from amitools.vamos.handler.base import ERROR_OBJECT_NOT_FOUND

    class EmptyRootHandler(Handler):
        def locate_object(self, ami_path, exclusive=False):
            if ami_path not in ("", ":"):
                raise HandlerError(ERROR_OBJECT_NOT_FOUND)
            return HandlerLock(key="")

        def free_lock(self, lock):
            pass

        def copy_dir(self, lock):
            return HandlerLock(key=lock.key)

        def same_lock(self, a, b):
            return a.key == b.key

        def examine_object(self, lock):
            return HandlerFileInfo(self.name, HandlerFileInfo.DIR)

Disassembling memory
~~~~~~~~~~~~~~~~~~~~

The ``DisAsm`` helper disassembles a single instruction or a block of memory:

.. code-block:: python

    from amitools.vamos.machine import DisAsm

    dasm = DisAsm.create("68000")
    num_bytes, text = dasm.disassemble(0x2000)
    code = dasm.disassemble_block(data, start_pc=0x2000)
    dasm.dump_block(code)
