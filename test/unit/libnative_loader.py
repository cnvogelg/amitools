from amitools.vamos.libnative import LibLoader
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.machine import Machine
from amitools.vamos.atypes import ExecLibrary, Library


def libnative_loader_load_lib_test(buildlibnix):
  machine = Machine()
  mem = machine.get_mem()
  alloc = MemoryAlloc.for_machine(machine)
  loader = LibLoader(mapchine, alloc)
  sp = machine.get_ram_begin() - 4
  # setup exec
  exec_lib = ExecLibrary.alloc(alloc, "exec.library", "bla", 520*6)
  exec_lib.setup()
  exec_lib.fill_funcs()
  exec_base = exec_lib.get_addr()
  mem.w32(4, exec_base)
  machine.set_zero_mem(0, exec_base)
  # load
  lib_file = buildlibnix.make_lib('testnix')
  lib_base, seglist = loader.load_lib(lib_file, run_sp=sp)
  assert lib_base > 0
  assert seglist
  # we have to manually clean the lib here (as Exec FreeMem() does not work)
  lib = Library(mem ,lib_base, alloc)
  lib.free()
  # cleanup
  seglist.free()
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
                              "libs:bla.library"]
  assert f("foo/bla.library") == ["foo/bla.library",
                                  "libs/foo/bla.library",
                                  "PROGDIR:foo/bla.library",
                                  "PROGDIR:libs/foo/bla.library",
                                  "libs:foo/bla.library"]
