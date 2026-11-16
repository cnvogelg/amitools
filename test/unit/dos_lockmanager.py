from types import SimpleNamespace

from amitools.vamos.handler import HandlerLock
from amitools.vamos.lib.dos.Lock import Lock
from amitools.vamos.lib.dos.LockManager import LockManager


class _Handler:
    """opaque handler stand-in; records the handler locks it frees"""

    def __init__(self):
        self.freed = []

    def free_lock(self, lock):
        self.freed.append(lock)


def _make_mgr(mem_alloc):
    mem, alloc = mem_alloc
    path_mgr = SimpleNamespace(ami_volume_of_path=lambda ami_path: "SYS")
    dos_list = SimpleNamespace(
        get_entry_by_name=lambda name: SimpleNamespace(mem=SimpleNamespace(addr=0x1000))
    )
    mgr = LockManager(path_mgr, dos_list, alloc, mem, handler_mgr=None)
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
