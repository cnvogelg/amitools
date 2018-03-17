

class LibBase(object):
  """base class for all libraries represented in vamos.
     both vamos internal, vamos fake and native libs use the common
     LibBase"""

  def __init__(self, info, struct=None, fd=None):
    self.info = info
    # optional struct and func table
    self.struct = struct
    self.fd = fd
    # a lib has one or more mem representations
    # more if its a (native) multi base lib
    self.lib_mems = []

  def __str__(self):
    bases = ",".join(map(str, self.lib_mems))
    return "[%s:%s]" % (self.info, bases)

  def get_info(self):
    return self.info

  def get_struct(self):
    return self.struct

  def get_fd(self):
    return self.fd

  def get_lib_mems(self):
    return self.lib_mems

  def add_lib_mem(self, lib_mem):
    self.lib_mems.append(lib_mem)

  def remove_lib_mem(self, lib_mem):
    self.lib_mems.remove(lib_mem)


class LibIntBase(LibBase):
  """a vamos interal lib has a stub, a impl and allocator and patcher"""

  def __init__(self, info, struct, fd, impl, stub, ctx, alloc, patcher,
               profile=None):
    LibBase.__init__(self, info, struct, fd)
    self.impl = impl
    self.stub = stub
    self.ctx = ctx
    self.alloc = alloc
    self.patcher = patcher
    self.profile = profile

  def get_impl(self):
    return self.impl

  def get_stub(self):
    return self.stub

  def get_alloc(self):
    return self.alloc

  def get_patcher(self):
    return self.neg_size

  def get_profile(self):
    return self.profile
