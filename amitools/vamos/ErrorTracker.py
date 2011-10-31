from Log import log_main
from Exceptions import *
import sys
import traceback

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
  
  def report_invalid_memory(self, mode, width, addr):
    self.report_error(InvalidMemoryAccessError(chr(mode), width, addr))
  
  def report_error(self, e):
    self.has_errors = True
    self.cpu_state = self.cpu.get_state()
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
      label = self.label_mgr.get_label(addr)
      if label != None:
        delta = addr - label.addr
        log_main.error("%s -> +%06x %s",e,delta,label)
      else:
        log_main.error(e)
    else:
      log_main.error(e)
    # give CPU state dump
    for d in self.cpu.dump_state(self.cpu_state):
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
