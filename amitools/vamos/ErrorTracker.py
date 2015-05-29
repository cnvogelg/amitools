from Log import log_main
from Exceptions import *
import sys
import traceback
import CPU

class ErrorTracker:
  def __init__(self, cpu, label_mgr):
    self.cpu = cpu
    self.label_mgr = label_mgr
    self.vamos_error = None
    self.other_error = None
    self.has_errors = False
    self.cpu_state = None
    self.other_tb = None
    self.other_type = None
    self.other_value = None

  # direct callback from MEM module -> on error
  def report_invalid_memory(self, mode, width, addr):
    mode_char = chr(mode)
    self.report_error(InvalidMemoryAccessError(mode_char, width, addr))

  def report_error(self, e):
    # ignore if already an error
    if self.has_errors:
      return
    self.has_errors = True
    self.cpu_state = CPU.CPUState()
    self.cpu_state.get(self.cpu)
    if isinstance(e, VamosError):
      self.vamos_error = e
    else:
      self.other_error = e
      exc_type, exc_value, exc_traceback = sys.exc_info()
      self.other_tb = traceback.extract_tb(exc_traceback)
      self.other_type = exc_type
      self.other_value = exc_value

  # show vamos error with machine state
  def dump_vamos_error(self):
    e = self.vamos_error
    if e == None:
      return
    # memory error?
    if isinstance(e, InvalidMemoryAccessError):
      addr = e.addr
      label,offset = self.label_mgr.get_label_offset(addr)
      if label != None:
        log_main.error("%s -> +%06x %s",e,offset,label)
      else:
        log_main.error(e)
    else:
      log_main.error(e)
    # give CPU state dump
    pc = self.cpu_state.pc
    label,offset = self.label_mgr.get_label_offset(pc)
    if label != None:
      log_main.error("PC=%08x -> +%06x %s",pc,offset,label)
    for d in self.cpu_state.dump():
      log_main.error(d)

  # dump a python exception
  def dump_other_error(self):
    e = self.other_error
    if e == None:
      return
    if self.other_type == KeyboardInterrupt:
      log_main.error("Keyboard Abort")
    else:
      log_main.error("*** Python EXCEPTION: %s (%s) ***",self.other_value,self.other_type)
      for t in self.other_tb:
        log_main.error("%s:%d in %s: %s",*t)

  def dump(self):
    self.dump_vamos_error()
    self.dump_other_error()
