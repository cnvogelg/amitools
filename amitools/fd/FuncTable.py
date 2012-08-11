from FuncDef import FuncDef

class FuncTable:
  """Store a function table"""
  def __init__(self, base_name):
    self.funcs = []
    self.base_name = base_name
    self.bias_map = {}
  
  def get_base_name(self):
    return self.base_name
  
  def get_funcs(self):
    return self.funcs
  
  def get_func_by_bias(self, bias):
    if bias in self.bias_map:
      return self.bias_map[bias]
    else:
      return None
    
  def add_func(self, f):
    self.funcs.append(f)
    self.bias_map[f.get_bias()] = f

  def dump(self):
    print("FuncTable:",self.base_name)
    for f in self.funcs:
      f.dump()
