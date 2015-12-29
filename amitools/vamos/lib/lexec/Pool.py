from amitools.vamos.Log import log_exec
from amitools.vamos.Exceptions import *
from Puddle import Puddle

class Pool:

  def __init__(self, mem, alloc, flags, size, thresh):
    self.alloc   = alloc
    self.mem     = mem
    self.minsize = size
    self.flags   = flags
    self.thresh  = thresh    
    self.puddles = []

  def __del__(self):
    while len(self.puddles) > 0:
      puddle = self.puddles.pop()
      del puddle

  def __str__(self):
    poolstr = ""
    for puddle in self.puddles:
      if poolstr == "":
        poolstr = "{%s}" % puddle
      else:
        poolstr = "%s,{%s}" % (poolstr,puddle)
    return poolstr
        
  def AllocPooled(self, label_mgr, name, size):
    result = 0
    if size >= self.thresh:
      puddle = Puddle(self.mem, self.alloc, label_mgr, name, size)
      if puddle != None:
        self.puddles.append(puddle)
        result = puddle.AllocPooled(name, size)
    else: 
      for puddle in self.puddles:
        result = puddle.AllocPooled(name,size)
        if result > 0:
          break
        # none of the puddles had enough memory
      if result == 0:
        puddle = Puddle(self.mem, self.alloc, label_mgr, name, self.minsize)
        if puddle != None:
          self.puddles.append(puddle)
          result = puddle.AllocPooled(name, size)
    if result == 0: 
      log_exec.info("AllocPooled: Unable to allocate memory (%x)", size)
    #print "%s allocated -> %s" % (size,self)
    return result

  def FreePooled(self, mem, size):
    if mem != 0:
      for puddle in self.puddles:
        if puddle.contains(mem,size):
          puddle.FreePooled(mem,size)
    #print "%s released -> %s" % (size,self)
