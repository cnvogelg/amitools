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
    ERROR_OBJECT_NOT_FOUND,
    ERROR_RENAME_ACROSS_DEVICES,
    MODE_NEWFILE,
    HandlerError,
)
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

    def get_all_names(self):
        return list(self.handlers.keys())

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

    def resolve(self, ami_path, env=None, cwd=None):
        """resolve an Amiga path to a list of (handler, rel_path) candidates

        Multi assigns yield one candidate per resolved volume path, in order.
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

    def _first_existing(self, ami_path, env=None, cwd=None):
        """return the first candidate whose object exists"""
        candidates = self.resolve(ami_path, env=env, cwd=cwd)
        for handler, rel_path in candidates:
            try:
                handler.locate_object(rel_path)
                return handler, rel_path
            except HandlerError:
                continue
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
            try:
                handler.locate_object(rel_path)
            except HandlerError:
                continue
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

    def is_filesystem(self, name):
        handler = self.get_handler(name)
        if handler is None:
            return True
        return handler.is_filesystem


def build_handler_manager(path_mgr, file_system=None, registry=None):
    """create a HandlerManager and bind every volume of the path manager

    This is the top-level entry point that turns the configured volumes into
    registered handlers. ``file_system`` defaults to the volume manager's
    shared host file system so handlers and the path layer stay consistent.
    """
    vol_mgr = path_mgr.get_vol_mgr()
    if file_system is None:
        file_system = vol_mgr.file_system
    mgr = HandlerManager(path_mgr, file_system=file_system, registry=registry)
    for volume in vol_mgr.get_all_volumes():
        mgr.bind_volume(volume)
    return mgr
