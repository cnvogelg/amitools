from amitools.vamos.astructs import LibraryStruct
from amitools.vamos.atypes import Library
from amitools.fd import read_lib_fd
from .base import LibIntBase
from .stub import LibStubGen
from .patch import LibPatcherMultiTrap
from .profile import LibProfile


class LibCreator(object):
  """create a vamos internal libs"""

  def __init__(self, alloc, traps, label_mgr=None,
               fd_dir=None,
               exc_handler=None, log_missing=None, log_valid=None,
               profile_all=False):
    self.alloc = alloc
    self.traps = traps
    self.label_mgr = label_mgr
    # options
    self.fd_dir = fd_dir
    self.profile_all = profile_all
    self.stub_gen = LibStubGen(exc_handler=exc_handler,
                               log_missing=log_missing, log_valid=log_valid)

  def _create_library(self, info):
    name = info.get_name()
    id_str = info.get_id_string()
    neg_size = info.get_neg_size()
    pos_size = info.get_pos_size()
    library = Library.alloc(self.alloc, name, id_str, neg_size, pos_size)
    version = info.get_version()
    revision = info.get_revision()
    library.setup(version=version, revision=revision)
    return library

  def create_lib(self, info, ctx, impl=None, do_profile=False):
    name = info.get_name()
    # get fd
    fd = read_lib_fd(name, self.fd_dir)
    # profile?
    if do_profile or self.profile_all:
      profile = LibProfile(name, fd)
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
    library = self._create_library(info)
    addr = library.get_addr()
    # patcher
    patcher = LibPatcherMultiTrap(self.alloc.mem, self.traps, stub)
    patcher.patch_jump_table(addr)
    # fix lib sum
    library.update_sum()
    # create base
    base = LibIntBase(info, struct, fd, impl, stub, ctx, patcher, profile)
    base.add_lib_mem(library)
    # finally call startup func in impl
    if impl is not None:
      impl.setup_lib(ctx, addr)
    return base
