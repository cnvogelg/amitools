
class LibCtx(object):
  """the default context a library receives"""
  def __init__(self, cpu, mem):
    self.cpu = cpu
    self.mem = mem

  def __str__(self):
    return "[LibCtx:cpu=%s,mem=%s]" % (self.cpu, self.mem)


class LibCtxMap(object):
  """register non-default context objects for libraries"""
  def __init__(self):
    self.ctx_map = {}
    self.def_ctx = None

  def add_ctx(self, name, ctx):
    self.ctx_map[name] = ctx

  def get_ctx(self, name):
    if name in self.ctx_map:
      return self.ctx_map[name]
    return self.get_default_ctx()

  def set_default_ctx(self, def_ctx):
    self.def_ctx = def_ctx

  def get_default_ctx(self):
    return self.def_ctx
