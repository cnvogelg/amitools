from amitools.vamos.libnative import LibLoader
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.machine import Machine
from amitools.vamos.atypes import ExecLibrary, Library


def setup():
  machine = Machine()
  mem = machine.get_mem()
  alloc = MemoryAlloc.for_machine(machine)
  loader = LibLoader(machine, alloc)
  sp = machine.get_ram_begin() - 4
  # setup exec
  exec_lib = ExecLibrary.alloc(alloc, "exec.library", "bla", 520*6)
  exec_lib.setup()
  exec_lib.fill_funcs()
  exec_base = exec_lib.get_addr()
  mem.w32(4, exec_base)
  machine.set_zero_mem(0, exec_base)
  return loader, alloc, mem, sp, exec_lib


def libnative_loader_load_lib_test(buildlibnix):
  loader, alloc, mem, sp, exec_lib = setup()
  # load
  lib_file = buildlibnix.make_lib('testnix')
  lib_base, seglist = loader.load_lib(lib_file, run_sp=sp)
  assert lib_base > 0
  assert seglist
  # we have to manually clean the lib here (as Exec FreeMem() does not work)
  lib = Library(mem, lib_base, alloc)
  lib.free()
  # cleanup
  seglist.free()
  exec_lib.free()
  assert alloc.is_all_free()


def libnative_loader_load_lib_fail_test():
  loader, alloc, mem, sp, exec_lib = setup()
  # load
  lib_file = "bla.library"
  lib_base, seglist = loader.load_lib(lib_file, run_sp=sp)
  assert lib_base == 0
  assert seglist is None
  # cleanup
  exec_lib.free()
  assert alloc.is_all_free()


def libnative_loader_load_lib_name_test(buildlibnix):
  loader, alloc, mem, sp, exec_lib = setup()
  # path mgr mock
  lib_file = buildlibnix.make_lib('testnix')

  class PathMgrMock:
    def ami_to_sys_path(self, lock, ami_path, mustExist=True):
      if ami_path == 'LIBS:testnix.library':
        return lib_file
  pm = PathMgrMock()
  # load
  lib_base, seglist, sys_path, ami_path = loader.load_lib_name(
      pm, "testnix.library", run_sp=sp)
  assert lib_base > 0
  assert seglist
  assert ami_path == 'LIBS:testnix.library'
  assert sys_path == lib_file
  # we have to manually clean the lib here (as Exec FreeMem() does not work)
  lib = Library(mem, lib_base, alloc)
  lib.free()
  # cleanup
  seglist.free()
  exec_lib.free()
  assert alloc.is_all_free()


def libnative_loader_load_lib_name_fail_test():
  loader, alloc, mem, sp, exec_lib = setup()
  # path mgr mock
  lib_file = "bla.library"

  class PathMgrMock:
    def ami_to_sys_path(self, lock, ami_path, mustExist=True):
      return None
  pm = PathMgrMock()
  # load
  lib_base, seglist, sys_path, ami_path = loader.load_lib_name(
      pm, "testnix.library", run_sp=sp)
  assert lib_base == 0
  assert seglist is None
  assert ami_path is None
  assert sys_path is None
  # cleanup
  exec_lib.free()
  assert alloc.is_all_free()


def libnative_loader_base_name_test():
  f = LibLoader.get_lib_base_name
  assert f("bla.library") == "bla.library"
  assert f("a/relative/bla.library") == "bla.library"
  assert f("abs:bla.library") == "bla.library"
  assert f("abs:relative/bla.library") == "bla.library"


def libnative_loader_search_paths_test():
  f = LibLoader.get_lib_search_paths
  # abs path
  assert f("progdir:bla.library") == ["progdir:bla.library"]
  assert f("abs:bla.library") == ["abs:bla.library"]
  # rel path
  assert f("bla.library") == ["bla.library",
                              "libs/bla.library",
                              "PROGDIR:bla.library",
                              "PROGDIR:libs/bla.library",
                              "LIBS:bla.library"]
  assert f("foo/bla.library") == ["foo/bla.library",
                                  "libs/foo/bla.library",
                                  "PROGDIR:foo/bla.library",
                                  "PROGDIR:libs/foo/bla.library",
                                  "LIBS:foo/bla.library"]
