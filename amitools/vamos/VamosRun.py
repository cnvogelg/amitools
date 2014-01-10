import time

from CPU import *
from Log import log_main

class Trap:
  def __init__(self, addr, func, one_shot):
    self.addr = addr
    self.func = func
    self.one_shot = one_shot
  def __str__(self):
    return "[@%06x:%s:one_shot=%s]" % (self.addr, self.func, self.one_shot)

class VamosRun:
  def __init__(self, vamos, benchmark=False):
    self.cpu = vamos.cpu
    self.mem = vamos.mem
    self.ctx = vamos
    # store myself in context
    self.ctx.run = self
    
    self.stay = True
    self.et = vamos.error_tracker
    self.trap_time = 0.0
    
    self.traps = {}
    self.trap_addrs = []
    
    self.benchmark = benchmark
    
  def init_cpu(self):
    # prepare m68k
    log_main.info("setting up m68k")

    # setup stack & first PC
    self.mem.access.w32(0, self.ctx.process.stack_initial)
    self.mem.access.w32(4, self.ctx.process.prog_start)
    self.cpu.pulse_reset()

    # set end RESET opcode at 0 and execbase at 4
    op_reset = 0x04e70
    self.mem.access.w16(0, op_reset)
    self.mem.access.w32(4, self.ctx.exec_lib.lib_base)

    # setup arg in D0/A0
    self.cpu.w_reg(REG_D0, self.ctx.process.arg_len)
    self.cpu.w_reg(REG_A0, self.ctx.process.arg_base)

    # d2=stack_size.  this value is also in 4(sp) (see Process.init_stack), but
    # various C programs rely on it being present (1.3-3.1 at least have it).
    self.cpu.w_reg(REG_D2, self.ctx.process.stack_size)

    # to track old dos values
    self.cpu.w_reg(REG_A2, self.ctx.dos_guard_base)
    self.cpu.w_reg(REG_A5, self.ctx.dos_guard_base)
    self.cpu.w_reg(REG_A6, self.ctx.dos_guard_base)

  def add_trap(self, addr, func, one_shot=False):
    trap = Trap(addr, func, one_shot)
    self.traps[addr] = trap
    self.trap_addrs = self.traps.keys()
    return trap
  
  def remove_trap(self, trap):
    del self.traps[trap.addr]
    self.trap_addrs = self.traps.keys()

  def reset_func(self):
    """this callback is entered from CPU whenever a RESET opcode is encountered.
       dispatch to end vamos or call a trap.
    """
    pc = self.cpu.r_pc() - 2
    # addr == 0 or an error occurred -> end reached
    if pc == 0 or self.et.has_errors:
      self.cpu.end()
      self.stay = False
    # a lib trap!
    else:
      try:
        begin = time.clock()
        
        # a registered trap?
        if pc in self.trap_addrs:
          trap = self.traps[pc]
          trap.func(self.ctx)
          if trap.one_shot:
            self.remove_trap(trap)          
        # unknown RESET opcode found
        else:
          raise UnsupportedVamosFeature("Unexpected RESET opcode")
        
        end = time.clock()
        # account for trap time
        self.trap_time += end - begin
      except BaseException as e:
        self.et.report_error(e)
        self.cpu.end()
        self.stay = False

  def _calc_benchmark(self, total_cycles, delta_time):
    python_time = self.trap_time + self.ctx.lib_mgr.bench_total    
    cpu_time = delta_time - python_time
    mhz = total_cycles / (1000000.0 * delta_time)
    cpu_percent = cpu_time * 100.0 / delta_time
    python_percent = 100.0 - cpu_percent
    log_main.info("done %d cycles in host time %.4fs -> %5.2f MHz m68k CPU", total_cycles, cpu_time, mhz)
    log_main.info("code time %.4fs (%.2f %%), python time %.4fs (%.2f %%) -> total time %.4fs", \
      cpu_time, cpu_percent, python_time, python_percent, delta_time)

  def run(self, cycles_per_run=1000, max_cycles=0):
    """main run loop of vamos"""
    log_main.info("start cpu: %06x", self.ctx.process.prog_start)

    total_cycles = 0
    start_time = time.clock()

    # main loop
    while self.stay:
      total_cycles += self.cpu.execute(cycles_per_run)
      # end after enough cycles
      if max_cycles > 0 and total_cycles >= max_cycles:
        break
      # some error fored a quit?
      if self.et.has_errors:
        break

    end_time = time.clock()
    
    # calc benchmark values
    if self.benchmark:
      self._calc_benchmark( total_cycles, end_time - start_time )

    # if errors happened then report them now
    if self.et.has_errors:
      log_main.error("After %d cycles:", total_cycles)
      self.et.dump()
      exit_code = 1
    else:
      # get exit code from CPU
      exit_code = int(self.cpu.r_reg(REG_D0))
      log_main.info("exit code=%d", exit_code)

    return exit_code
    