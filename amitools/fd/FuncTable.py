from FuncDef import FuncDef

class FuncTable:
  """Store a function table"""
  def __init__(self, base_name):
    self.funcs = []
    self.base_name = base_name
  
  def get_base_name(self):
    return self.base_name
  
  def get_funcs(self):
    return self.funcs
    
  def add_func(self, f):
    self.funcs.append(f)

  def dump(self):
    print("FuncTable:",self.base_name)
    for f in self.funcs:
      f.dump()
