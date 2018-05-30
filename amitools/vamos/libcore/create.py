from amitools.vamos.astructs import LibraryStruct
from amitools.vamos.atypes import Library, NodeType
from amitools.fd import read_lib_fd
from .vlib import VLib
from .stub import LibStubGen
from .patch import LibPatcherMultiTrap


class LibCreator(object):
  """create a vamos internal libs"""

  def __init__(self, alloc, traps,
               fd_dir=None,
               log_missing=None, log_valid=None,
               profiler=None):
    self.alloc = alloc
    self.traps = traps
    # options
    self.fd_dir = fd_dir
    self.profiler = profiler
    self.stub_gen = LibStubGen(log_missing=log_missing, log_valid=log_valid)

  def _create_library(self, info, is_dev):
    if is_dev:
      ltype = NodeType.NT_DEVICE
    else:
      ltype = NodeType.NT_LIBRARY
    name = info.get_name()
    id_str = info.get_id_string()
    neg_size = info.get_neg_size()
    pos_size = info.get_pos_size()
    library = Library.alloc(self.alloc, name, id_str, neg_size, pos_size)
    version = info.get_version()
    revision = info.get_revision()
    library.setup(version=version, revision=revision, type=ltype)
    return library

  def create_lib(self, info, ctx, impl=None):
    name = info.get_name()
    if name.endswith('.device'):
      is_dev = True
    elif name.endswith('.library'):
      is_dev = False
    else:
      raise ValueError("create_lib: %s is neither lib nor dev!" % name)
    # get fd
    fd = read_lib_fd(name, self.fd_dir)
    assert fd.is_device == is_dev
    # profile?
    if self.profiler:
      profile = self.profiler.create_profile(name, fd)
    else:
      profile = None
    # create stub
    if impl is None:
      stub = self.stub_gen.gen_fake_stub(name, fd, ctx, profile)
      struct = LibraryStruct
    else:
      stub = self.stub_gen.gen_stub(name, impl, fd, ctx, profile)
      struct = impl.get_struct_def()
    # adjust info pos/neg size
    if info.pos_size == 0:
      info.pos_size = struct.get_size()
    if info.neg_size == 0:
      info.neg_size = fd.get_neg_size()
    # allocate and init lib
    library = self._create_library(info, is_dev)
    addr = library.get_addr()
    # patcher
    patcher = LibPatcherMultiTrap(self.alloc, self.traps, stub)
    patcher.patch_jump_table(addr)
    # fix lib sum
    library.update_sum()
    # create vamos lib and combine all pieces
    vlib = VLib(library, info, struct, fd, impl,
                stub, ctx, patcher, profile, is_dev)
    return vlib
