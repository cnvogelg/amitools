from CPU import *

from Log import *
import logging
import time
import inspect

class AmigaLibrary:
  
  op_rts = 0x4e75
  op_reset = 0x4e70
  
  def __init__(self, name, version, struct, profile=False):
    self.name = name
    self.version = version
    self.struct = struct

    # flags
    self.profile = profile
    self.fast_call = False

    # needs calc size
    self.pos_size = None
    self.neg_size = None
    self.fd = None

  def calc_size(self, fd):
    """pass the fd describing the lib 
       and setup the jump table (neg size) and library struct (pos size)
    """
    # keep function description
    self.fd = fd
    # get pos_size
    self.pos_size = self.struct.get_size()
    # calc neg_size
    max_bias = fd.get_max_bias()
    self.neg_size = max_bias + 6
  
  def _get_class_methods(self):
    """return a map with method name to bound method mapping of this class"""    
    members = inspect.getmembers(self, predicate=inspect.ismethod)
    result = {}
    for member in members:
      name = member[0]
      method = member[1]
      result[name] = method
    return result

  def get_callee_pc(self,ctx):
    """a call stub log helper to extract the callee's pc"""
    sp = ctx.cpu.r_reg(REG_A7)
    return ctx.mem.read_mem(2,sp)
    
  def _gen_arg_dump(self,args,ctx):
    """a call stub helper to dump the registers of a call"""
    if args == None or len(args) == 0:
      return ""
    result = []
    for a in args:
      name = a[0]
      reg = a[1]
      reg_num = int(reg[1])
      if reg[0] == 'a':
        reg_num += 8
      val = ctx.cpu.r_reg(reg_num)
      result.append("%s[%s]=%08x" % (name,reg,val))
    return ", ".join(result)

  def _generate_call_stub(self, mem_lib, ctx, bias, name, method=None, args=None):
    """generate a call stub for this given bound method
       this will construct a small wrapper around the library call to be set as a trap
       function.
       For unknown methods it can generate a default/dummy stub that only set d0=0
    """    
    # method is available
    if method != None:
      # fast call a method
      if self.fast_call:
        # is profiling enabled?
        if self.profile:
          def call_stub(op, pc):
            start = time.clock()
            d0 = method(mem_lib, ctx)
            end = time.clock()
            delta = end - start
            self._account_profile_data(name, delta)
            if d0 != None:
              ctx.cpu.w_reg(REG_D0, d0)
        # no profiling, really fast call :)
        else:
          def call_stub(op, pc):
            d0 = method(mem_lib, ctx)
            if d0 != None:
              ctx.cpu.w_reg(REG_D0, d0)
      # call method with optional trace
      else:
        # is profiling enabled?
        if self.profile:
          # with profiling
          def call_stub(op, pc):
            callee_pc = self.get_callee_pc(ctx)
            call_name = "%4d %s( %s ) from PC=%06x" % (bias, name, self._gen_arg_dump(args, ctx), callee_pc)
            self.log("{ CALL: %s" % call_name, level=logging.WARN)
            start = time.clock()
            d0 = method(mem_lib, ctx)
            end = time.clock()
            delta = end - start
            self._account_profile_data(name, delta)
            self.log("} END CALL: d0=%s (default)" % (d0), level=logging.WARN)
            if d0 != None:
              ctx.cpu.w_reg(REG_D0, d0)
        else:
          # no profiling
          def call_stub(op, pc):
            callee_pc = self.get_callee_pc(ctx)
            call_name = "%4d %s( %s ) from PC=%06x" % (bias, name, self._gen_arg_dump(args, ctx), callee_pc)
            self.log("{ CALL: %s" % call_name, level=logging.WARN)
            d0 = method(mem_lib, ctx)
            self.log("} END CALL: d0=%s (default)" % (d0), level=logging.WARN)
            if d0 != None:
              ctx.cpu.w_reg(REG_D0, d0)

    # dummy method:
    else:
      if self.fast_call:
        def call_stub(op, pc):
          ctx.cpu.w_reg(REG_D0, 0)
      else:
        def call_stub(op, pc):
          callee_pc = self.get_callee_pc(ctx)
          call_name = "%4d %s( %s ) from PC=%06x" % (bias, name, self._gen_arg_dump(args, ctx), callee_pc)
          self.log("? CALL: %s -> d0=0 (default)" % call_name, level=logging.WARN)
          ctx.cpu.w_reg(REG_D0, 0)
        
    return call_stub
    
  def trap_lib_entry(self, mem_lib, ctx, bias, name, method=None, args=None):
    """generate a trap in the library's jump table.
       returns True if trap was applied or False if no trap could be setup
    """
    # get call stub
    call_stub = self._generate_call_stub(mem_lib, ctx, bias, name, method, args)
    # allocate a trap
    tid = ctx.cpu.trap_setup(call_stub, auto_rts=True)
    if tid < 0:
      self.log("patch $%04x: '%s' -> NO TRAP AVAILABLE" % (bias, name), level=logging.ERROR)
      return False
    # generate opcode
    op = 0xa000 | tid
    # patch the lib in memory
    addr = mem_lib.lib_base - bias
    ctx.mem.write_mem(1,addr,op)
    self.log("patch $%04x: '%s' [%s]" % (bias, name, method), level=logging.DEBUG)
    return True  

  def trap_class_entries(self, mem_lib, ctx, reset_others=False, add_private=False):
    """look up all names (from fd) and if members of this class match then trap the function.
       optionally you can place a RESET opcode on all other entry points
    """
    # this works only with fd file!
    if self.fd == None:
      return False
    
    # build a map: bias -> func name
    bias_map = {}
    for f in self.fd.get_funcs():
      # add public and optionally private API calls
      if add_private or not f.is_private():
        bias_map[f.get_bias()] = (f.get_name(), f.get_args())
    
    # get all implemented class methods
    method_map = self._get_class_methods()
      
    # loop over all biases
    bias = 6
    addr = mem_lib.lib_base - bias
    while bias < self.neg_size:
      # bias is found in FD
      if bias in bias_map:
        # get function name from FD
        info = bias_map[bias]
        name = info[0]
        args = info[1]
        # is a method implemented in this class?
        if name in method_map:
          method = method_map[name]
        else:
          method = None
        
        # now trap entry
        self.trap_lib_entry(mem_lib, ctx, bias, name, method, args)

      # place a RESET in untrapped lib entries
      elif reset_others:
        self.log("patch $%04x: <RESET>" % bias, level=logging.DEBUG)
        ctx.mem.write_mem(1,addr,self.op_reset)
        
      addr -= 6
      bias += 6

  def __str__(self):
    return "[Lib %s V%d pos_size=%d neg_size=%d]" % \
      (self.name, self.version, self.pos_size, self.neg_size)
  
  def setup_lib(self, mem_lib, ctx):
    # enable profiling
    if self.profile:
      self.profile_map = {}
  
  def finish_lib(self, mem_lib, ctx):
    # dump profile
    if self.profile:
      self.dump_profile()
  
  def get_num_vectors(self):
    return self.num_jumps
    
  def get_struct(self):
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
  
  def log(self, text, level=logging.INFO):
    log_lib.log(level, "[%16s]  %s", self.name, text)

  def dump_profile(self):
    log_prof.info("'%s' Function Call Profile", self.name)
    funcs = sorted(self.profile_map.keys())
    sum_total = 0.0
    for f in funcs:
      entry = self.profile_map[f]
      cnt = entry[1]
      total = entry[0]
      per_call = total / cnt
      log_prof.info("  %20s: #%8d  total=%10.4f  per call=%10.4f", f, cnt, total, per_call)
      sum_total += total
    log_prof.info("sum total=%.4f",sum_total)

  def _account_profile_data(self, func, delta):
    """account profiling data for the current function"""
    if self.profile_map.has_key(func):
      entry = self.profile_map[func]
      entry[0] += delta
      entry[1] += 1
    else:
      entry = [delta, 1]
      self.profile_map[func] = entry
