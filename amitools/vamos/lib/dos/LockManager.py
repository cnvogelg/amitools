from amitools.util import SlotArray
from amitools.vamos.handler import HandlerError
from amitools.vamos.log import log_lock
from amitools.vamos.error import VamosInternalError
from amitools.vamos.libstructs import DosListVolumeStruct, FileLockStruct
from .Lock import Lock
from .PathPart import expand_progdir_path


class LockKey:
    """manage a set of lock objects that belong to the same key

    key identifies the file object within its volume. We use the identity
    of the handler that owns the object plus the handler lock key, so two
    locks on the same object share a key (and thus a DOS fl_Key).
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

    def is_empty(self):
        return not self.locks_by_baddr


class LockManager:
    def __init__(
        self,
        path_mgr,
        dos_list,
        alloc,
        mem,
        handler_mgr=None,
        max_locks=1024,
    ):
        self.path_mgr = path_mgr
        self.dos_list = dos_list
        self.alloc = alloc
        self.mem = mem
        self.handler_mgr = handler_mgr
        # we manage keys per file object
        # each individual file object gets a unique slot = key
        self.keys = SlotArray(max_locks)
        # map each file object identity to a lock_key
        self.lock_key_map = {}

    def _lock_identity(self, lock):
        """identity of the object a lock points at

        Prefer the handler lock key so locks on the same object share a DOS
        key. Fall back to the Amiga path for locks without a handler.
        """
        if lock.handler is not None and lock.handler_lock is not None:
            return (id(lock.handler), lock.handler_lock.key)
        return (None, str(lock.ami_path).lower())

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

        # is a key already assigned to this object?
        identity = self._lock_identity(lock)
        lock_key = self.lock_key_map.get(identity)
        if not lock_key:
            # allocate new slot id
            lock_key = LockKey(identity)
            slot_id = self.keys.alloc(lock_key)
            log_lock.debug("allocate lock key slot %s for %s", slot_id, identity)
            if slot_id is None:
                log_lock.error("no more lock slots! max=%d", len(self.keys))
                return None
            lock_key.slot_id = slot_id
            self.lock_key_map[identity] = lock_key
        else:
            slot_id = lock_key.slot_id
            log_lock.debug("found lock key slot %s for %s", slot_id, identity)

        # allocate lock struct and use slot_id for key
        lock.alloc(self.alloc, vol_baddr, slot_id)
        # fl_Task is the packet port of the handler that owns the lock
        dispatcher = getattr(lock.handler, "dispatcher", None)
        if dispatcher is not None:
            lock.struct.fl_Task.aptr = dispatcher.port

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
        if lock_key.is_empty():
            del self.lock_key_map[lock_key.key]
            self.keys.free(slot_id)

        # release the handler-side lock object (ACTION_FREE_LOCK)
        if lock.handler is not None and lock.handler_lock is not None:
            lock.handler.free_lock(lock.handler_lock)

        # free lock itself
        lock.free(self.alloc)
        del lock

    def create_lock(self, cur_dir, ami_path, exclusive, home_dir=None):
        log_lock.debug(
            "create_lock: ami_path='%s' cur_dir=%s home_dir=%s",
            ami_path,
            cur_dir,
            home_dir,
        )
        if ami_path == "":
            if cur_dir is None:
                ami_path = "SYS:"
            else:
                ami_path = cur_dir.ami_path
        else:
            # Handle '*' prefix (PROGDIR: - program's home directory)
            expanded = expand_progdir_path(ami_path, home_dir)
            if expanded != ami_path:
                log_lock.debug("expanded '*' path to: %s", expanded)
                ami_path = expanded
            ami_path = self.path_mgr.ami_abs_path(cur_dir, ami_path)
        name = self.path_mgr.ami_name_of_path(cur_dir, ami_path)
        cwd = cur_dir.ami_path if cur_dir is not None else None
        try:
            handler, handler_lock = self.handler_mgr.locate_object(
                ami_path, exclusive=exclusive, cwd=cwd
            )
        except HandlerError as e:
            log_lock.info("lock '%s' invalid: '%s' (%s)", name, ami_path, e)
            return None
        lock = Lock(
            name,
            ami_path,
            exclusive,
            handler=handler,
            handler_lock=handler_lock,
        )
        return self._register_lock(lock)

    def register_handler_lock(
        self, handler, handler_lock, ami_path, name=None, exclusive=False
    ):
        """build and register a DOS lock from a handler lock + Amiga path

        Used by the handler-backed lock operations (``dup_lock``,
        ``create_parent_lock``, ``DupLockFromFH``, ``ParentOfFH``) that already
        hold a handler lock and only need a DOS ``Lock`` around it.
        """
        if name is None:
            name = self.path_mgr.ami_name_of_path(None, ami_path)
        lock = Lock(
            name,
            ami_path,
            exclusive,
            handler=handler,
            handler_lock=handler_lock,
        )
        return self._register_lock(lock)

    def dup_lock(self, lock):
        # handler-backed: ACTION_COPY_DIR replicates the object
        if lock.handler is not None and lock.handler_lock is not None:
            try:
                handler_lock = lock.handler.copy_dir(lock.handler_lock)
            except HandlerError as e:
                log_lock.info("dup_lock '%s' failed: %s", lock, e)
                return None
            return self.register_handler_lock(
                lock.handler,
                handler_lock,
                lock.ami_path,
                name=lock.name,
                exclusive=lock.exclusive,
            )
        # path-based fallback for handler-less locks (bare test managers)
        return self.create_lock(lock, "", False)

    def create_parent_lock(self, lock):
        # handler-backed: ACTION_PARENT resolves the parent on the handler
        if lock.handler is not None and lock.handler_lock is not None:
            try:
                handler_lock = lock.handler.parent(lock.handler_lock)
            except HandlerError as e:
                log_lock.info("parent of '%s' failed: %s", lock, e)
                return None
            ami_parent_path = self.path_mgr.ami_abs_parent_path(lock.ami_path)
            name = self.path_mgr.ami_name_of_path(None, ami_parent_path)
            return self.register_handler_lock(
                lock.handler, handler_lock, ami_parent_path, name=name
            )
        # path-based fallback for handler-less locks (bare test managers)
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
            raw_lock = FileLockStruct(self.mem, b_addr << 2)
            key = raw_lock.key.val
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
            vol_addr = lock.struct.volume.aptr
            volnode = DosListVolumeStruct(self.mem, vol_addr)
            name_addr = volnode.name.aptr
            name = self.mem.r_bstr(name_addr) + ":"
            return name

    def same_lock(self, lock1, lock2):
        """do two locks refer to the same file system object?"""
        if lock1 is None or lock2 is None:
            return lock1 is lock2
        return self._lock_identity(lock1) == self._lock_identity(lock2)
