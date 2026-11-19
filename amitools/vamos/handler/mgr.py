"""Handler manager: registry and dispatcher for file system handlers.

The manager owns the mapping from a volume/device name to its handler and
performs Amiga path resolution (assigns, cwd, volume split) before handing a
volume-relative path to the right handler. It is the single entry point the
DOS layer uses for path based operations; operations on an existing lock or
file are done on the handler stored with that handle.
"""

from amitools.vamos.log import log_handler
from amitools.vamos.path import HostFileSystem
from amitools.vamos.path.amipath import AmiPath

from .base import (
    ERROR_ACTION_NOT_KNOWN,
    ERROR_NO_MORE_ENTRIES,
    ERROR_OBJECT_EXISTS,
    ERROR_OBJECT_NOT_FOUND,
    ERROR_RENAME_ACROSS_DEVICES,
    MODE_NEWFILE,
    HandlerError,
)
from .dispatch import HandlerDispatcher
from .registry import default_registry


class HandlerManager:
    def __init__(self, path_mgr, file_system=None, registry=None):
        self.path_mgr = path_mgr
        self.file_system = file_system or HostFileSystem()
        self.registry = registry if registry is not None else default_registry()
        self.handlers = {}

    # ----- registration -----

    def register(self, name, handler):
        """register a handler for a volume or device name"""
        lo_name = name.lower()
        self.handlers[lo_name] = handler
        log_handler.info("register handler '%s': %s", name, handler)
        return handler

    def bind_volume(self, volume):
        """create and register the handler selected by a volume's config

        The handler type is read from the volume's ``handler`` config option
        (default ``hostfs``) and looked up in the registry. An unknown type
        raises :class:`HandlerError` with ``ERROR_ACTION_NOT_KNOWN``.
        """
        cfg = volume.get_cfg() or {}
        type_name = cfg.get("handler", "hostfs")
        handler = self.registry.create(
            type_name,
            volume.get_name(),
            volume.get_path(),
            cfg,
            self.file_system,
        )
        if handler is None:
            raise HandlerError(
                ERROR_ACTION_NOT_KNOWN,
                "unknown handler type '%s' for volume '%s'"
                % (type_name, volume.get_name()),
            )
        return self.register(volume.get_name(), handler)

    def unregister(self, name):
        handler = self.handlers.pop(name.lower(), None)
        if handler is not None:
            log_handler.info("unregister handler '%s'", name)
        return handler

    def shutdown(self):
        """release all registered handlers"""
        for name in list(self.handlers):
            handler = self.handlers[name]
            handler_shutdown = getattr(handler, "shutdown", None)
            if handler_shutdown is not None:
                handler_shutdown()
        self.handlers.clear()
        log_handler.info("handler manager shut down")

    def get_handler(self, name):
        return self.handlers.get(str(name).lower())

    # ----- packet ports (dispatchers) -----

    def attach_dispatchers(self, port_mgr, mem, make_decoder):
        """give every registered handler its own packet port

        ``make_decoder(handler)`` builds the :class:`PacketDecoder` that serves
        that handler; it is wrapped in a :class:`HandlerDispatcher` and injected
        as ``handler.dispatcher``. Idempotent: handlers that already have a
        dispatcher are left alone.
        """
        for name, handler in self.handlers.items():
            # a native handler is served by its own 68k task: its dispatcher
            # shim already reports the real packet port
            if getattr(handler, "is_native", False):
                continue
            if getattr(handler, "dispatcher", None) is not None:
                continue
            decoder = make_decoder(handler)
            handler.dispatcher = HandlerDispatcher(
                port_mgr, mem, "%s handler" % name, decoder
            )
            log_handler.info(
                "attach dispatcher '%s': port=%06x", name, handler.dispatcher.port
            )

    def detach_dispatchers(self):
        """free every handler's packet port"""
        for handler in self.handlers.values():
            dispatcher = getattr(handler, "dispatcher", None)
            if dispatcher is not None:
                dispatcher.free()
                handler.dispatcher = None

    def get_dispatcher(self, name):
        """the packet-port dispatcher of the handler registered as ``name``"""
        handler = self.get_handler(name)
        if handler is None:
            return None
        return getattr(handler, "dispatcher", None)

    def _volume_handler(self, volume_name):
        """resolve a handler by volume/device name (strip a trailing colon)

        Raises :class:`HandlerError` with ``ERROR_OBJECT_NOT_FOUND`` for an
        unknown volume.
        """
        name = str(volume_name)
        if name.endswith(":"):
            name = name[:-1]
        handler = self.get_handler(name)
        if handler is None:
            raise HandlerError(
                ERROR_OBJECT_NOT_FOUND, "unknown volume '%s'" % volume_name
            )
        return handler

    def disk_info(self, volume_name):
        """lock-less volume query (ACTION_DISK_INFO)

        Resolve the handler by volume/device name and ask it for its disk
        info. Raises :class:`HandlerError` with ``ERROR_OBJECT_NOT_FOUND``
        for an unknown volume.
        """
        return self._volume_handler(volume_name).disk_info(None)

    def rename_disk(self, volume_name, new_name):
        """relabel a volume (ACTION_RENAME_DISK)"""
        return self._volume_handler(volume_name).rename_disk(new_name)

    def format(self, volume_name, new_vol_name, dos_type):
        """format a volume (ACTION_FORMAT)

        ``volume_name`` selects the handler (e.g. ``DF0:``); ``new_vol_name``
        is the name of the new volume.
        """
        return self._volume_handler(volume_name).format(new_vol_name, dos_type)

    def more_cache(self, volume_name, count):
        """add cache buffers to a volume (ACTION_MORE_CACHE)"""
        return self._volume_handler(volume_name).more_cache(count)

    def get_handler_by_port(self, port):
        """the handler that owns a packet port (or ``None``)

        The reverse of :meth:`get_dispatcher`: used by ``ReadLink`` to resolve
        a handler from a bare ``port`` argument.
        """
        for handler in self.handlers.values():
            dispatcher = getattr(handler, "dispatcher", None)
            if dispatcher is not None and dispatcher.port == port:
                return handler
        return None

    def attach_packet_transport(self, alloc, port_mgr, mem, find_port=None, pump=None):
        """attach the live machine to every detached packet handler

        A ``?handler=packet`` volume is bound before ``exec.library`` exists, so
        its :class:`~amitools.vamos.handler.dospkt.DosPktHandler` starts out
        detached. Once the port manager is available the DOS layer calls this to
        hand it the allocator, the ``PortManager`` and a port-name resolver.
        Handlers that need no transport (or are already attached) are ignored.
        """
        for handler in self.handlers.values():
            attach = getattr(handler, "attach_transport", None)
            if attach is not None:
                attach(alloc, port_mgr, mem, find_port=find_port, pump=pump)

    def get_all_names(self):
        return list(self.handlers.keys())

    def get_all_handlers(self):
        """every registered handler, in registration order"""
        return list(self.handlers.values())

    # ----- path resolution -----

    def _env(self, env, cwd):
        if env is not None or cwd is None:
            return env
        return self.path_mgr.create_env(cwd=AmiPath(cwd))

    def _split(self, vol_path):
        pos = vol_path.find(":")
        if pos <= 0:
            return None
        vol_name = vol_path[:pos]
        rel_path = vol_path[pos + 1 :]
        handler = self.get_handler(vol_name)
        if handler is None:
            return None
        return handler, rel_path

    def _device_candidate(self, ami_path):
        """direct handler lookup for a bare device prefix

        Device names like ``NIL:`` or ``CONSOLE:`` are handlers but neither a
        volume nor an assign, so the path manager does not resolve them. Fall
        back to a direct lookup by the prefix before the first colon.
        """
        path_str = str(ami_path)
        pos = path_str.find(":")
        if pos <= 0:
            return None
        handler = self.get_handler(path_str[:pos])
        if handler is None:
            return None
        return handler, path_str[pos + 1 :]

    def resolve(self, ami_path, env=None, cwd=None):
        """resolve an Amiga path to a list of (handler, rel_path) candidates

        Multi assigns yield one candidate per resolved volume path, in order.
        A bare device name that the path manager cannot resolve is looked up
        directly in the handler registry.
        """
        env = self._env(env, cwd)
        vol_paths = self.path_mgr.volpaths(ami_path, env=env)
        candidates = []
        seen = set()
        for vol_path in vol_paths:
            split = self._split(str(vol_path))
            if split is None:
                continue
            handler, rel_path = split
            key = (id(handler), rel_path.lower())
            if key in seen:
                continue
            seen.add(key)
            candidates.append((handler, rel_path))
        if not candidates:
            device = self._device_candidate(ami_path)
            if device is not None:
                candidates.append(device)
        return candidates

    def _dispatch(self, ami_path, func, env=None, cwd=None):
        """try each candidate until a handler call succeeds"""
        candidates = self.resolve(ami_path, env=env, cwd=cwd)
        last_error = None
        for handler, rel_path in candidates:
            try:
                return handler, func(handler, rel_path)
            except HandlerError as e:
                last_error = e
        if last_error is not None:
            raise last_error
        raise HandlerError(ERROR_OBJECT_NOT_FOUND)

    def _first(self, ami_path, env=None, cwd=None):
        """return the first candidate (for creating new objects)"""
        candidates = self.resolve(ami_path, env=env, cwd=cwd)
        if not candidates:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        return candidates[0]

    @staticmethod
    def _exists(handler, rel_path):
        """probe existence, releasing the probe lock again"""
        try:
            lock = handler.locate_object(rel_path)
        except HandlerError:
            return False
        handler.free_lock(lock)
        return True

    def _first_existing(self, ami_path, env=None, cwd=None):
        """return the first candidate whose object exists"""
        candidates = self.resolve(ami_path, env=env, cwd=cwd)
        for handler, rel_path in candidates:
            if self._exists(handler, rel_path):
                return handler, rel_path
        if candidates:
            return candidates[0]
        raise HandlerError(ERROR_OBJECT_NOT_FOUND)

    # ----- path based dispatch -----

    def locate_object(self, ami_path, exclusive=False, env=None, cwd=None):
        return self._dispatch(
            ami_path, lambda h, p: h.locate_object(p, exclusive), env=env, cwd=cwd
        )

    def find_input(self, ami_path, env=None, cwd=None):
        return self._dispatch(ami_path, lambda h, p: h.find_input(p), env=env, cwd=cwd)

    def find_update(self, ami_path, env=None, cwd=None):
        return self._dispatch(ami_path, lambda h, p: h.find_update(p), env=env, cwd=cwd)

    def find_output(self, ami_path, mode=MODE_NEWFILE, env=None, cwd=None):
        # Match the previous DOS "searchMulti" behavior: prefer an existing
        # object in any candidate and only create a new object in the first
        # candidate. (AmigaDOS itself writes to the first assign dir.)
        candidates = self.resolve(ami_path, env=env, cwd=cwd)
        if not candidates:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        for handler, rel_path in candidates:
            if self._exists(handler, rel_path):
                return handler, handler.find_output(rel_path, mode)
        handler, rel_path = candidates[0]
        return handler, handler.find_output(rel_path, mode)

    def delete_object(self, ami_path, env=None, cwd=None):
        return self._dispatch(
            ami_path, lambda h, p: h.delete_object(p), env=env, cwd=cwd
        )

    def set_protect(self, ami_path, mask, env=None, cwd=None):
        return self._dispatch(
            ami_path, lambda h, p: h.set_protect(p, mask), env=env, cwd=cwd
        )

    def set_comment(self, ami_path, comment, env=None, cwd=None):
        return self._dispatch(
            ami_path, lambda h, p: h.set_comment(p, comment), env=env, cwd=cwd
        )

    def set_date(self, ami_path, date, env=None, cwd=None):
        return self._dispatch(
            ami_path, lambda h, p: h.set_date(p, date), env=env, cwd=cwd
        )

    def create_dir(self, ami_path, env=None, cwd=None):
        return self._dispatch(ami_path, lambda h, p: h.create_dir(p), env=env, cwd=cwd)

    def rename_object(self, old_path, new_path, env=None, cwd=None):
        old_handler, old_rel = self._first_existing(old_path, env=env, cwd=cwd)
        new_handler, new_rel = self._first(new_path, env=env, cwd=cwd)
        if old_handler is not new_handler:
            raise HandlerError(ERROR_RENAME_ACROSS_DEVICES)
        return old_handler, old_handler.rename_object(old_rel, new_rel)

    def _abs_path(self, ami_path, env=None, cwd=None):
        env = self._env(env, cwd)
        return str(self.path_mgr.abspath(ami_path, env=env))

    def make_link(self, ami_path, dest, soft, env=None, cwd=None):
        """create a link (ACTION_MAKE_LINK)

        ``dest`` is the target path string (soft link) or a handler lock on
        the target (hard link). The link's parent directory is resolved to a
        handler lock which is released again after the handler call.
        """
        abs_path = self._abs_path(ami_path, env=env, cwd=cwd)
        parent_path = self.path_mgr.ami_abs_parent_path(abs_path)
        name = self.path_mgr.ami_name_of_path(None, abs_path)
        handler, lock = self.locate_object(parent_path, env=env, cwd=cwd)
        try:
            if not soft and getattr(dest, "handler", None) is not handler:
                raise HandlerError(ERROR_RENAME_ACROSS_DEVICES)
            handler.make_link(lock, name, dest, soft)
        finally:
            handler.free_lock(lock)

    def read_link(self, dir_ami_path, path, size, env=None, cwd=None):
        """resolve a soft link relative to a directory (ACTION_READ_LINK)"""
        handler, lock = self.locate_object(dir_ami_path, env=env, cwd=cwd)
        try:
            return handler.read_link(lock, path, size)
        finally:
            handler.free_lock(lock)

    def set_owner(self, ami_path, owner, env=None, cwd=None):
        """set the owner of an object (ACTION_SET_OWNER)"""
        return self._dispatch(
            ami_path,
            lambda h, p: h.set_owner(None, p, owner),
            env=env,
            cwd=cwd,
        )

    def add_notify(self, ami_path, notify, env=None, cwd=None):
        """start monitoring an object (ACTION_ADD_NOTIFY)"""
        return self._dispatch(
            ami_path, lambda h, p: h.add_notify(notify), env=env, cwd=cwd
        )

    def remove_notify(self, ami_path, notify, env=None, cwd=None):
        """stop monitoring an object (ACTION_REMOVE_NOTIFY)"""
        return self._dispatch(
            ami_path, lambda h, p: h.remove_notify(notify), env=env, cwd=cwd
        )

    def is_filesystem(self, name):
        handler = self.get_handler(name)
        if handler is None:
            return True
        # the local flag describes the handler; a transport handler's
        # ``is_filesystem()`` is the remote packet query and is not available
        # until its transport is attached (and would be a needless round trip)
        is_fs = getattr(handler, "is_fs", None)
        if is_fs is not None:
            return is_fs
        return handler.is_filesystem()

    # ----- directory listing -----

    def list_dir(self, ami_path, env=None, cwd=None):
        """return the entry names of a directory via its handler

        Returns None if the object does not exist or is not a directory.
        """
        candidates = self.resolve(ami_path, env=env, cwd=cwd)
        for handler, rel_path in candidates:
            try:
                lock = handler.locate_object(rel_path)
            except HandlerError:
                continue
            try:
                if not handler.examine_object(lock).is_dir:
                    return None
                names = []
                key = 0
                while True:
                    try:
                        entry = handler.examine_next(lock, key)
                    except HandlerError as e:
                        if e.code == ERROR_NO_MORE_ENTRIES:
                            break
                        raise
                    names.append(entry.name)
                    key = entry.key
                return names
            except HandlerError:
                continue
            finally:
                handler.free_lock(lock)
        return None

    def path_exists(self, ami_path, env=None, cwd=None):
        """return True if the path exists on any responsible handler"""
        for handler, rel_path in self.resolve(ami_path, env=env, cwd=cwd):
            if self._exists(handler, rel_path):
                return True
        return False

    # ----- deferred assign dirs -----

    def _create_deferred_assign_dirs(self):
        """create ``?create`` assign dirs that live on a non-host volume

        A non-host volume (``ram:``, ...) has no host directory, so
        ``Assign.setup()`` cannot create the assign dirs while the path
        manager is set up. Once the handlers are bound we create them in the
        handler's file system instead.
        """
        path_mgr = self.path_mgr
        assign_mgr = path_mgr.get_assign_mgr()
        vol_mgr = path_mgr.get_vol_mgr()
        for assign in assign_mgr.assigns:
            if "create" not in assign.get_cfg():
                continue
            for a in assign.get_assigns():
                volpaths = assign_mgr.resolve_assigns(a, as_list=True)
                for volpath in volpaths:
                    split = assign_mgr._split_volume_remainder(volpath)
                    if split is None:
                        continue
                    vol_name, rel_dir = split
                    volume = vol_mgr.get_volume(vol_name)
                    if volume is None:
                        continue
                    # a host volume creates its dirs during path setup; only
                    # handler-backed volumes (no host path) and image-backed
                    # volumes are created here
                    if volume.get_path() is not None and not volume.is_image:
                        continue
                    if not rel_dir:
                        continue
                    handler = self.get_handler(volume.get_name())
                    if handler is None:
                        continue
                    self._create_dir_path(handler, rel_dir)

    @staticmethod
    def _create_dir_path(handler, rel_dir):
        """create ``rel_dir`` (and its parents) via ``handler.create_dir``"""
        parts = [p for p in str(rel_dir).split("/") if p]
        for i in range(1, len(parts) + 1):
            try:
                handler.create_dir("/".join(parts[:i]))
            except HandlerError as e:
                if e.code != ERROR_OBJECT_EXISTS:
                    log_handler.warning("can't create assign dir '%s': %s", rel_dir, e)
                    return


def build_handler_manager(path_mgr, file_system=None, registry=None):
    """create a HandlerManager and bind every volume of the path manager

    This is the top-level entry point that turns the configured volumes into
    registered handlers. ``file_system`` defaults to the volume manager's
    shared host file system so handlers and the path layer stay consistent.

    The ``NIL:`` and ``CONSOLE:`` devices always exist in AmigaDOS, so they
    are registered as built-in device handlers unless a volume already
    provides a handler under that name.
    """
    vol_mgr = path_mgr.get_vol_mgr()
    if file_system is None:
        file_system = vol_mgr.file_system
    mgr = HandlerManager(path_mgr, file_system=file_system, registry=registry)
    for volume in vol_mgr.get_all_volumes():
        mgr.bind_volume(volume)
    # a non-host volume has no host path, so its assign dirs are created here
    mgr._create_deferred_assign_dirs()
    # built-in AmigaDOS devices
    for dev_name in ("nil", "console"):
        if mgr.get_handler(dev_name) is None:
            handler = mgr.registry.create(dev_name, dev_name, None, {}, file_system)
            if handler is not None:
                mgr.register(dev_name, handler)
    # let the path layer reach the handlers for path-less volumes
    path_mgr.set_handler_mgr(mgr)
    return mgr
