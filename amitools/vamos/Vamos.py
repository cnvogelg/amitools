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
from lib.IconLibrary import IconLibrary
from lib.lexec.ExecStruct import *
from lib.dos.DosStruct import *

from Log import *
from CPU import *

class Vamos:
  
  def __init__(self, raw_mem, cpu, path_mgr):
    self.raw_mem = raw_mem
    self.ram_size = raw_mem.ram_size
    self.cpu = cpu
    self.path_mgr = path_mgr

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
    self.lib_mgr = LibManager( self.label_mgr )
    
    # no current process right now
    self.process = None
    self.proc_list = []
    self.tr_list = []

  def init(self, cfg):
    self.init_managers()
    self.register_base_libs(cfg.lib_versions['exec'], cfg.lib_versions['dos'])
    self.init_trampoline()  
    self.create_old_dos_guard()
    self.open_exec_lib()
    return True

  def cleanup(self):
    self.close_exec_lib()
    self.free_trampoline()
    self.alloc.dump_orphans()
  
  # ----- process handling -----
  
  def _set_this_task(self, proc):
    """tell exec about this process and all others referencing process from here"""
    self.process = proc
    self.exec_lib.lib_class.set_this_task(self.exec_lib, proc)
  
  def set_main_process(self, proc):
    log_proc.info("set main process: %s", proc)
    self.proc_list.append(proc)
    self._set_this_task(proc)
  
  def start_sub_process(self, proc):
    log_proc.info("start sub process: %s", proc)
    self.proc_list.append(proc)
    self._set_this_task(proc)
    
    # setup trampoline to enter sub process
    tr_mem_size = 128
    tr_mem = self.alloc.alloc_memory("SubProcJump", tr_mem_size)
    tr = Trampoline(self, tr_mem)
    tr.init()
    tr.save_all_but_d0()
    # new proc registers: d0=arg_len a0=arg_cptr
    tr.set_dx_l(0, proc.arg_len)
    tr.set_ax_l(0, proc.arg_base)
    # to track old dos values
    tr.set_ax_l(2, self.dos_guard_base)
    tr.set_ax_l(5, self.dos_guard_base)
    tr.set_ax_l(6, self.dos_guard_base)
    # setup new stack
    stack_save_addr = tr_mem.addr + tr_mem_size - 4
    tr.write_ax_l(7, stack_save_addr)
    new_stack = proc.stack_initial
    tr.set_ax_l(7, new_stack)
    # call code! (jmp - return value is on stack)
    tr.jmp(proc.prog_start)
    # restore stack (set a label to return from new stack - see below)
    lab = tr.set_label()
    tr.read_ax_l(7, stack_save_addr)
    # restore regs
    tr.restore_all_but_d0()
    # trap to clean up sub process resources
    tr.trap(lambda x : self.stop_sub_process())
    tr.rts()
    tr.done()
    # get label addr -> set as return value of new stack
    lab_addr = tr.get_label(lab)
    log_proc.debug("new_stack=%06x trampoline_return=%06x", new_stack, lab_addr)
    self.mem.access.w32(new_stack, lab_addr)
    
    # push trampoline
    self.tr_list.append(tr)
  
  def stop_sub_process(self):
    # get return value
    ret_code = self.cpu.r_reg(REG_D0)
    # pop process
    proc = self.proc_list.pop()
    log_proc.info("stop sub process: %s ret_code=%d", proc, ret_code)
    proc.free()
    # pop trampoline
    tr = self.tr_list.pop()
    self.alloc.free_memory(tr.mem)
    
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

  def register_base_libs(self, exec_version, dos_version):
    # register libraries
    # exec
    self.exec_lib_def = ExecLibrary(self.lib_mgr, self.alloc, version=exec_version)
    self.lib_mgr.register_int_lib(self.exec_lib_def)
    # dos
    self.dos_lib_def = DosLibrary(self.mem, self.alloc, version=dos_version)
    self.dos_lib_def.set_managers(self.path_mgr, self.lock_mgr, self.file_mgr, self.port_mgr, self.seg_loader)
    self.lib_mgr.register_int_lib(self.dos_lib_def)
    # icon
    self.icon_lib_def = IconLibrary()
    self.lib_mgr.register_int_lib(self.icon_lib_def)

  def init_trampoline(self):
    self.tr_mem_size = 256
    self.tr_mem = self.alloc.alloc_memory("Trampoline", self.tr_mem_size)
    self.tr = Trampoline(self, self.tr_mem)

  def free_trampoline(self):
    self.alloc.free_memory(self.tr_mem)

  def open_exec_lib(self):
    # open exec lib
    self.exec_lib = self.lib_mgr.open_lib(ExecLibrary.name, 0, self)
    log_mem_init.info(self.exec_lib)

  def close_exec_lib(self):
    self.lib_mgr.close_lib(self.exec_lib.lib_base, self)

  def create_old_dos_guard(self):
    # create a guard memory for tracking invalid old dos access
    self.dos_guard_base = self.mem.reserve_special_range()
    self.dos_guard_size = 0x010000
    label = LabelRange("old_dos",self.dos_guard_base, self.dos_guard_size)
    self.label_mgr.add_label(label)
    log_mem_init.info(label)
