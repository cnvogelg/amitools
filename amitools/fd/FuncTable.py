from FuncDef import FuncDef

class FuncTable:
  """Store a function table"""
  def __init__(self, base_name):
    self.funcs = []
    self.base_name = base_name
    self.bias_map = {}
    self.name_map = {}
    self.max_bias = 0
  
  def get_base_name(self):
    return self.base_name
  
  def get_funcs(self):
    return self.funcs
  
  def get_func_by_bias(self, bias):
    if bias in self.bias_map:
      return self.bias_map[bias]
    else:
      return None
  
  def get_max_bias(self):
    return self.max_bias
  
  def has_func(self, name):
    return name in self.name_map
  
  def get_func_by_name(self, name):
    if name in self.name_map:
      return self.name_map[name]
    else:
      return None
  
  def get_num_funcs(self):
    return len(self.funcs)
  
  def add_func(self, f):
    # add to list
    self.funcs.append(f)
    # store by bias
    bias = f.get_bias()
    self.bias_map[bias] = f
    # store by name
    name = f.get_name()
    self.name_map[name] = f
    # adjust max bias
    if bias > self.max_bias:
      self.max_bias = bias

  def dump(self):
    print("FuncTable:",self.base_name)
    for f in self.funcs:
      f.dump()
