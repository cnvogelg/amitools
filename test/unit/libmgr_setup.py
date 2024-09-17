from amitools.vamos.libmgr import SetupLibManager
from amitools.vamos.machine import Machine, MemoryMap, Runtime
from amitools.vamos.path import PathManager
from amitools.vamos.cfgcore import ConfigDict
from amitools.vamos.schedule import Scheduler


def libmgr_setup_default_test():
    machine = Machine()
    runtime = Runtime(machine)
    mem_map = MemoryMap(machine)
    mem_map.setup_ram_allocator()
    scheduler = Scheduler(machine)
    path_mgr = PathManager()
    slm = SetupLibManager(machine, mem_map, runtime.run, scheduler, path_mgr)
    slm.setup()
    slm.open_base_libs()
    slm.close_base_libs()
    slm.cleanup()
