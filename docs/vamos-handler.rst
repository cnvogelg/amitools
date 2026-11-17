vamos - File System Handlers
============================


Concept
-------

AmigaDOS reaches a file system through a *handler*: the DOS layer sends
``ACTION_*`` packets to a handler process and only ever sees opaque handles
(locks, file handles) and result structures in return. vamos mirrors this
split with a small Python *handler API*: a handler maps each AmigaDOS packet
onto one Python method, and the emulated ``dos.library`` only ever talks to
that API. It never touches a host path.

Keeping the boundary packet-shaped has two advantages:

- The DOS layer is independent of how a file system is implemented: a host
  directory, an in-memory volume, a device, or a real AmigaDOS file system all
  look the same.
- The same API is the seam a real packet transport adapts to: the packet
  bridge turns a handler call into an actual ``DosPacket`` and the packet
  transport sends it to a handler port, so a handler can also be reached by
  m68k code that speaks DOS packets directly.

The handler API lives in :mod:`amitools.vamos.handler`. The registry and
volume/device plumbing live in :mod:`amitools.vamos.handler.mgr`; the DOS
layer in :mod:`amitools.vamos.lib.DosLibrary` calls into it.


API reference
-------------

Handler
~~~~~~~

``Handler`` is the base class. Every action a handler does not implement raises
``HandlerError`` with ``ERROR_ACTION_NOT_KNOWN``, so the DOS layer reports it
exactly like AmigaDOS reports an unknown packet.

``is_filesystem`` distinguishes a real file system (a volume) from a device
such as ``NIL:`` or ``CONSOLE:``.

The action methods are grouped into three families:

**Locks** (a lock names an object; it is released again with ``free_lock``):

- ``locate_object(ami_path, exclusive=False)`` -- resolve a path to a lock
  (``ACTION_LOCATE_OBJECT``).
- ``free_lock(lock)`` -- release a lock (``ACTION_FREE_LOCK``).
- ``copy_dir(lock)`` -- replicate a lock on the same object
  (``ACTION_COPY_DIR``; this is ``LOCATE_OBJECT`` with an empty name and works
  on files and directories alike).
- ``parent(lock)`` -- lock the parent directory (``ACTION_PARENT``); the volume
  root has no parent.
- ``same_lock(a, b)`` -- do two locks name the same object
  (``ACTION_SAME_LOCK``).
- ``examine_object(lock)`` -- return ``HandlerFileInfo`` for the locked object
  (``ACTION_EXAMINE_OBJECT``).
- ``examine_next(lock, key)`` -- return the next ``HandlerFileInfo`` in a
  directory scan, or raise ``ERROR_NO_MORE_ENTRIES`` (``ACTION_EXAMINE_NEXT``).
- ``info(lock)`` / ``disk_info(lock)`` -- return ``HandlerInfoData`` for a lock
  or, with ``lock=None``, for the whole volume (``ACTION_INFO`` /
  ``ACTION_DISK_INFO``).
- ``fh_from_lock(lock, mode=MODE_OLDFILE)`` -- open the locked object as a file
  (``ACTION_FH_FROM_LOCK``).
- ``parent_fh(fh)`` / ``copy_dir_fh(fh)`` -- lock the parent of, or the object
  behind, an open file handle (``ACTION_PARENT_FH`` / ``ACTION_COPY_DIR_FH``).

**Files** (a ``HandlerFile`` is the opaque open-file handle):

- ``find_input(ami_path)`` / ``find_output(ami_path, mode)`` /
  ``find_update(ami_path)`` -- open a file for reading / writing / updating
  (``ACTION_FINDINPUT`` / ``ACTION_FINDOUTPUT`` / ``ACTION_FINDUPDATE``).
- ``read(fh, size)`` / ``write(fh, data)`` -- ``ACTION_READ`` /
  ``ACTION_WRITE``.
- ``seek(fh, offset, whence)`` -- ``ACTION_SEEK``.
- ``set_file_size(fh, size, mode)`` -- ``ACTION_SET_FILE_SIZE``.
- ``flush(fh)`` -- ``ACTION_FLUSH``.
- ``end(fh)`` -- close a file (``ACTION_END``).
- ``set_mode(fh, cooked)`` / ``wait_for_char(fh, timeout)`` -- console-only
  operations (``ACTION_SCREEN_MODE`` / ``ACTION_WAIT_CHAR``).

**Names** (path-based operations that need no open handle):

- ``delete_object(ami_path)`` -- ``ACTION_DELETE_OBJECT``.
- ``rename_object(old_path, new_path)`` -- ``ACTION_RENAME_OBJECT``.
- ``set_protect(ami_path, mask)`` -- ``ACTION_SET_PROTECT``.
- ``set_comment(ami_path, comment)`` -- ``ACTION_SET_COMMENT``.
- ``set_date(ami_path, date)`` -- ``ACTION_SET_DATE``.
- ``create_dir(ami_path)`` -- ``ACTION_CREATE_DIR``.

``ACTION_METHODS`` is the 1:1 map from method name to ``DosAction``. The
invariant is that *every* public action method models exactly one AmigaDOS
packet, so the packet bridge can translate a method call into the matching
``DosPacket`` without a special case. Methods that have no packet are
deliberately *not* part of the handler API: ``tell`` and ``is_interactive`` are
answered by the DOS file handle itself, and lifecycle methods such as
``shutdown`` are not actions.

Errors and modes
~~~~~~~~~~~~~~~~

A handler signals failure with ``HandlerError(code, msg=None)``, where ``code``
is a DOS-compatible error code. The constants (in
:mod:`amitools.vamos.handler.base`) are:

``ERROR_NO_FREE_STORE`` 103, ``ERROR_BAD_NUMBER`` 115,
``ERROR_OBJECT_IN_USE`` 202, ``ERROR_OBJECT_EXISTS`` 203,
``ERROR_OBJECT_NOT_FOUND`` 205, ``ERROR_ACTION_NOT_KNOWN`` 209,
``ERROR_INVALID_COMPONENT_NAME`` 210, ``ERROR_INVALID_LOCK`` 211,
``ERROR_OBJECT_WRONG_TYPE`` 212, ``ERROR_RENAME_ACROSS_DEVICES`` 215,
``ERROR_DIRECTORY_NOT_EMPTY`` 216, ``ERROR_TOO_MANY_LEVELS`` 217,
``ERROR_SEEK_ERROR`` 219, ``ERROR_DISK_FULL`` 221,
``ERROR_DELETE_PROTECTED`` 222, ``ERROR_WRITE_PROTECTED`` 223,
``ERROR_READ_PROTECTED`` 224, ``ERROR_NO_MORE_ENTRIES`` 232,
``ERROR_NOT_IMPLEMENTED`` 236.

The DOS layer maps the code to ``IoErr``. The open modes passed to the
``find_*``/``fh_from_lock`` methods are ``MODE_OLDFILE`` (1005),
``MODE_NEWFILE`` (1006), and ``MODE_READWRITE`` (1004).

Result and handle types
~~~~~~~~~~~~~~~~~~~~~~~

- ``HandlerLock`` -- an opaque lock. ``key`` is a hashable identity of the
  locked object *within its handler*; the DOS layer groups locks with the same
  ``key`` (``fl_Key``). ``handler`` points back to the owning handler.
- ``HandlerFile`` -- an opaque open file. ``fobj`` is the underlying stream the
  DOS file handle reads/writes. The flags tell the DOS layer how to wrap it:
  ``is_nil`` (the ``NIL:`` sink), ``need_close`` (whether closing the handle
  closes the stream; console handles share the host stream), and ``auto_flush``
  (flush after every write).
- ``HandlerFileInfo`` -- the ``FileInfoBlock`` fields: ``name``,
  ``entry_type``/``is_dir`` (``DIR`` = 2, ``FILE`` = -3), ``protection``,
  ``size``, ``blocks``, ``date``, ``comment``, and ``key`` (the next scan key).
- ``HandlerInfoData`` -- the ``InfoData`` fields: ``num_blocks``,
  ``num_blocks_used``, ``bytes_per_block``, ``disk_type``, ``disk_state``
  (``DISK_STATE_VALIDATED`` = 82 / ``DISK_STATE_WRITE_PROTECTED`` = 80),
  ``num_soft_errors``, and ``unit_number``.

HandlerManager
~~~~~~~~~~~~~~

``HandlerManager`` owns the registered handlers and resolves Amiga paths to
them. It is built once at startup and passed to the DOS layer.

- Registration: ``register(name, handler)``, ``unregister(name)``,
  ``get_handler(name)`` (case-insensitive), ``get_all_names()``, and
  ``shutdown()`` (calls a handler's ``shutdown`` if it has one).
- ``bind_volume(volume)`` creates and registers the handler selected by a
  volume's ``?handler=<type>`` config option (default ``hostfs``); an unknown
  type raises ``ERROR_ACTION_NOT_KNOWN``.
- Path-based dispatch: ``locate_object``, ``find_input``/``find_output``/
  ``find_update``, ``delete_object``, ``rename_object``, ``set_protect``/
  ``set_comment``/``set_date``, and ``create_dir``. A path is resolved to one
  or more ``(handler, rel_path)`` candidates (multi-assign order) and the first
  one that succeeds wins; ``find_output`` prefers an existing object in any
  candidate and creates a new one only in the first. A bare device prefix that
  the path layer cannot resolve (``NIL:``, ``CONSOLE:``) is looked up directly.
- ``list_dir``, ``path_exists``, ``is_filesystem``, and
  ``disk_info(volume_name)`` (a lock-less ``ACTION_DISK_INFO`` query, used by
  ``Info()`` when a lock has no handler lock).
- ``attach_packet_transport(...)`` hands the live machine to handlers that need
  a packet transport. ``build_handler_manager(...)`` is the top-level entry
  point: it binds every volume and creates the ``?create`` assign directories
  that live on a non-host volume (which has no host path to create them in).

HandlerRegistry
~~~~~~~~~~~~~~~

``HandlerRegistry`` maps a lower-cased type name to a factory
``(name, path, cfg, file_system) -> Handler``. ``default_registry()`` returns a
registry with the built-in types ``hostfs``, ``ram``, ``nil``, ``console``, and
``packet``. ``get_all_types()`` lists them and ``create(...)`` builds one (or
returns ``None`` for an unknown type).


Built-in handlers
-----------------

``hostfs`` -- ``HostFileSysHandler``
    The default. Backs a volume with a host directory tree; every path is
    resolved relative to the volume root and mapped to the host file system
    case-insensitively.

``ram`` -- ``RamHandler``
    An in-memory AmigaDOS file system. It keeps a tree of files in shared
    ``bytearray`` buffers (all open handles see each other), so no host temp
    directory is needed. The nominal capacity is set with ``?size=<kb>``
    (default 1024 KiB).

``nil`` -- ``NilHandler``
    The ``NIL:`` sink: every read returns EOF and every write is discarded. It
    is a device, not a file system.

``console`` -- ``ConsoleHandler``
    ``CONSOLE:`` (and its alias ``*``) on the host standard input/output. It
    owns the tty (termios) handling and the ESC/CSI and Latin-1 to UTF-8
    conversions; the DOS layer only sees a plain byte stream.

``packet`` -- ``DosPktHandler``
    A bridge that sends handler calls to a real AmigaDOS handler port
    (``?handler=packet&port=<name|addr>``). It is created before the port
    manager exists and is attached to the live machine once ``exec.library``
    is up.


Writing a handler
-----------------

Subclass ``Handler``, implement the actions the file system supports, and
register a factory under a type name. The following minimal handler knows a
single empty root directory:

.. code-block:: python

    from amitools.vamos.handler import (
        Handler,
        HandlerError,
        HandlerFileInfo,
        HandlerLock,
        HandlerRegistry,
    )
    from amitools.vamos.handler.base import ERROR_OBJECT_NOT_FOUND


    class MemoryHandler(Handler):
        """a handler that only knows an empty root directory"""

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

    def memory_factory(name, path, cfg, file_system):
        return MemoryHandler(name)

    registry = HandlerRegistry()
    registry.add_type("mem", memory_factory)

Select it on a volume with ``?handler=mem``. A handler that only implements a
subset of the actions is fine: the unimplemented ones raise
``ERROR_ACTION_NOT_KNOWN``.


Selection
---------

A volume selects its handler with ``?handler=<type>`` in its spec; without the
option it uses ``hostfs`` and maps to a host directory::

    vamos -V work:/abs/path?handler=hostfs myprog
    vamos -V scratch:?handler=ram myprog

The auto ``ram:`` volume uses the ``ram`` handler and the auto ``root:`` volume
uses ``hostfs``. ``NIL:`` and ``CONSOLE:`` always exist as built-in devices,
so they need no volume definition. See :doc:`vamos` for the volume model and
:doc:`vamos-ref` for the command-line and config options.
