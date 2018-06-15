class ConfigDict(dict):
  """a dictionary that also allows to access fields direclty by key"""

  def __getattr__(self, name):
    if name in self:
      return self[name]
    else:
      raise AttributeError

  def __setattr__(self, name, val):
    self[name] = val

  def __delattr__(self, name):
    del self[name]
