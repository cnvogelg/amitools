"""Handler manager: registry and dispatcher for file system handlers.

The manager owns the mapping from a volume/device name to its handler and
performs Amiga path resolution (assigns, cwd, volume split) before handing a
volume-relative path to the right handler. It is the single entry point the
DOS layer uses for path based operations; operations on an existing lock or
file are done on the handler stored with that handle.
"""

from amitools.vamos.log import log_handler
from amitools.vamos.path import HostFileSystem

from .base import (
    ERROR_OBJECT_NOT_FOUND,
    ERROR_RENAME_ACROSS_DEVICES,
    HandlerError,
    MODE_NEWFILE,
)


class HandlerManager:
    def __init__(self, path_mgr, file_system=None):
        self.path_mgr = path_mgr
        self.file_system = file_system or HostFileSystem()
        self.handlers = {}

    # ----- registration -----

    def register(self, name, handler):
        """register a handler for a volume or device name"""
        lo_name = name.lower()
        self.handlers[lo_name] = handler
        log_handler.info("register handler '%s': %s", name, handler)
        return handler

    def unregister(self, name):
        handler = self.handlers.pop(name.lower(), None)
        if handler is not None:
            log_handler.info("unregister handler '%s'", name)
        return handler

    def get_handler(self, name):
        return self.handlers.get(str(name).lower())

    def get_all_names(self):
        return list(self.handlers.keys())

    # ----- path resolution -----

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

    def resolve(self, ami_path, env=None):
        """resolve an Amiga path to a list of (handler, rel_path) candidates

        Multi assigns yield one candidate per resolved volume path, in order.
        """
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

    def _dispatch(self, ami_path, env, func):
        """try each candidate until a handler call succeeds"""
        candidates = self.resolve(ami_path, env=env)
        last_error = None
        for handler, rel_path in candidates:
            try:
                return handler, func(handler, rel_path)
            except HandlerError as e:
                last_error = e
        if last_error is not None:
            raise last_error
        raise HandlerError(ERROR_OBJECT_NOT_FOUND)

    def _first(self, ami_path, env):
        """return the first candidate (for creating new objects)"""
        candidates = self.resolve(ami_path, env=env)
        if not candidates:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        return candidates[0]

    def _first_existing(self, ami_path, env):
        """return the first candidate whose object exists"""
        candidates = self.resolve(ami_path, env=env)
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

    def locate_object(self, ami_path, exclusive=False, env=None):
        return self._dispatch(ami_path, env, lambda h, p: h.locate_object(p, exclusive))

    def find_input(self, ami_path, env=None):
        return self._dispatch(ami_path, env, lambda h, p: h.find_input(p))

    def find_update(self, ami_path, env=None):
        return self._dispatch(ami_path, env, lambda h, p: h.find_update(p))

    def find_output(self, ami_path, mode=MODE_NEWFILE, env=None):
        return self._dispatch(ami_path, env, lambda h, p: h.find_output(p, mode))

    def delete_object(self, ami_path, env=None):
        return self._dispatch(ami_path, env, lambda h, p: h.delete_object(p))

    def set_protect(self, ami_path, mask, env=None):
        return self._dispatch(ami_path, env, lambda h, p: h.set_protect(p, mask))

    def set_comment(self, ami_path, comment, env=None):
        return self._dispatch(ami_path, env, lambda h, p: h.set_comment(p, comment))

    def set_date(self, ami_path, date, env=None):
        return self._dispatch(ami_path, env, lambda h, p: h.set_date(p, date))

    def create_dir(self, ami_path, env=None):
        return self._dispatch(ami_path, env, lambda h, p: h.create_dir(p))

    def rename_object(self, old_path, new_path, env=None):
        old_handler, old_rel = self._first_existing(old_path, env)
        new_handler, new_rel = self._first(new_path, env)
        if old_handler is not new_handler:
            raise HandlerError(ERROR_RENAME_ACROSS_DEVICES)
        return old_handler, old_handler.rename_object(old_rel, new_rel)

    def is_filesystem(self, name):
        handler = self.get_handler(name)
        if handler is None:
            return True
        return handler.is_filesystem
