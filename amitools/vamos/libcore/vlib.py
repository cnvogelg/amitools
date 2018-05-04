class VLib(object):
  """a vamos interal lib.

  A vamos internal lib has a stub, a impl and allocator and patcher
  """

  def __init__(self, library, info, struct, fd, impl, stub, ctx, patcher,
               profile=None):
    self.library = library
    self.info = info
    self.struct = struct
    self.fd = fd
    self.impl = impl
    self.stub = stub
    self.ctx = ctx
    self.patcher = patcher
    self.profile = profile

  def get_library(self):
    return self.library

  def get_info(self):
    return self.info

  def get_struct(self):
    return self.struct

  def get_fd(self):
    return self.fd

  def get_impl(self):
    return self.impl

  def get_stub(self):
    return self.stub

  def get_patcher(self):
    return self.neg_size

  def get_profile(self):
    return self.profile

  def free(self,):
    # call cleanup func in impl
    if self.impl is not None:
      self.impl.finish_lib(self.ctx)
    # cleanup patcher
    self.patcher.cleanup()
    # free library memory
    self.library.free()
    # clear members but leave alone ctx and profile
    self.library = None
    self.stub = None
    self.impl = None
    self.patcher = None
