from amitools.vamos.loader import SegmentLoader
from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc


def loader_segload_sys_int_test(buildlibnix, mem_alloc):
    mem, alloc = mem_alloc
    lib_file = buildlibnix.make_lib("testnix")
    loader = SegmentLoader(alloc)
    info = loader.int_load_sys_seglist(lib_file)
    assert info
    info.seglist.free()
    assert alloc.is_all_free()


def loader_segload_ami_int_test(buildlibnix, mem_alloc):
    mem, alloc = mem_alloc
    lib_file = buildlibnix.make_lib("testnix")

    class PathMgrMock:
        def ami_to_sys_path(self, lock, ami_path, mustExist=True):
            if ami_path == "blu":
                return lib_file

    pm = PathMgrMock()
    loader = SegmentLoader(alloc, path_mgr=pm)
    info = loader.int_load_ami_seglist("blu")
    assert info
    info.seglist.free()
    assert alloc.is_all_free()


def loader_segload_sys_load_unload_test(buildlibnix, mem_alloc):
    mem, alloc = mem_alloc
    lib_file = buildlibnix.make_lib("testnix")
    loader = SegmentLoader(alloc)
    # load
    baddr = loader.load_sys_seglist(lib_file)
    assert baddr > 0
    info = loader.get_info(baddr)
    assert info.seglist.get_baddr() == baddr
    # unload
    ok = loader.unload_seglist(baddr)
    assert ok
    info = loader.get_info(baddr)
    assert info is None
    assert loader.shutdown() == 0
    assert alloc.is_all_free()


def loader_segload_ami_load_unload_test(buildlibnix, mem_alloc):
    mem, alloc = mem_alloc
    lib_file = buildlibnix.make_lib("testnix")

    class PathMgrMock:
        def ami_to_sys_path(self, lock, ami_path, mustExist=True):
            if ami_path == "blu":
                return lib_file

    pm = PathMgrMock()
    loader = SegmentLoader(alloc, path_mgr=pm)
    # load
    baddr = loader.load_ami_seglist("blu")
    assert baddr > 0
    info = loader.get_info(baddr)
    assert info.seglist.get_baddr() == baddr
    # unload
    ok = loader.unload_seglist(baddr)
    assert ok
    info = loader.get_info(baddr)
    assert info is None
    assert loader.shutdown() == 0
    assert alloc.is_all_free()


def loader_segload_register(mem_alloc):
    mem, alloc = mem_alloc
    loader = SegmentLoader(alloc)
    # my seglist
    seglist = SegList.alloc(mem, [64])
    baddr = seglist.get_baddr()
    loader.register_seglist(baddr)
    # unload registered seglist
    assert loader.unload_seglist(baddr)
    assert loader.shutdown() == 0
    assert alloc.is_all_free()


def loader_segload_unregister(mem_alloc):
    mem, alloc = mem_alloc
    loader = SegmentLoader(alloc)
    # my seglist
    seglist = SegList.alloc(mem, [64])
    baddr = seglist.get_baddr()
    loader.register_seglist(baddr)
    loader.unregister_seglist(baddr)
    # unload registered seglist
    assert not loader.unload_seglist(baddr)
    assert loader.shutdown() == 0
    assert alloc.is_all_free()
