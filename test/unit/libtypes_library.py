import pytest
from amitools.vamos.machine.opcodes import op_rts
from amitools.vamos.libstructs import LibraryStruct, NodeType, LibFlags
from amitools.vamos.libtypes import Library
from amitools.vamos.label import LabelLib
from amitools.fd import read_lib_fd


def libtypes_library_base_test(mem_alloc):
    mem, alloc = mem_alloc
    # alloc lib
    name = "my.library"
    id_str = "my.library 1.2"
    neg_size = 12
    pos_size = LibraryStruct.get_size()
    lib = Library.alloc(alloc, name=name, id_string=id_str, neg_size=neg_size)
    assert lib._mem_obj.size == neg_size + pos_size
    assert pos_size == lib.pos_size.val
    assert neg_size == lib.neg_size.val
    assert lib.node.name.str == name
    assert lib.id_string.str == id_str
    # lib setup
    flags = LibFlags.LIBF_SUMMING | LibFlags.LIBF_CHANGED
    ltype = NodeType.NT_DEVICE
    pri = -3
    ver = 1
    rev = 2
    lib.new_lib(version=ver, revision=rev, pri=pri, flags=flags, type=ltype)
    # check lib
    node = lib.node
    assert node.succ.ref is None
    assert node.pred.ref is None
    assert node.type.val == ltype
    assert node.pri.val == pri
    assert lib.flags.val == flags
    assert lib.pad.val == 0
    assert lib.neg_size.val == neg_size
    assert lib.pos_size.val == pos_size
    assert lib.version.val == ver
    assert lib.revision.val == rev
    assert lib.sum.val == 0
    assert lib.open_cnt.val == 0
    assert lib.node.name.str == name
    assert lib.id_string.str == id_str
    # fill funcs
    lib.fill_funcs()
    lib_base = lib.get_addr()
    assert mem.r16(lib_base - 6) == op_rts
    # done
    lib.free()
    assert alloc.is_all_free()


def libtypes_library_sum_test(mem_alloc):
    mem, alloc = mem_alloc
    # alloc lib
    name = "my.library"
    id_str = "my.library 1.2"
    neg_size = 30
    lib = Library.alloc(alloc, name=name, id_string=id_str, neg_size=neg_size)
    # assume rounded neg size
    assert lib.neg_size.val == 32
    mem.w32(lib.addr - 32, 0xDEADBEEF)
    mem.w32(lib.addr - 28, 0xCAFEBABE)
    my_sum = (0xDEADBEEF + 0xCAFEBABE) & 0xFFFFFFFF
    lib_sum = lib.calc_sum()
    assert lib_sum == my_sum
    lib.update_sum()
    assert lib.sum.val == my_sum
    assert lib.check_sum()
    # done
    lib.free()
    assert alloc.is_all_free()


def libtypes_library_open_cnt_test(mem_alloc):
    mem, alloc = mem_alloc
    # alloc lib
    name = "my.library"
    id_str = "my.library 1.2"
    neg_size = 30
    pos_size = LibraryStruct.get_size()
    lib = Library.alloc(alloc, name=name, id_string=id_str, neg_size=neg_size)
    # test open cnt
    assert lib.open_cnt.val == 0
    lib.inc_open_cnt()
    assert lib.open_cnt.val == 1
    lib.dec_open_cnt()
    assert lib.open_cnt.val == 0
    # done
    lib.free()
    assert alloc.is_all_free()


def libtypes_library_label_test(mem_alloc):
    mem, alloc = mem_alloc
    name = "vamostest.library"
    id_str = "vamostest.library 0.1"
    fd = read_lib_fd("vamostest.library")
    neg_size = fd.get_neg_size()
    lib = Library.alloc(alloc, name=name, id_string=id_str, neg_size=neg_size, fd=fd)
    # check for label
    label = lib._mem_obj.label
    if alloc.get_label_mgr():
        assert label
        assert isinstance(label, LabelLib)
        assert label.fd == fd
    else:
        assert not label
    # done
    lib.free()
    assert alloc.is_all_free()
