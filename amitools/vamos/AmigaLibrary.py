from CPU import *

class AmigaLibrary:
  
  def __init__(self, name, version, calls, struct):
    self.name = name
    self.version = version
    self.calls = calls
    self.struct = struct
    self.trace = False

    # get pos_size
    self.pos_size = struct.get_size()

    # calc neg_size
    last_call_bias = calls[-1][0]    
    self.neg_size = last_call_bias + 6
    self.num_jumps = self.neg_size / 6
        
    # setup jump_table: [call_tuple|None, PyFunc|None]
    self.jump_table = []
    call_id = 0
    off = 0
    for i in xrange(self.num_jumps):
      call = None
      cur_call = self.calls[call_id]
      if cur_call[0]==off:
        call = cur_call
        call_id += 1
      off += 6
      self.jump_table.append([call,None])
  
  def set_trace(self, on):
    self.trace = on
  
  def __str__(self):
    return "[Lib %s V%d num_jumps=%d pos_size=%d neg_size=%d]" % \
      (self.name, self.version, self.num_jumps, self.pos_size, self.neg_size)
  
  def open(self, mem_lib, ctx):
    pass
  
  def close(self, mem_lib, ctx):
    pass
  
  def get_pos_struct(self):
    return self.struct
  
  def get_name(self):
    return self.name
    
  def get_version(self):
    return self.version
  
  def get_total_size(self):
    return self.neg_size + self.pos_size
  
  def get_neg_size(self):
    return self.neg_size
    
  def get_pos_size(self):
    return self.pos_size
  
  def set_funcs(self, funcs):
    for f in funcs:
      self.set_func(*f)

  def set_func(self, key, callee):
    off = key / 6
    self.set_by_offset(off, callee)
    
  def set_by_offset(self, off, callee, name="none", param=None, ret=REG_D0):
    self.jump_table[off][1] = callee

  def trace_log(self, text):
    if self.trace:
      print "\t[%s] %s" % (self.name, text)

  def call_vector(self, off, mem_lib, ctx):
    jump_entry = self.jump_table[off]

    call = jump_entry[0]
    self.trace_log("call: %4d %s( %s )" % (call[0], call[1], self.gen_arg_dump(call[2], ctx)))

    callee = jump_entry[1]
    if callee != None:
      d0 = callee(mem_lib, ctx)
      if d0 != None:
        self.trace_log("return d0=%08x" % (d0))
        ctx.cpu.w_reg(REG_D0, d0)
    else:
      self.trace_log("default d0=0")
      ctx.cpu.w_reg(REG_D0, 0)
    
  def get_callee_pc(self,ctx):
    sp = ctx.cpu.r_reg(REG_A7)
    return ctx.mem.read_mem(2,sp)
    
  def gen_arg_dump(self,args,ctx):
    if args == None:
      return ""
    result = []
    for a in args:
      name = a[0]
      reg = a[1]
      reg_num = int(reg[1])
      if reg[0] == 'a':
        reg_num += 8
      val = ctx.cpu.r_reg(reg_num)
      result.append("%s[%s]=%x" % (name,reg,val))
    return ", ".join(result)
