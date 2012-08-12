class FuncDef:
  """A function definition"""
  def __init__(self, name, bias, private=False):
    self.name = name
    self.bias = bias
    self.private = private
    self.args = []
  def __str__(self):
    return self.get_str()
  def get_name(self):
    return self.name
  def get_bias(self):
    return self.bias
  def is_private(self):
    return self.private
  def get_args(self):
    return self.args
  def add_arg(self, name, reg):
    self.args.append((name, reg))
  def dump(self):
    print(self.name,self.bias,self.private,self.args)
  def get_arg_str(self, with_reg=True):
    if len(self.args) == 0:
      return "()"
    elif with_reg:
      return "( " + ", ".join(map(lambda x : "%s/%s" % (x[0],x[1]), self.args)) + " )"
    else:
      return "( " + ", ".join(map(lambda x : "%s" % x[0], self.args)) + " )"      
  def get_str(self, with_reg=True):
    return self.name + self.get_arg_str(with_reg)
