from MemoryBlock import MemoryBlock
from MemoryLayout import MemoryLayout
from MemoryRange import MemoryRange
from MemoryAlloc import MemoryAlloc
from MainMemory import MainMemory
from ResetRange import ResetRange
from EndRange import EndRange
from AmigaLibrary import AmigaLibrary
from AmigaExecBase import AmigaExecBase
from LibManager import LibManager
from SegmentLoader import SegmentLoader
from VamosContext import VamosContext
from PathManager import PathManager

# lib
from lib.ExecLibrary import ExecLibrary
from lib.DosLibrary import DosLibrary
from structure.ExecStruct import *
from structure.DosStruct import *

from Log import *

class Vamos:
  
  def __init__(self):
    # --- create memory layout ---
    log_mem_init.info("setting up memory")
    self.mem_size = 0x1000000
    self.mem = MainMemory(self.mem_size)
    log_mem_init.info(self.mem)

  def init_segments(self):
    # --- load segments of binary ---
    self.seg_base = 0x010000
    self.seg_size = 0x070000
    self.seg_mem = MemoryAlloc("segments", self.seg_base, self.seg_size)
    self.mem.add_range(self.seg_mem)
    log_mem_init.info(self.seg_mem)
    self.seg_loader = SegmentLoader( self.seg_mem )

  def load_main_binary(self, bin_file):
    self.bin_file = bin_file
    log_main.info("loading binary: %s", bin_file)
    self.bin_seg_list = self.load_seg(bin_file)
    if self.bin_seg_list == None:
      return False
    self.prog_start = self.bin_seg_list[0].addr
    return True

  def load_seg(self, bin_file):
    # load binary
    seg_list = self.seg_loader.load_seg(bin_file)
    if seg_list == None:
      log_main.error("failed loading binary: '%s' %s", bin_file, seg_loader.error)
      return None
    log_mem_init.info("binary segments: %s",bin_file)
    for s in seg_list:
      log_mem_init.info(s)
    return seg_list
    
  def init_stack(self):
    # --- setup stack ---
    self.magic_end = 0xff0000
    self.stack_base = 0x080000
    self.stack_size = 0x040000
    self.stack_end = self.stack_base + self.stack_size
    self.stack_mem = MemoryBlock("stack", self.stack_base, self.stack_size)
    # prepare stack
    # TOP: size
    # TOP-4: return from program -> magic_ed
    self.stack_initial = self.stack_end - 4
    self.stack_mem.w32(self.stack_initial, self.stack_size)
    self.stack_initial -= 4
    self.stack_mem.w32(self.stack_initial, self.magic_end)
    self.mem.add_range(self.stack_mem)
    log_mem_init.info(self.stack_mem)

  def init_heap(self):
    # --- setup heap ---
    self.heap_base = 0x100000
    self.heap_size = 0x040000
    self.heap_mem = MemoryAlloc("heap", self.heap_base, self.heap_size)
    self.mem.add_range(self.heap_mem)
    log_mem_init.info(self.heap_mem)

  def init_args(self, bin_args):
    # setup arguments
    self.bin_args = bin_args
    self.arg_text = " ".join(bin_args) + "\n" # AmigaDOS appends a new line to the end
    self.arg_len  = len(self.arg_text)
    self.arg_size = self.arg_len + 1
    self.arg_mem  = self.heap_mem.alloc_memory("args", self.arg_size)
    self.arg_base = self.arg_mem.addr
    self.arg_mem.w_cstr(self.arg_base, self.arg_text)
    log_main.info("args: %s (%d)", self.arg_text, self.arg_size)
    log_mem_init.info(self.arg_mem)

  def init_lib_manager(self):
    # --- libs ---
    self.lib_base = 0xf08000
    self.lib_size = 0x0e0000
    self.lib_mgr  = LibManager(self.lib_base, self.lib_size)
    self.mem.add_range(self.lib_mgr)
    log_mem_init.info(self.lib_mgr)

  def init_path_manager(self, prefix):
    self.prefix = prefix
    self.path_mgr = PathManager(prefix)

  def register_base_libs(self):
    # register libraries
    self.exec_lib_def = ExecLibrary(self.lib_mgr, self.heap_mem)
    self.lib_mgr.register_lib(self.exec_lib_def)
    self.dos_lib_def = DosLibrary(self.heap_mem)
    self.lib_mgr.register_lib(self.dos_lib_def)

  def init_context(self, cpu):
    self.ctx = VamosContext( cpu, self.mem, self.lib_mgr, self.heap_mem )
    self.ctx.bin_args = self.bin_args
    self.ctx.bin_file = self.bin_file
    self.ctx.seg_loader = self.seg_loader
    self.ctx.path_mgr = self.path_mgr
    return self.ctx

  def setup_process(self):
    # create CLI
    self.cli = self.heap_mem.alloc_struct("CLI",CLIDef)
    self.cli.w_s("cli_DefaultStack", self.stack_size / 4) # in longs
    self.cmd_mem = self.heap_mem.alloc_bstr("cmd",self.bin_file)
    self.cli.w_s("cli_CommandName", self.cmd_mem.addr)
    log_mem_init.info(self.cli)

    # create my task structure
    self.this_task = self.heap_mem.alloc_struct("ThisTask",ProcessDef)
    self.this_task.w_s("pr_CLI", self.cli.addr)
    self.ctx.this_task = self.this_task
    log_mem_init.info(self.this_task)

  def open_exec_lib(self):
    # open exec lib
    self.exec_lib = self.lib_mgr.open_lib(ExecLibrary.name, ExecLibrary.version, self.ctx)
    log_mem_init.info(self.exec_lib)
    self.exec_base_range = AmigaExecBase(self.exec_lib.get_lib_base())
    log_mem_init.info(self.exec_base_range)

  def create_old_dos_guard(self):
    # create a guard memory for tracking invalid old dos access
    self.dos_guard_base = 0xfe8000
    self.dos_guard_size = 0x008000
    self.dos_guard = MemoryRange("old dos",self.dos_guard_base, self.dos_guard_size)
    self.mem.add_range(self.dos_guard)

  # ----- magic ranges for vamos CPU control -----
  def setup_reset_range(self):
    self.reset_range = ResetRange(self.prog_start, self.stack_initial)
    self.mem.add_range(self.reset_range)
    
  def setup_execbase_range(self):
    self.mem.remove_range(self.reset_range)
    self.mem.add_range(self.exec_base_range)
    
  def setup_end_range(self):
    self.end_range = EndRange(self.magic_end)
    self.mem.add_range(self.end_range)
    