
from MemoryStruct import MemoryStruct
from MemoryLayout import InvalidMemoryAccessError
from CPU import *

class AmigaLibrary(MemoryStruct):
  
  op_rts = 0x4e75
  
  def __init__(self, name, version, calls, struct, context):
    self.name = name
    self.version = version
    self.calls = calls
    self.struct = struct
    self.context = context
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

    # keep mem and cpu
    self.cpu = self.context.get_cpu()
    self.mem = self.context.get_mem()
  
  def __str__(self):
    return "[AmigaLib:%s V%d num_jumps=%d pos_size=%d neg_size=%d [%06x ... %06x ... %06x]]" % \
      (self.name, self.version, self.num_jumps, self.pos_size, self.neg_size, self.begin_addr, self.base_addr, self.end_addr)
  
  def set_addr(self, addr):
    self.base_addr = addr
    self.begin_addr = addr - self.neg_size
    self.pos_size = self.struct.get_size()
    self.end_addr = addr + self.pos_size
    MemoryStruct.__init__(self, self.name, addr, self.struct)    

  def set_funcs(self, funcs):
    for f in funcs:
      self.set_func(*f)

  def set_func(self, key, callee):
    off = key / 6
    self.set_by_offset(off, callee)
    
  def set_by_offset(self, off, callee, name="none", param=None, ret=REG_D0):
    self.jump_table[off][1] = callee

  def is_inside(self, addr):
    return ((addr >= self.begin_addr) and (addr < self.end_addr))
    
  def read_mem(self, width, addr):
    # pos range -> redirect to struct
    if addr >= self.addr:
      return MemoryStruct.read_mem(self, width, addr)
    # trap lib call and return RTS opcode
    elif(width == 1):
      self.call_vector(addr)
      return self.op_rts
    # invalid access to neg area
    else:
      raise InvalidMemoryAccessError(width, addr)

  def write_mem(self, width, addr, val):
    # pos range -> redirect to struct
    if addr >= self.addr:
      return MemoryStruct.write_mem(self, width, addr, val)
    # writes to neg area are not allowed for now
    else:
      raise InvalidMemoryAccessError(width, addr)

  def call_vector(self, addr):
    off = (self.base_addr - addr) / 6
    key = (addr - self.base_addr)
    jump_entry = self.jump_table[off]

    # trace call
    call = jump_entry[0]
    print "  [lib_call: %s: %4d %s( %s )]" % (self.name, call[0], call[1], self.gen_arg_dump(call[2]))

    callee = jump_entry[1]
    if callee != None:
      d0 = callee()
      if d0 != None:
        print "  [return d0=%08x]" % (d0)
        self.cpu.w_reg(REG_D0, d0)
    else:
      print "  [default d0=0]"
      self.cpu.w_reg(REG_D0, 0)
    
  def get_callee_pc(self):
    sp = self.cpu.r_reg(REG_A7)
    return self.context.mem.read_mem(2,sp)
    
  def log(self,msg):
    print "\t[%s]" % msg
  
  def gen_arg_dump(self,args):
    if args == None:
      return ""
    result = []
    for a in args:
      name = a[0]
      reg = a[1]
      reg_num = int(reg[1])
      if reg[0] == 'a':
        reg_num += 8
      val = self.cpu.r_reg(reg_num)
      result.append("%s[%s]=%x" % (name,reg,val))
    return ", ".join(result)
