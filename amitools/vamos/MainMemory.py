from MemoryLayout import MemoryLayout
from Exceptions import InvalidMemoryAccessError
from AccessMemory import AccessMemory
import traceback
import sys

class MainMemory(MemoryLayout):
  
  def __init__(self, size):
    MemoryLayout.__init__(self, "main", 0, size)
    self.invalid_access = []
    self.force_quit = False
    self.exit = None
    self.access = AccessMemory(self)
    
  def get_read_funcs(self):
    return ( lambda addr: self.read_mem(0,addr),
             lambda addr: self.read_mem(1,addr),
             lambda addr: self.read_mem(2,addr))

  def get_write_funcs(self):
    return ( lambda addr,val: self.write_mem(0,addr,val),
             lambda addr,val: self.write_mem(1,addr,val),
             lambda addr,val: self.write_mem(2,addr,val))

  def read_mem(self, width, addr):
    try:
      if self.force_quit and width == 1:
        return 0x4e70 # RESET opcode
      return MemoryLayout.read_mem(self, width, addr)
    except InvalidMemoryAccessError as e:
      self._handle_mem_error(e)
      self.trace_read(e.width, e.addr, 0, text="OUT!");
      return 0
    except BaseException as e:
      self._handle_exc(e)
      return 0

  def write_mem(self, width, addr, val):
    try:
      return MemoryLayout.write_mem(self, width, addr, val)
    except InvalidMemoryAccessError as e:
      self._handle_mem_error(e)
      self.trace_write(e.width, e.addr, 0, text="OUT!");
      return None
    except BaseException as e:
      self._handle_exc(e)
      return None
  
  def _handle_mem_error(self, e):
    self.trace_write(e.width, e.addr, 0, text="OUT!")
    e.state = self.ctx.cpu.get_state()
    e.pc_range_offset = self.get_range_offset(e.state['pc'])
    self.invalid_access.append(e)
    self.force_quit = True
  
  def _handle_exc(self, e):
    e.state = self.ctx.cpu.get_state()
    e.pc_range_offset = self.get_range_offset(e.state['pc'])
    exc_type, exc_value, exc_traceback = sys.exc_info()
    self.exit = {
      'tb' : traceback.extract_tb(exc_traceback),
      'type' : exc_type,
      'value' : exc_value
    }
    self.force_quit = True
