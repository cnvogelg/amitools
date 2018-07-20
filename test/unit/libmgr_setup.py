from amitools.vamos.libmgr import SetupLibManager
from amitools.vamos.machine import Machine, MemoryMap
from amitools.vamos.path import PathManager
from amitools.vamos.cfgcore import ConfigDict
from amitools.vamos.schedule import Scheduler


def libmgr_setup_default_test():
  machine = Machine()
  mem_map = MemoryMap(machine)
  mem_map.setup_ram_allocator()
  scheduler = Scheduler(machine)
  path_mgr = PathManager()
  slm = SetupLibManager(machine, mem_map, scheduler, path_mgr)
  vamos_legacy = ConfigDict({
      'run_command': None,
      'run_sub_process': None
  })
  slm.setup(vamos_legacy)
  slm.open_base_libs()
  slm.close_base_libs()
  slm.cleanup()
