from amitools.vamos.machine import MemoryMap, Machine, HWAccess
from amitools.vamos.cfgcore import ConfigDict


def machine_memmap_parse_config_test():
    machine = Machine()
    mm = MemoryMap(machine)
    old_base = mm.get_old_dos_guard_base()
    cfg = ConfigDict({"hw_access": "ignore", "old_dos_guard": True})
    assert mm.parse_config(cfg)
    assert mm.get_old_dos_guard_base() != old_base
    assert mm.get_hw_access().mode == HWAccess.MODE_IGNORE
    assert mm.get_alloc()


def machine_memmap_cleanup_stops_free_list_mirror_test():
    machine = Machine()
    mm = MemoryMap(machine)
    cfg = ConfigDict({"hw_access": "ignore", "old_dos_guard": False})
    assert mm.parse_config(cfg)
    alloc = mm.get_alloc()
    mem_obj = alloc.alloc_memory(64)
    # what exec.library's AllocatorMemHeader installs
    calls = []
    alloc.change_callback = lambda: calls.append(1)
    mm.cleanup()
    machine.cleanup()
    # a late free, as by a Pool finalizer, must not reach guest memory
    alloc.free_memory(mem_obj)
    assert calls == []
