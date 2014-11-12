from LabelManager import LabelManager
from LabelRange import LabelRange
from MemoryAlloc import MemoryAlloc
from MainMemory import MainMemory
from AmigaLibrary import AmigaLibrary
from LibManager import LibManager
from SegmentLoader import SegmentLoader
from PathManager import PathManager
from FileManager import FileManager
from LockManager import LockManager
from PortManager import PortManager
from ErrorTracker import ErrorTracker
from DosListManager import DosListManager
from Trampoline import Trampoline

# lib
from lib.ExecLibrary import ExecLibrary
from lib.DosLibrary import DosLibrary
from lib.lexec.ExecStruct import *
from lib.dos.DosStruct import *
from lib.IntuitionLibrary import IntuitionLibrary

from Log import *
from CPU import *

class Vamos:
  
  def __init__(self, raw_mem, cpu, cfg):
    self.raw_mem = raw_mem
    self.ram_size = raw_mem.ram_size
    self.cpu = cpu
    self.cpu_type = cfg.cpu
    self.path_mgr = PathManager( cfg )

    # create a label manager and error tracker
    self.label_mgr = LabelManager()
    self.error_tracker = ErrorTracker(cpu, self.label_mgr)
    self.label_mgr.error_tracker = self.error_tracker

    # set a label for first two dwords
    label = LabelRange("zero_page",0,8)
    self.label_mgr.add_label(label)
    
    # create memory access
    self.mem = MainMemory(self.raw_mem, self.error_tracker)
    self.mem.ctx = self

    # create memory allocator
    self.mem_begin = 0x1000
    self.alloc = MemoryAlloc(self.mem, 0, self.ram_size, self.mem_begin, self.label_mgr)
    
    # create segment loader
    self.seg_loader = SegmentLoader( self.mem, self.alloc, self.label_mgr, self.path_mgr )

    # lib manager
    self.lib_mgr = LibManager( self.label_mgr, cfg)
    
    # no current process right now
    self.process = None
    self.proc_list = []

  def init(self, cfg):
    self.init_managers()
    self.register_base_libs(cfg)
    self.create_old_dos_guard()
    self.open_exec_lib()
    return True

  def cleanup(self):
    self.close_exec_lib()
    self.alloc.dump_orphans()
  
  # ----- process handling -----
  
  def _set_this_task(self, proc):
    """tell exec about this process and all others referencing process from here"""
    self.process = proc
    self.exec_lib.set_this_task(proc)
  
  def set_main_process(self, proc):
    log_proc.info("set main process: %s", proc)
    self.proc_list.append(proc)
    self._set_this_task(proc)
  
  def start_sub_process(self, proc):
    log_proc.info("start sub process: %s", proc)
    self.proc_list.append(proc)
    self._set_this_task(proc)
    
    # setup trampoline to enter sub process
    tr = Trampoline(self, "SubProcJump")

    # reserve a long for old stack
    old_stack_off = tr.dc_l(0)

    # code starts
    tr.save_all_but_d0()
    # new proc registers: d0=arg_len a0=arg_cptr
    tr.set_dx_l(0, proc.arg_len)
    tr.set_ax_l(0, proc.arg_base)
    # d2=stack_size.  this value is also in 4(sp) (see Process.init_stack), but
    # various C programs rely on it being present (1.3-3.1 at least have it).
    tr.set_dx_l(2, proc.stack_size)
    # to track old dos values
    tr.set_ax_l(2, self.dos_guard_base)
    tr.set_ax_l(5, self.dos_guard_base)
    tr.set_ax_l(6, self.dos_guard_base)
    # save old stack and set new stack
    tr.write_ax_l(7, old_stack_off, True) # write to data offset (dc.l above)
    new_stack = proc.stack_initial
    tr.set_ax_l(7, new_stack)
    # call code! (jmp - return value is on stack)
    tr.jmp(proc.prog_start)
    # restore stack (set a label to return from new stack - see below)
    return_off = tr.get_code_offset()
    tr.read_ax_l(7, old_stack_off, True) # read from data offset (dc.l above)
    # restore regs
    tr.restore_all_but_d0()
    # trap to clean up sub process resources
    def trap_stop_sub_process():
      self.stop_sub_process()
    tr.final_rts(trap_stop_sub_process)
    # realize trampoline in memory (data+code)
    tr.done()
    # get label addr -> set as return value of new stack
    return_addr = tr.get_code_addr(return_off)
    log_proc.debug("new_stack=%06x return_addr=%06x", new_stack, return_addr)
    # place return address for new process
    self.mem.access.w32(new_stack, return_addr)

  def stop_sub_process(self):
    # get return value
    ret_code = self.cpu.r_reg(REG_D0)
    # pop process
    proc = self.proc_list.pop()
    log_proc.info("stop sub process: %s ret_code=%d", proc, ret_code)
    proc.free()
    
  # ----- init environment -----
  
  def init_managers(self):
    self.doslist_base = self.mem.reserve_special_range()
    self.doslist_size = 0x010000
    self.doslist_mgr = DosListManager(self.path_mgr, self.doslist_base, self.doslist_size)
    self.label_mgr.add_label(self.doslist_mgr)
    self.mem.set_special_range_read_funcs(self.doslist_base, r32=self.doslist_mgr.r32_doslist)
    log_mem_init.info(self.doslist_mgr)

    # fill dos list
    volumes = self.path_mgr.get_all_volume_names()
    for vol in volumes:
      self.doslist_mgr.add_volume(vol)
    
    self.lock_base = self.mem.reserve_special_range()
    self.lock_size = 0x010000
    self.lock_mgr = LockManager(self.path_mgr, self.doslist_mgr, self.lock_base, self.lock_size)
    self.label_mgr.add_label(self.lock_mgr)
    self.mem.set_special_range_read_funcs(self.lock_base, r32=self.lock_mgr.r32_lock)
    log_mem_init.info(self.lock_mgr)
    
    self.file_base = self.mem.reserve_special_range()
    self.file_size = 0x010000
    self.file_mgr = FileManager(self.path_mgr, self.file_base, self.file_size)
    self.label_mgr.add_label(self.file_mgr)
    self.mem.set_special_range_read_funcs(self.file_base, r32=self.file_mgr.r32_fh)
    log_mem_init.info(self.file_mgr)

    self.port_base = self.mem.reserve_special_range()
    self.port_size = 0x010000
    self.port_mgr  = PortManager(self.port_base, self.port_size)
    self.label_mgr.add_label(self.port_mgr)
    log_mem_init.info(self.port_mgr)

  def register_base_libs(self, cfg):
    # register libraries
    # exec
    exec_cfg = cfg.get_lib_config('exec.library')
    self.exec_lib_def = ExecLibrary(self.lib_mgr, self.alloc, exec_cfg)
    self.lib_mgr.register_vamos_lib(self.exec_lib_def)
    # dos
    dos_cfg = cfg.get_lib_config('dos.library')
    self.dos_lib_def = DosLibrary(self.mem, self.alloc, dos_cfg)
    self.dos_lib_def.set_managers(self.path_mgr, self.lock_mgr, self.file_mgr, self.port_mgr, self.seg_loader)
    self.lib_mgr.register_vamos_lib(self.dos_lib_def)
    # intuition
    int_cfg = cfg.get_lib_config('intuition.library')
    self.int_lib_def = IntuitionLibrary(int_cfg)
    self.lib_mgr.register_vamos_lib(self.int_lib_def)

  def open_exec_lib(self):
    # open exec lib
    self.exec_lib = self.lib_mgr.open_lib(ExecLibrary.name, 0, self)
    self.exec_lib_def.set_cpu(self.cpu_type)
    self.exec_lib_def.set_ram_size(self.ram_size)
    log_mem_init.info(self.exec_lib)

  def close_exec_lib(self):
    self.lib_mgr.close_lib(self.exec_lib.addr_base, self)

  def create_old_dos_guard(self):
    # create a guard memory for tracking invalid old dos access
    self.dos_guard_base = self.mem.reserve_special_range()
    self.dos_guard_size = 0x010000
    label = LabelRange("old_dos",self.dos_guard_base, self.dos_guard_size)
    self.label_mgr.add_label(label)
    log_mem_init.info(label)
