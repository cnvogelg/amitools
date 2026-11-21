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

**Names** (operations on a path or name that need no open file handle):

- ``delete_object(ami_path)`` -- ``ACTION_DELETE_OBJECT``.
- ``rename_object(old_path, new_path)`` -- ``ACTION_RENAME_OBJECT``.
- ``set_protect(ami_path, mask)`` -- ``ACTION_SET_PROTECT``.
- ``set_comment(ami_path, comment)`` -- ``ACTION_SET_COMMENT``.
- ``set_date(ami_path, date)`` -- ``ACTION_SET_DATE``.
- ``create_dir(ami_path)`` -- ``ACTION_CREATE_DIR``.
- ``make_link(lock, name, dest, soft)`` -- ``ACTION_MAKE_LINK``. Creates a link
  named ``name`` in the directory of ``lock``. A soft link (``soft=True``)
  stores ``dest`` as a path string; a hard link (``soft=False``) shares the
  file named by the ``dest`` lock, so both names see the same data and
  metadata.
- ``read_link(lock, path, size)`` -- ``ACTION_READ_LINK``.

The ADFS handler supports both kinds of link; the host file system supports
soft links only (a hard link raises ``ERROR_NOT_IMPLEMENTED``). A hard link
whose target lock belongs to a different handler is
``ERROR_RENAME_ACROSS_DEVICES`` (``HandlerManager`` checks this).

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
  a packet transport. ``attach_native_transport(...)`` does the same for
  ``?handler=native`` volumes: it builds the 68k task host
  (``NativeHandlerManager``) that runs the handler binaries and keeps it as
  ``native_mgr``; ``stop_native_transport()`` stops it. ``build_handler_manager(...)``
  is the top-level entry point: it binds every volume and creates the
  ``?create`` assign directories that live on a non-host volume (which has no
  host path to create them in).
- The transports cannot be attached while the handlers are bound (they need
  exec/dos), so the top-level wiring connects them to the lib manager
  lifecycle: ``SetupLibManager`` exposes ``add_post_setup_callback``/
  ``add_pre_shutdown_callback`` hooks and ``main.wire_handler_transports(...)``
  registers the attach/detach steps on them. The lib manager itself stays
  handler-agnostic.

HandlerRegistry
~~~~~~~~~~~~~~~

``HandlerRegistry`` maps a lower-cased type name to a factory
``(name, path, cfg, file_system) -> Handler``. ``default_registry()`` returns a
registry with the built-in types ``hostfs``, ``adfs``, ``ram``, ``nil``,
``console``, ``packet`` and ``native``. ``get_all_types()`` lists them and
``create(...)`` builds one (or returns ``None`` for an unknown type).


Packet decoder
~~~~~~~~~~~~~~

The packet bridge described above is the *client* direction: it turns a handler
call into a ``DosPacket``. ``PacketDecoder`` (in
:mod:`amitools.vamos.handler.decode`) is the *server* direction: it reads an
incoming ``DosPacket``, resolves the packet's target, calls the matching
handler method, and writes ``dp_Res1``/``dp_Res2``. It is what lets a handler
port answer m68k code that speaks DOS packets directly (``DoPkt``/``SendPkt``)
exactly like a real AmigaDOS handler.

The decoder is kept free of DOS-layer imports: the DOS layer injects small
resolver callbacks that translate the opaque handles carried in a packet
(lock BPTRs, file-handle ids) into handler objects and register the result of an
action back as a DOS handle:

- ``resolve_fh(fh_id)`` -> ``(handler, handler_file, ami_path)``
- ``resolve_lock(lock_id)`` -> ``(handler, handler_lock, ami_path)``
- ``volume_handler()`` -> the handler this decoder serves (its port's handler);
  it names the handler for ZERO-lock, volume-relative path packets
- ``register_lock(handler, handler_lock, ami_path)`` -> ``lock_id``
- ``register_file(handler, handler_file, ami_path)`` -> ``fh_id``
- ``release_lock(lock_id)`` / ``release_file(fh_id)`` (optional) release a DOS
  handle on ``FREE_LOCK`` / ``END``

``decode(pkt)`` returns ``dp_Res1``. A ``HandlerError`` becomes
``res1=DOSFALSE`` with ``res2=code``; an unknown action becomes
``ERROR_ACTION_NOT_KNOWN``; and ``PARENT`` of the volume root answers
``res1=0, res2=0``. A decoder is scoped to one handler: an fh/lock packet whose
handle belongs to a *different* handler is rejected with ``ERROR_INVALID_LOCK``,
so only the owning handler's port can resolve its handles, like a real handler
process.

Handler dispatcher
~~~~~~~~~~~~~~~~~~

``HandlerDispatcher`` (in :mod:`amitools.vamos.handler.dispatch`) bundles a
handler's own message port with the decoder that serves it. The DOS layer gives
every registered handler a dispatcher (``handler.dispatcher``): a message put on
the port is decoded onto that handler and the reply is posted back to the
packet's ``dp_Port``. The port is what ``GetDeviceProc`` reports as ``dvp_Port``
and what ``fh_Type``/``fl_Task`` name for a file or lock, so guest code can send
packets straight to the owning handler. The dispatchers are created when
``dos.library`` opens and freed when it closes.

``GetDeviceProc`` fills the rest of the ``DevProc`` from the DOS list:
``dvp_Lock`` is a lock on the device/volume/assign root and ``dvp_DevNode`` the
matching entry. A multi-directory assign sets ``DVPF_ASSIGN`` and returns each
directory on repeated calls (the passed ``DevProc`` is reused in place). With
the name ``"*"`` it walks the whole DOS device list instead, one device per
call, ending with ``ERROR_NO_MORE_ENTRIES``; a ``DevProc`` that owns a temporary
root lock (a plain device) sets ``DVPF_UNLOCK`` so ``FreeDeviceProc`` releases
it.


Built-in handlers
-----------------

``hostfs`` -- ``HostFileSysHandler``
    The default. Backs a volume with a host directory tree; every path is
    resolved relative to the volume root and mapped to the host file system
    case-insensitively.

``adfs`` -- ``AdfsHandler``
    An AmigaDOS file system (OFS/FFS) inside an image file, through the
    ``amitools.fs`` package. The volume path is the image: a raw floppy image
    (``.adf``), a hardfile (``.hdf``) or one RDB partition (``.rdb``, selected
    with ``?part=``). The image type is auto-detected from the contents and the
    file extension; ``?img=`` forces it (``adf``/``adf_hd``/``hdf``/``rdb``, or
    ``xdf`` for "raw image, detect"). It is the default handler for a volume
    whose source is a file rather than a directory.

``ram`` -- ``RamHandler``
    An in-memory AmigaDOS file system. It keeps a tree of files in shared
    ``bytearray`` buffers (all open handles see each other), so no host temp
    directory is needed. The nominal capacity is set with ``?size=<kb>``
    (default 1024 KiB).

``nil`` -- ``NilHandler``
    The ``NIL:`` sink: every read returns EOF and every write is discarded. It
    is a device, not a file system; ``locate_object`` only resolves the device
    root (for ``Lock("NIL:")``/``GetDeviceProc``).

``console`` -- ``ConsoleHandler``
    ``CONSOLE:`` (and its alias ``*``) on the host standard input/output. It
    owns the tty (termios) handling and the ESC/CSI and Latin-1 to UTF-8
    conversions; the DOS layer only sees a plain byte stream. Like ``NIL:`` it
    is a device and only exposes a lock on the device root.

``packet`` -- ``DosPktHandler``
    A bridge that sends handler calls to a real AmigaDOS handler port
    (``?handler=packet&port=<name|addr>``). It is created before the port
    manager exists and is attached to the live machine once ``exec.library``
    is up.

``native`` -- ``NativeHandler``
    A *client* of an original 68k AmigaDOS file system handler that runs as its
    own task inside the emulator. The handler binary is loaded as a seglist,
    started as a process and talked to over its real ``MsgPort`` with the exec
    message/signal functions (``PutMsg``/``WaitPort``/``GetMsg``), so an
    unmodified handler such as ``pfs3aio`` can mount a ``--disk`` partition or a
    raw ADF/HDF image. Select it with a path-less ``?handler=native`` volume::

        vamos --disk work.hdf -V "WORK:?handler=native,binary=/path/pfs3aio,device=DH0"

    Options (comma-separated after ``?``):

    ``binary``
        The handler seglist: a host path, an Amiga path (``LIBS:pfs3aio``), or
        omitted to mount the driver the RDB stores for the partition's DOS type.

    ``device`` / ``part``
        The ``--disk`` device to mount, named by its DOS device node
        (``device=DH0``), its RDB partition (``part=DH0`` or ``part=1``) or a
        raw image's whole-disk device name. With neither set the volume name is
        tried, then the first partition.

    ``globvec``
        The handler's ``dol_GlobVec``: ``-1`` for a C handler, ``-2`` for an
        assembler one. Overrides the value stored in the RDB driver.

    ``stack`` / ``priority``
        The handler process's stack size (default 4 KiB) and exec task priority.

    The volume is bound before ``exec.library`` exists, so the handler is
    created detached and attached to the live machine (and its started task)
    once the base libraries are open. When the mount name equals the partition's
    DOS device name the manager *adopts* the ``--disk`` node instead of creating
    a second one. A handler that fails to start aborts vamos with a setup error.


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

A volume whose source is a *file* is an image-backed ADFS volume: the handler
defaults to ``adfs`` and the file is not mapped to the host file system::

    vamos -V work:disk.adf myprog
    vamos -V work:disk.rdb?part=1 myprog

The auto ``ram:`` volume uses the ``ram`` handler and the auto ``root:`` volume
uses ``hostfs``. ``NIL:`` and ``CONSOLE:`` always exist as built-in devices,
so they need no volume definition. See :doc:`../user/config` for the volume
model and :doc:`../user/options` for the command-line and config options.
