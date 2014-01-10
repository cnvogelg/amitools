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

    # will be set by lib manager
    self.lib_mgr = None

    # stub generation flags
    self.profile = profile
    self.log_call = False
    self.benchmark = False
    self.catch_ex = False

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

  def _generate_dummy_call_stub(self, ctx, bias, name, args=None):
    """a call stub for unsupported/empty functions.
       only trace the call and return D0=0
    """
    if self.log_call:
      def call_stub(op, pc):
        callee_pc = self.get_callee_pc(ctx)
        call_name = "%4d %s( %s ) from PC=%06x" % (bias, name, self._gen_arg_dump(args, ctx), callee_pc)
        self.log("? CALL: %s -> d0=0 (default)" % call_name, level=logging.WARN)
        ctx.cpu.w_reg(REG_D0, 0)
    else:
      def call_stub(op, pc):
        ctx.cpu.w_reg(REG_D0, 0)
    return call_stub

  def _generate_fast_call_stub(self, mem_lib, ctx, method):
    """generate a fast call stub without any processing"""
    def call_stub(op, pc):
      """the generic call stub: call python bound method and 
         if return value exists then set it in CPU's D0 register"""
      d0 = method(mem_lib, ctx)
      if d0 != None:
        ctx.cpu.w_reg(REG_D0, d0)
    return call_stub

  def _generate_call_stub(self, mem_lib, ctx, bias, name, method=None, args=None):
    """generate a call stub for this given bound method
       this will construct a small wrapper around the library call to be set as a trap
       function.
       For unknown methods it can generate a default/dummy stub that only set d0=0
    """
    # if no method is available then generate a dummy stub
    if method == None:
      return self._generate_dummy_call_stub(ctx, bias, name, args)

    # if extra processing is disabled then create a compact call stub
    if not self.log_call and not self.benchmark and not self.profile and not self.catch_ex:
      return self._generate_fast_call_stub(mem_lib, ctx, method)
    
    # ... otherwise processing is enabled and we need to synthesise a
    # suitable call stub
    need_timing = self.benchmark or self.profile
    code = ["def call_stub(op, pc):"]
    
    # logging (begin)
    if self.log_call:
      code.append('  callee_pc = self.get_callee_pc(ctx)')
      code.append('  call_name = "%4d %s( %s ) from PC=%06x" % (bias, name, self._gen_arg_dump(args, ctx), callee_pc)')
      code.append('  self.log("{ CALL: %s" % call_name, level=logging.WARN)')
    
    # timing code
    if need_timing:
      code.append('  start = time.clock()')
      
    # main call: call method and evaluate result
    code.append('  d0 = method(mem_lib, ctx)')
    code.append('  if d0 != None:')
    code.append('    ctx.cpu.w_reg(REG_D0, d0)')
    
    # timing code
    if need_timing:
      code.append('  end = time.clock()')
      code.append('  delta = end - start')
    if self.profile:
      code.append('  self._account_profile_data(name, delta)')
    if self.benchmark:
      code.append('  self._account_benchmark_data(delta)')

    # logging (end)
    if self.log_call:
      code.append('  self.log("} END CALL: d0=%s (default)" % (d0), level=logging.WARN)')

    # wrap exception handler
    if self.catch_ex:
      c = [code[0]]
      c.append("  try:")
      for l in code[1:]:
        c.append("  " + l)
      c.append("  except:")
      c.append("    self._handle_exc()")
      code = c
      
    # generate code
    l = {}
    l.update(globals())
    l.update(locals())
    exec "\n".join(code) in l
    return l['call_stub']
    
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
    self.log("patch $%04x: op=$%04x '%s' [%s]" % (bias, op, name, method), level=logging.DEBUG)
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
  
  def _account_benchmark_data(self, delta):
    self.lib_mgr.bench_total += delta
    
  def _handle_exc(self):
    """handle an exception that occurred inside the call stub's python code"""
    # TBD
    print "ARGH"

