import pytest
from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.astructs import LibraryStruct
from amitools.vamos.atypes import Library, CString, NodeType, LibFlags


def atypes_library_base_test():
  mem = MockMemory()
  alloc = MemoryAlloc(mem)
  # alloc lib
  name = "my.library"
  id_str = "my.library 1.2"
  neg_size = 36
  pos_size = LibraryStruct.get_size()
  lib = Library.alloc(alloc, name, id_str, neg_size)
  assert lib.get_name() == name
  assert lib.get_id_string() == id_str
  size = lib.get_size()
  assert pos_size == lib.get_pos_size()
  assert neg_size == lib.get_neg_size()
  assert size == pos_size + neg_size
  # lib setup
  flags = LibFlags(LibFlags.LIBF_SUMMING, LibFlags.LIBF_CHANGED)
  ltype = NodeType(NodeType.NT_DEVICE)
  pri = -3
  ver = 1
  rev = 2
  lib.setup(version=ver, revision=rev, pri=pri, flags=flags, type=ltype)
  # check lib
  node = lib.get_node()
  assert node.get_succ() is None
  assert node.get_pred() is None
  assert node.get_type() == ltype
  assert node.get_pri() == pri
  assert lib.get_flags() == flags
  assert lib.get_pad() == 0
  assert lib.get_neg_size() == neg_size
  assert lib, get_pos_size() == pos_size
  assert lib.get_version() == ver
  assert lib.get_revision() == rev
  assert lib.get_sum() == 0
  assert lib.get_open_cnt() == 0
  assert lib.get_name() == name
  assert lib.get_id_string() == id_str
  # done
  lib.free()
  assert alloc.is_all_free()
