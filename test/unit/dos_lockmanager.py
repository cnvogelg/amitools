from types import SimpleNamespace

from amitools.vamos.handler import HandlerError, HandlerLock
from amitools.vamos.lib.dos.Lock import Lock
from amitools.vamos.lib.dos.LockManager import LockManager
from amitools.vamos.path.amipath import AmiPath


class _Handler:
    """opaque handler stand-in; records the handler locks it frees"""

    def __init__(self):
        self.freed = []
        self.copied = []
        self.parented = []

    def free_lock(self, lock):
        self.freed.append(lock)

    def copy_dir(self, lock):
        self.copied.append(lock)
        new_lock = HandlerLock(key=lock.key)
        new_lock.handler = self
        return new_lock

    def parent(self, lock):
        self.parented.append(lock)
        if not lock.key:
            raise HandlerError(205)
        new_lock = HandlerLock(
            key=lock.key.rsplit("/", 1)[0] if "/" in lock.key else ""
        )
        new_lock.handler = self
        return new_lock


def _ami_abs_parent_path(path):
    ap = AmiPath(path)
    parent = ap.parent()
    return str(parent if parent is not None else ap)


def _ami_name_of_path(cwd, path):
    ap = AmiPath(path)
    name = ap.filename()
    return name if name is not None else ap.prefix() + ":"


def _make_mgr(mem_alloc, handler_mgr=None):
    mem, alloc = mem_alloc
    path_mgr = SimpleNamespace(
        ami_volume_of_path=lambda ami_path: "SYS",
        ami_abs_parent_path=_ami_abs_parent_path,
        ami_name_of_path=_ami_name_of_path,
        ami_abs_path=lambda cwd, path: str(path),
    )
    dos_list = SimpleNamespace(
        get_entry_by_name=lambda name: SimpleNamespace(mem=SimpleNamespace(addr=0x1000))
    )
    mgr = LockManager(path_mgr, dos_list, alloc, mem, handler_mgr=handler_mgr)
    return mgr, mem, alloc


def _make_lock(handler, handler_key, ami_path="SYS:dir"):
    handler_lock = HandlerLock(key=handler_key)
    handler_lock.handler = handler
    return Lock("dir", ami_path, handler=handler, handler_lock=handler_lock)


def dos_lockmanager_same_object_shares_key_test(mem_alloc):
    mgr, mem, alloc = _make_mgr(mem_alloc)
    handler = _Handler()

    first = mgr._register_lock(_make_lock(handler, "dir"))
    second = mgr._register_lock(_make_lock(handler, "dir"))

    # same object -> same DOS fl_Key but distinct lock addresses
    assert first.key == second.key
    assert first.b_addr != second.b_addr
    assert first.struct.key.val == second.struct.key.val
    assert mgr.get_by_b_addr(first.b_addr) is first
    assert mgr.get_by_b_addr(second.b_addr) is second

    # releasing one lock keeps the shared slot alive and frees its handler lock
    first_handler_lock = first.handler_lock
    mgr.release_lock(first)
    assert mgr.get_by_b_addr(second.b_addr) is second
    assert len(mgr.lock_key_map) == 1
    assert handler.freed == [first_handler_lock]

    # releasing the last lock frees the slot and drops the mapping
    mgr.release_lock(second)
    assert not mgr.lock_key_map
    assert mgr.keys.num_free() == 1024
    assert handler.freed == [first_handler_lock, second.handler_lock]
    assert alloc.is_all_free()


def dos_lockmanager_distinct_objects_get_distinct_keys_test(mem_alloc):
    mgr, mem, alloc = _make_mgr(mem_alloc)
    handler = _Handler()

    first = mgr._register_lock(_make_lock(handler, "a"))
    second = mgr._register_lock(_make_lock(handler, "b"))
    other_handler = mgr._register_lock(_make_lock(_Handler(), "a"))

    assert first.key != second.key
    assert first.key != other_handler.key
    assert mgr.keys.num_free() == 1024 - 3

    mgr.release_lock(first)
    mgr.release_lock(second)
    mgr.release_lock(other_handler)
    assert not mgr.lock_key_map
    assert mgr.keys.num_free() == 1024
    assert alloc.is_all_free()


def dos_lockmanager_without_handler_uses_ami_path_test(mem_alloc):
    mgr, mem, alloc = _make_mgr(mem_alloc)

    first = mgr._register_lock(Lock("a", "SYS:a"))
    same = mgr._register_lock(Lock("a", "SYS:a"))
    other = mgr._register_lock(Lock("b", "SYS:b"))

    assert first.key == same.key
    assert first.key != other.key

    mgr.release_lock(first)
    mgr.release_lock(same)
    mgr.release_lock(other)
    assert not mgr.lock_key_map
    assert mgr.keys.num_free() == 1024
    assert alloc.is_all_free()


# ----- handler-backed lock operations (step 12d) -----


def _handler_lock(handler, key):
    lock = HandlerLock(key=key)
    lock.handler = handler
    return lock


def dos_lockmanager_register_handler_lock_test(mem_alloc):
    mgr, mem, alloc = _make_mgr(mem_alloc)
    handler = _Handler()
    handler_lock = _handler_lock(handler, "dir")

    lock = mgr.register_handler_lock(handler, handler_lock, "SYS:dir", name="dir")

    assert lock.handler is handler
    assert lock.handler_lock is handler_lock
    assert lock.name == "dir"
    assert lock.ami_path == "SYS:dir"
    assert mgr.get_by_b_addr(lock.b_addr) is lock

    mgr.release_lock(lock)
    assert handler.freed == [handler_lock]
    assert alloc.is_all_free()


def dos_lockmanager_register_handler_lock_default_name_test(mem_alloc):
    mgr, mem, alloc = _make_mgr(mem_alloc)
    handler = _Handler()
    lock = mgr.register_handler_lock(handler, _handler_lock(handler, "dir"), "SYS:dir")
    assert lock.name == "dir"
    mgr.release_lock(lock)
    assert alloc.is_all_free()


def dos_lockmanager_dup_lock_handler_test(mem_alloc):
    mgr, mem, alloc = _make_mgr(mem_alloc)
    handler = _Handler()
    lock = mgr._register_lock(_make_lock(handler, "dir"))

    dup = mgr.dup_lock(lock)

    assert dup is not lock
    assert dup.handler is handler
    assert dup.key == lock.key  # same object -> same DOS fl_Key
    assert dup.name == "dir"
    assert handler.copied == [lock.handler_lock]

    mgr.release_lock(dup)
    mgr.release_lock(lock)
    assert alloc.is_all_free()


def dos_lockmanager_parent_lock_handler_test(mem_alloc):
    mgr, mem, alloc = _make_mgr(mem_alloc)
    handler = _Handler()
    lock = mgr._register_lock(_make_lock(handler, "dir/sub", ami_path="SYS:dir/sub"))

    parent = mgr.create_parent_lock(lock)

    assert parent.handler is handler
    assert parent.ami_path == "SYS:dir"
    assert parent.name == "dir"
    assert handler.parented == [lock.handler_lock]

    # the volume root has no parent
    root = mgr._register_lock(_make_lock(handler, "", ami_path="SYS:"))
    assert mgr.create_parent_lock(root) is None

    mgr.release_lock(parent)
    mgr.release_lock(root)
    mgr.release_lock(lock)
    assert alloc.is_all_free()


# ----- path-based fallback for handler-less locks -----


def dos_lockmanager_dup_lock_handlerless_test(mem_alloc):
    handler = _Handler()
    located = []

    def locate_object(ami_path, exclusive=False, cwd=None):
        located.append((ami_path, exclusive, cwd))
        return handler, _handler_lock(handler, ami_path.lower())

    mgr, mem, alloc = _make_mgr(
        mem_alloc, handler_mgr=SimpleNamespace(locate_object=locate_object)
    )
    lock = mgr._register_lock(Lock("a", "SYS:a"))

    dup = mgr.dup_lock(lock)

    assert located == [("SYS:a", False, "SYS:a")]
    assert dup is not lock
    assert dup.ami_path == "SYS:a"

    mgr.release_lock(dup)
    mgr.release_lock(lock)
    assert alloc.is_all_free()


def dos_lockmanager_parent_lock_handlerless_test(mem_alloc):
    handler = _Handler()
    located = []

    def locate_object(ami_path, exclusive=False, cwd=None):
        located.append(ami_path)
        return handler, _handler_lock(handler, ami_path.lower())

    mgr, mem, alloc = _make_mgr(
        mem_alloc, handler_mgr=SimpleNamespace(locate_object=locate_object)
    )
    lock = mgr._register_lock(Lock("sub", "SYS:dir/sub"))

    parent = mgr.create_parent_lock(lock)

    assert located == ["SYS:dir"]
    assert parent.ami_path == "SYS:dir"

    root = mgr._register_lock(Lock("SYS:", "SYS:"))
    assert mgr.create_parent_lock(root) is None

    mgr.release_lock(parent)
    mgr.release_lock(root)
    mgr.release_lock(lock)
    assert alloc.is_all_free()
