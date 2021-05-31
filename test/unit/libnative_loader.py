from amitools.vamos.libnative import LibLoader
from amitools.vamos.loader import SegmentLoader
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.machine import Machine
from amitools.vamos.libtypes import ExecLibrary, Library


def setup(path_mgr=None):
    machine = Machine()
    mem = machine.get_mem()
    alloc = MemoryAlloc.for_machine(machine)
    segload = SegmentLoader(alloc, path_mgr=path_mgr)
    loader = LibLoader(machine, alloc, segload)
    sp = machine.get_ram_begin() - 4
    # setup exec
    exec_lib = ExecLibrary.alloc(
        alloc, name="exec.library", id_string="bla", neg_size=520 * 6
    )
    assert exec_lib.LibNode.neg_size.val == 520 * 6
    exec_lib.new_lib()
    exec_lib.fill_funcs()
    exec_base = exec_lib.get_addr()
    mem.w32(4, exec_base)
    machine.set_zero_mem(0, exec_base)
    return loader, segload, alloc, mem, sp, exec_lib


def free_lib(mem, alloc, lib_base):
    lib = Library(mem, lib_base)
    mem_obj = alloc.get_memory(lib_base - lib.neg_size.val)
    assert mem_obj
    alloc.free_memory(mem_obj)


def libnative_loader_load_sys_lib_test(buildlibnix):
    loader, segload, alloc, mem, sp, exec_lib = setup()
    # load
    lib_file = buildlibnix.make_lib("testnix")
    lib_base, seglist_baddr = loader.load_sys_lib(lib_file, run_sp=sp)
    assert lib_base > 0
    assert seglist_baddr > 0
    # we have to manually clean the lib here (as Exec FreeMem() does not work)
    free_lib(mem, alloc, lib_base)
    # cleanup
    segload.unload_seglist(seglist_baddr)
    assert segload.shutdown() == 0
    exec_lib.free()
    assert alloc.is_all_free()


def libnative_loader_load_sys_lib_fail_test():
    loader, segload, alloc, mem, sp, exec_lib = setup()
    # load
    lib_file = "bla.library"
    lib_base, seglist_baddr = loader.load_sys_lib(lib_file, run_sp=sp)
    assert lib_base == 0
    assert seglist_baddr == 0
    # cleanup
    exec_lib.free()
    assert alloc.is_all_free()


def libnative_loader_load_ami_lib_test(buildlibnix):
    # path mgr mock
    lib_file = buildlibnix.make_lib("testnix")

    class PathMgrMock:
        def ami_to_sys_path(self, lock, ami_path, mustExist=True):
            if ami_path == "LIBS:testnix.library":
                return lib_file

    pm = PathMgrMock()
    loader, segload, alloc, mem, sp, exec_lib = setup(pm)
    # load
    lib_base, seglist_baddr = loader.load_ami_lib("testnix.library", run_sp=sp)
    assert lib_base > 0
    assert seglist_baddr > 0
    info = segload.get_info(seglist_baddr)
    assert info
    assert info.ami_file == "LIBS:testnix.library"
    assert info.sys_file == lib_file
    # we have to manually clean the lib here (as Exec FreeMem() does not work)
    free_lib(mem, alloc, lib_base)
    # cleanup
    segload.unload_seglist(seglist_baddr)
    assert segload.shutdown() == 0
    exec_lib.free()
    assert alloc.is_all_free()


def libnative_loader_load_ami_lib_fail_test():
    # path mgr mock
    lib_file = "bla.library"

    class PathMgrMock:
        def ami_to_sys_path(self, lock, ami_path, mustExist=True):
            return None

    pm = PathMgrMock()
    loader, segload, alloc, mem, sp, exec_lib = setup(pm)
    # load
    lib_base, seglist_baddr = loader.load_ami_lib("testnix.library", run_sp=sp)
    assert lib_base == 0
    assert seglist_baddr == 0
    # cleanup
    assert segload.shutdown() == 0
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
    assert f("bla.library") == [
        "bla.library",
        "libs/bla.library",
        "PROGDIR:bla.library",
        "PROGDIR:libs/bla.library",
        "LIBS:bla.library",
    ]
    assert f("foo/bla.library") == [
        "foo/bla.library",
        "libs/foo/bla.library",
        "PROGDIR:foo/bla.library",
        "PROGDIR:libs/foo/bla.library",
        "LIBS:foo/bla.library",
    ]
