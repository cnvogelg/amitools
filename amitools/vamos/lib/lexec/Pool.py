from amitools.vamos.Log import log_exec
from amitools.vamos.Exceptions import *
from Puddle import Puddle

class Pool:

  def __init__(self, alloc, flags, size, thresh):
    self.alloc = alloc
    self.minsize = size
    self.flags = flags
    self.thresh = thresh    
    self.puddles = []

  def __del__(self):
    for puddle in self.puddles:
      del puddle
    self.puddles = []
        
  def AllocPooled(self, name, size):
    result = 0
    if size >= self.thresh:
      puddle = Puddle(self.alloc, name, size)
      if puddle != None:
        self.puddles.append(puddle)
        result = puddle.AllocPooled(name, size)
    else: 
      for puddle in self.puddles:
        result = puddle.AllocPooled(name,size)
        if (result > 0):
          break
        # none of the puddles had enough memory
      if (result == 0): 
        puddle = Puddle(self.alloc, name, self.minsize)
        if puddle != None:
          self.puddles.append(puddle)
          result = puddle.AllocPooled(name, size)
    
    if (result == 0): 
      log_exec.info("AllocPooled: Unable to allocate memory (%x)", size)
    
    return result