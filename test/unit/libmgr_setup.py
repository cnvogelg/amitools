from amitools.vamos.libmgr import SetupLibManager
from amitools.vamos.machine import Machine, MemoryMap
from amitools.vamos.path import PathManager
from amitools.vamos.cfgcore import ConfigDict


def libmgr_setup_default_test():
  machine = Machine()
  mem_map = MemoryMap(machine)
  mem_map.setup_ram_allocator()
  path_mgr = PathManager()
  slm = SetupLibManager(machine, mem_map, path_mgr)
  vamos_legacy = ConfigDict({
      'run_command': None,
      'start_sub_process': None
  })
  slm.setup(vamos_legacy)
  slm.open_base_libs()
  slm.close_base_libs()
  slm.cleanup()
