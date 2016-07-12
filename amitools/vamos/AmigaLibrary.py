from CPU import *
from Log import *

import logging
import time
import inspect
import sys, traceback

from label.LabelLib import LabelLib
from AccessStruct import AccessStruct
from lib.lexec.ExecStruct import LibraryDef

class AmigaLibrary:

  op_rts = 0x4e75
  op_reset = 0x4e70

  def __init__(self, name, struct, config):
    self.name = name
    self.struct = struct
    self.config = config
    self.version = config.version

    # will be set by lib manager
    self.lib_mgr = None

    # lib flags
    self.is_native = False

    # stub generation flags
    self.profile = config.profile
    self.log_call = False
    self.log_dummy_call = False
    self.benchmark = False
    self.catch_ex = True

    # proposal of size
    self.pos_size = self.struct.get_size()
    self.neg_size = 0

    # (optional) fd describing lib functions
    self.fd = None
    # (optional) native segment list loaded for lib
    self.seg_list = None

    # --- setup state in memory ---
    # set memory version
    self.mem_version = 0
    # memory pos size and neg size
    # (might differ if native lib was loaded)
    self.mem_pos_size = 0
    self.mem_neg_size = 0
    # if lib is setup then a base address is assigned
    self.mem_obj = None
    self.addr_base = 0
    self.addr_begin = 0
    self.addr_end = 0
    self.addr_base_open = 0 # address returned by open as lib base
    self.label = None
    self.access = None
    self.lib_access = None
    # number of users opening the lib
    self.ref_cnt = 0
    self.lock_in_memory = False
    self.traps = []
    # also an access object for the lib struct members are allocated

  def calc_neg_size_from_fd(self):
    """calc the neg size from the fd bias"""
    if self.fd == None:
      return
    max_bias = self.fd.get_max_bias()
    self.neg_size = max_bias + 6

  def use_sizes(self):
    self.mem_pos_size = self.pos_size
    self.mem_neg_size = self.neg_size

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
    return ctx.mem.access.r32(sp)

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
    if self.log_dummy_call:
      def call_stub(op, pc):
        callee_pc = self.get_callee_pc(ctx)
        call_name = "%4d %s( %s ) from PC=%06x" % (bias, name, self._gen_arg_dump(args, ctx), callee_pc)
        self.log("? CALL: %s -> d0=0 (default)" % call_name, level=logging.WARN)
        ctx.cpu.w_reg(REG_D0, 0)
    else:
      def call_stub(op, pc):
        ctx.cpu.w_reg(REG_D0, 0)
    return call_stub

  def _generate_fast_call_stub(self, ctx, method):
    """generate a fast call stub without any processing"""
    def call_stub(op, pc):
      """the generic call stub: call python bound method and
         if return value exists then set it in CPU's D0 register"""
      d0 = method(ctx)
      if d0 != None:
        if type(d0) is list:
          ctx.cpu.w_reg(REG_D0, d0[0] & 0xffffffff)
          ctx.cpu.w_reg(REG_D1, d0[1] & 0xffffffff)
        else:
          ctx.cpu.w_reg(REG_D0, d0 & 0xffffffff)
    return call_stub

  def _generate_call_stub(self, ctx, bias, name, method=None, args=None):
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
      return self._generate_fast_call_stub(ctx, method)

    # ... otherwise processing is enabled and we need to synthesise a
    # suitable call stub
    need_timing = self.benchmark or self.profile
    code = ["def call_stub(op, pc):"]

    # logging (begin)
    if self.log_call:
      code.append('  callee_pc = self.get_callee_pc(ctx)')
      code.append('  call_name = "%4d %s( %s ) from PC=%06x" % (bias, name, self._gen_arg_dump(args, ctx), callee_pc)')
      code.append('  self.log("{ CALL: %s" % call_name, level=logging.INFO)')

    # timing code
    if need_timing:
      code.append('  start = time.clock()')

    # main call: call method and evaluate result
    code.append('  d0 = method(ctx)')
    code.append('  if d0 != None:')
    code.append('    if type(d0) is list:')
    code.append('      ctx.cpu.w_reg(REG_D0, d0[0] & 0xffffffff)')
    code.append('      ctx.cpu.w_reg(REG_D1, d0[1] & 0xffffffff)')
    code.append('      res = "d0=%08x  d1=%08x" % d0')
    code.append('    else:')
    code.append('      ctx.cpu.w_reg(REG_D0, d0 & 0xffffffff)')
    code.append('      res = "d0=%08x" % d0')
    code.append('  else:')
    code.append('    res = "none"')

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
      code.append('  self.log("} END CALL: %s (default)" % res, level=logging.INFO)')

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

  def trap_lib_entry(self, ctx, bias, name, method=None, args=None):
    """generate a trap in the library's jump table.
       returns True if trap was applied or False if no trap could be setup
    """
    # get call stub
    call_stub = self._generate_call_stub(ctx, bias, name, method, args)
    # allocate a trap
    tid = ctx.traps.setup(call_stub, auto_rts=True)
    if tid < 0:
      self.log("patch $%04x: '%s' -> NO TRAP AVAILABLE" % (bias, name), level=logging.ERROR)
      return False
    # generate opcode
    op = 0xa000 | tid
    # patch the lib in memory
    addr = self.addr_base - bias
    self.traps.append(tid)
    ctx.mem.access.w16(addr,op)
    self.log("patch $%04x: op=$%04x '%s' [%s]" % (bias, op, name, method), level=logging.DEBUG)
    return True

  def trap_class_entries(self, ctx, add_private=False):
    """look up all names (from fd) and if members of this class match then trap the function.

       return (number of methods patched, number of dummies patched)
    """
    # this works only with fd file!
    if self.fd == None:
      return None

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
    addr = self.addr_base - bias
    num_dummy = 0
    num_method = 0
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
          num_method += 1
        else:
          method = None
          num_dummy += 1

        # now trap entry
        self.trap_lib_entry(ctx, bias, name, method, args)

      addr -= 6
      bias += 6

    return (num_method, num_dummy)

  def create_empty_jump_table(self, ctx):
    """create a table full of RESET opcodes for all function entries"""
    bias = 6
    addr = self.addr_base
    while bias < self.neg_size:
      ctx.mem.access.w16(addr,self.op_reset)
      bias += 6
      addr -= 6

  def __str__(self):
    return "[Lib %s V%d {+%d -%d} mem: V%d {+%d -%d} <%08x, %08x, %08x> open_base=%08x ref_cnt=%d]" % \
      (self.name, self.version,
       self.pos_size, self.neg_size,
       self.mem_version,
       self.mem_pos_size, self.mem_neg_size,
       self.addr_begin, self.addr_base, self.addr_end,
       self.addr_base_open, self.ref_cnt)

  def alloc_lib_base(self, ctx):
    """alloc memory for the library base"""
    # alloc memory - use an Exec AllocMemory() compatible scheme here
    # as the lib might get free'd by library code and calling FreeMem()
    lib_size = self.mem_neg_size + self.mem_pos_size
    tag = "LibBase(%s)" % self.name
    self.mem_obj = ctx.alloc.alloc_memory(tag, lib_size, add_label=False)
    self.addr_begin = self.mem_obj.addr
    self.addr_base = self.addr_begin + self.mem_neg_size
    self.addr_end = self.addr_base + self.mem_pos_size
    self.addr_base_open = self.addr_base
    # create memory label
    self.label = LabelLib(self.name, self.addr_begin, lib_size, self.addr_base, self.struct, self)
    ctx.label_mgr.add_label(self.label)
    # create access
    self.access = AccessStruct(ctx.mem, self.struct, self.addr_base)
    self.lib_access = AccessStruct(ctx.mem, LibraryDef, self.addr_base)

  def free_lib_base(self, ctx, free_alloc=True):
    """free memory for the library base"""
    # free memory
    if free_alloc:
      ctx.alloc.free_memory(self.mem_obj)
    ctx.label_mgr.remove_label(self.label)
    # clean up
    self.mem_obj = None
    self.addr_begin = 0
    self.addr_base = 0
    self.addr_end = 0
    self.addr_base_open = 0
    self.label = None
    self.access = None
    self.lib_access = None
    # release all the traps so they can be recycled
    for tid in self.traps:
      ctx.traps.free(tid)
    self.traps = []

  def fill_lib_struct(self):
    # now we can fill the library structure with some sane values
    self.lib_access.w_s("lib_Version", self.mem_version)
    self.lib_access.w_s("lib_PosSize", self.mem_pos_size)
    self.lib_access.w_s("lib_NegSize", self.mem_neg_size)
    self.lib_access.w_s("lib_OpenCnt", 0)

  def setup_lib(self, ctx, lock_in_memory = False):
    """the lib is now used in memory at the given base address"""
    self.ref_cnt = 0
    # enable profiling
    if self.profile:
      self.profile_map = {}
    # If the library is a system library, better lock it in memory
    # to ensure that the traps are kept.
    self.lock_in_memory = lock_in_memory

  def finish_lib(self, ctx):
    """the lib is no longer used in memory"""
    if self.ref_cnt != 0:
      self.log("lib ref count != 0: %d" % self.ref_cnt, level=logging.ERROR)

    # dump profile
    if self.profile:
      self.dump_profile()

  def inc_usage(self):
    """increment usage counter"""
    self.ref_cnt += 1
    self.lib_access.w_s("lib_OpenCnt", self.ref_cnt)

  def dec_usage(self):
    """decrement usage counter"""
    if not self.lock_in_memory:
      self.ref_cnt -= 1
      self.lib_access.w_s("lib_OpenCnt", self.ref_cnt)

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
    sys.stderr.write("\n**** Unexpected exception in library stub: %s " % sys.exc_info()[1])
    traceback.print_tb(sys.exc_info()[2],file=sys.stderr)
    sys.stderr.write("\n")
    raise

