
class LibCtx(object):
  """the default context a library receives"""
  def __init__(self, machine):
    self.machine = machine
    self.cpu = machine.get_cpu()
    self.mem = machine.get_mem()
    # will be set on creation
    self.vlib = None
    self.lib_mgr = None

  def __str__(self):
    return "[LibCtx:cpu=%s,mem=%s]" % (self.cpu, self.mem)


class LibCtxMap(object):
  """register non-default context objects for libraries"""
  def __init__(self, machine):
    self.ctx_map = {}
    self.machine = machine

  def add_ctx(self, name, ctx):
    self.ctx_map[name] = ctx

  def get_ctx(self, name):
    if name in self.ctx_map:
      return self.ctx_map[name]
    # return a new default context
    return LibCtx(self.machine)
