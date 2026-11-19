import io

from amitools.vamos.loader import SegmentLoader, SegList, StreamFileObj
from helper import HostFileOpener


def loader_segload_int_test(buildlibnix, mem_alloc):
    mem, alloc = mem_alloc
    lib_file = buildlibnix.make_lib("testnix")
    loader = SegmentLoader(alloc)
    with open(lib_file, "rb") as f:
        info = loader.int_load_seglist(f, name=lib_file)
    assert info
    assert info.ami_file is None
    assert info.name == lib_file
    info.seglist.free()
    assert alloc.is_all_free()


def loader_segload_int_fobj_test(buildlibnix, mem_alloc):
    mem, alloc = mem_alloc
    lib_file = buildlibnix.make_lib("testnix")
    loader = SegmentLoader(alloc)
    with open(lib_file, "rb") as stream:
        fobj = StreamFileObj(stream)
        info = loader.int_load_seglist(fobj, name="libs/testnix.library")
    assert info
    assert info.name == "libs/testnix.library"
    info.seglist.free()
    assert alloc.is_all_free()


def loader_segload_int_fail_test(mem_alloc):
    mem, alloc = mem_alloc
    loader = SegmentLoader(alloc)
    info = loader.int_load_seglist(io.BytesIO(b""))
    assert info is None
    assert alloc.is_all_free()


def loader_segload_load_unload_test(buildlibnix, mem_alloc):
    mem, alloc = mem_alloc
    lib_file = buildlibnix.make_lib("testnix")
    loader = SegmentLoader(alloc)
    with open(lib_file, "rb") as f:
        # load
        baddr = loader.load_seglist(f, name=lib_file)
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
    opener = HostFileOpener({"blu": lib_file})
    loader = SegmentLoader(alloc, file_opener=opener)
    # load
    baddr = loader.load_ami_seglist("blu")
    assert baddr > 0
    info = loader.get_info(baddr)
    assert info.seglist.get_baddr() == baddr
    assert info.ami_file == "blu"
    # unload
    ok = loader.unload_seglist(baddr)
    assert ok
    info = loader.get_info(baddr)
    assert info is None
    assert loader.shutdown() == 0
    assert alloc.is_all_free()


def loader_segload_ami_fail_test(mem_alloc):
    mem, alloc = mem_alloc
    opener = HostFileOpener()
    loader = SegmentLoader(alloc, file_opener=opener)
    assert loader.load_ami_seglist("missing") == 0
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
