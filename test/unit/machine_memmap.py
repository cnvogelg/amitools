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
