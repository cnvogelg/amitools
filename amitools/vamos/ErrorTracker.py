from Log import log_main
from Exceptions import *
from .machine import CPUState
import sys
import traceback

class ErrorTracker:
  def __init__(self, cpu, label_mgr, terminate_func=None):
    self.cpu = cpu
    self.label_mgr = label_mgr
    self.terminate_func = terminate_func
    self.has_errors = False

  # direct callback from MEM module -> on error
  def report_invalid_memory(self, mode, width, addr):
    mode_char = chr(mode)
    try:
      error = InvalidMemoryAccessError(mode_char, width, addr)
      raise error
    except Error as error:
      self.report_error(error)

  def report_error(self, error):
    # ignore if already an error
    if self.has_errors:
      return
    self.has_errors = True
    # is a vamos or other error?
    if isinstance(error, VamosError):
      self._dump_vamos_error(error)
    else:
      self._dump_other_error(error)
    # call terminate functions
    if self.terminate_func is not None:
      self.terminate_func()

  # show vamos error with machine state
  def _dump_vamos_error(self, error):
    # show exception
    lines = traceback.format_exc().split('\n')
    for line in lines:
      if line != "":
        log_main.error(line)
    # memory error?
    if isinstance(error, InvalidMemoryAccessError):
      addr = error.addr
      label, offset = self.label_mgr.get_label_offset(addr)
      if label is not None:
        log_main.error("@%08x -> +%06x %s", addr, offset, label)
    # give CPU state dump
    cpu_state = CPUState()
    cpu_state.get(self.cpu)
    pc = cpu_state.pc
    label, offset = self.label_mgr.get_label_offset(pc)
    if label is not None:
      log_main.error("PC=%08x -> +%06x %s", pc, offset, label)
    for d in cpu_state.dump():
      log_main.error(d)

  # dump a python exception
  def _dump_other_error(self, error):
    traceback.print_exc()

