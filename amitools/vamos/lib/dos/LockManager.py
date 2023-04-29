import os.path
import logging

from amitools.util import SlotArray
from amitools.vamos.log import log_lock
from amitools.vamos.error import VamosInternalError
from amitools.vamos.astructs import AccessStruct
from amitools.vamos.libstructs import DosListVolumeStruct, FileLockStruct
from .Error import *
from .Lock import Lock


class LockKey:
    """manage a set of lock objects that belong to the same key

    key is typically a unique identifier of the file object in the volume.
    we use the absolute system path here.
    """

    def __init__(self, key):
        self.key = key
        self.slot_id = None
        self.locks_by_baddr = {}

    def __repr__(self):
        return "LockKey(key={}, slot_id={}, locks={})".format(
            self.key, self.slot_id, self.locks_by_baddr
        )

    def add_lock(self, lock):
        self.locks_by_baddr[lock.b_addr] = lock

    def del_lock(self, lock):
        del self.locks_by_baddr[lock.b_addr]

    def find_lock_by_baddr(self, b_addr):
        return self.locks_by_baddr.get(b_addr)

    def no_locks(self):
        return bool(self.locks_by_baddr)


class LockManager:
    def __init__(self, path_mgr, dos_list, alloc, mem, max_locks=1024):
        self.path_mgr = path_mgr
        self.dos_list = dos_list
        self.alloc = alloc
        self.mem = mem
        # we manage keys per sys_path
        # each individual sys_path gets a unique slot = key
        self.keys = SlotArray(max_locks)
        # map each sys_path name to a lock_key
        self.sys_path_to_key_map = {}

    def _register_lock(self, lock):
        # look up volume
        volume_name = self.path_mgr.ami_volume_of_path(lock.ami_path)
        log_lock.debug("fl_Volume: looking up volume '%s' of %s", volume_name, lock)
        volume = self.dos_list.get_entry_by_name(volume_name)
        if volume is None:
            vol_baddr = 0
            log_lock.warning("lock volume? volume=%s lock=%s", volume, lock)
        else:
            vol_baddr = volume.mem.addr

        # is key already assigned to sys_path?
        lock_key = self.sys_path_to_key_map.get(lock.sys_path)
        if not lock_key:
            # allocate new slot id
            lock_key = LockKey(lock.sys_path)
            slot_id = self.keys.alloc(lock_key)
            log_lock.debug(
                "allocate log key slot %s for sys_path '%s'", slot_id, lock.sys_path
            )
            if slot_id is None:
                log_lock.error("no more lock slots! max=%d", len(self.keys))
                return None
            lock_key.slot_id = slot_id
        else:
            slot_id = lock_key.slot_id
            log_lock.debug(
                "found log key slot %s for sys_path '%s'", slot_id, lock.sys_path
            )

        # allocate lock struct and use slot_id for key
        lock.alloc(self.alloc, vol_baddr, slot_id)

        # register lock in key (with baddr allocated above)
        lock_key.add_lock(lock)

        log_lock.info("registered: %s" % lock)
        return lock

    def _unregister_lock(self, lock):
        log_lock.info("unregistered: %s" % lock)
        # fetch key and lock_key
        slot_id = lock.key
        lock_key = self.keys[slot_id]
        # remove lock in key
        lock_key.del_lock(lock)
        # last lock in key?
        if lock_key.no_locks():
            del self.sys_path_to_key_map[lock.sys_path]
            self.locks.free(slot_id)

        # free lock itself
        lock.free(self.alloc)
        del lock

    def create_lock(self, cur_dir, ami_path, exclusive):
        if ami_path == "":
            if cur_dir is None:
                ami_path = "SYS:"
            else:
                ami_path = cur_dir.ami_path
        else:
            ami_path = self.path_mgr.ami_abs_path(cur_dir, ami_path)
        sys_path = self.path_mgr.ami_to_sys_path(cur_dir, ami_path, searchMulti=True)
        name = self.path_mgr.ami_name_of_path(cur_dir, ami_path)
        if sys_path is None:
            log_lock.info("lock '%s' invalid: no sys path found: '%s'", name, ami_path)
            return None
        exists = os.path.exists(sys_path)
        if not exists:
            log_lock.info(
                "lock '%s' invalid: sys path does not exist: '%s' -> '%s'",
                name,
                ami_path,
                sys_path,
            )
            return None
        lock = Lock(name, ami_path, sys_path, exclusive)
        return self._register_lock(lock)

    def dup_lock(self, lock):
        return self.create_lock(lock, "", False)

    def create_parent_lock(self, lock):
        # top level
        if lock.ami_path[-1] == ":":
            return None
        ami_path = lock.ami_path
        ami_parent_path = self.path_mgr.ami_abs_parent_path(ami_path)
        if ami_parent_path != ami_path:
            return self.create_lock(None, ami_parent_path, False)
        else:
            return None

    def get_by_b_addr(self, b_addr, none_if_missing=False):
        if b_addr == 0:
            return None
        else:
            raw_lock = AccessStruct(self.mem, FileLockStruct, b_addr << 2)
            key = raw_lock.r_s("fl_Key")
            lock_key = self.keys[key]
            log_lock.debug(
                "lookup key in baddr=%08x: %s -> lock_key=%r", b_addr, key, lock_key
            )
            lock = lock_key.find_lock_by_baddr(b_addr)
            if lock:
                return lock
            else:
                raise VamosInternalError("lock not found by b_addr?!")

    def release_lock(self, lock):
        if lock and lock.b_addr != 0:
            self._unregister_lock(lock)

    def volume_name_of_lock(self, lock):
        if lock is None:
            return "SYS:"
        else:
            vol_addr = lock.mem.access.r_s("fl_Volume")
            volnode = AccessStruct(self.mem, DosListVolumeStruct, vol_addr)
            name_addr = volnode.r_s("dol_Name")
            name = self.mem.access.r_bstr(name_addr) + ":"
            return name
