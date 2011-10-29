from Log import log_main
import sys
import traceback

class ErrorTracker:
  def __init__(self):
    self.vamos_error = None
    self.other_error = None
    self.has_errors = False
    self.cpu_state = None
    self.other_tb = None
    self.other_type = None
    self.other_value = None
    
  def report_vamos_error(self, e, cpu):
    self.vamos_error = e
    self.has_errors = True
    self.cpu_state = cpu.get_state()
      
  def report_other_error(self, e):
    self.other_error = e
    self.has_errors = True
    exc_type, exc_value, exc_traceback = sys.exc_info()
    self.other_tb = traceback.extract_tb(exc_traceback)
    self.other_type = exc_type
    self.other_value = exc_value
  
  # show vamos error with machine state
  def dump_vamos_error(self, cpu):
    e = self.vamos_error
    if e == None:
      return
    # show vamos error
    log_main.error(e)
    # give CPU state dump
    for d in cpu.dump_state(self.cpu_state):
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
  
  def dump(self, cpu):
    self.dump_vamos_error(cpu)
    self.dump_other_error()
