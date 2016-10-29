import time
import ctypes
import re
import os

from amitools.vamos.AmigaLibrary import *
from dos.DosStruct import *
from lexec.ExecStruct import ListDef, MinListDef, NodeDef
from amitools.vamos.Exceptions import *
from amitools.vamos.Log import log_dos
from amitools.vamos.AccessStruct import AccessStruct
from amitools.vamos.path.PathManager import PathManager
from amitools.vamos.path.PathManager import AssignManager
from dos.Args import *
from dos.Error import *
from dos.AmiTime import *
from util.TagList import *
import dos.Printf
from dos.DosTags import DosTags
from dos.PatternMatch import Pattern, pattern_parse, pattern_match
from dos.MatchFirstNext import MatchFirstNext
from amitools.vamos.label.LabelStruct import LabelStruct
from dos.CommandLine import CommandLine
from amitools.vamos.Process import Process
import dos.PathPart
from dos.DosList import DosList
from dos.LockManager import LockManager
from dos.FileManager import FileManager

class DosLibrary(AmigaLibrary):
  name = "dos.library"

  DOSFALSE = 0
  DOSTRUE = 0xffffffff

  LV_VAR   = 0	# an variable
  LV_ALIAS = 1	# an alias
  LVF_IGNORE            =       0x80
  GVF_GLOBAL_ONLY	=       0x100
  GVF_LOCAL_ONLY        =	0x200
  GVF_BINARY_VAR	=	0x400

  def __init__(self, mem, alloc, path, config):
    AmigaLibrary.__init__(self, self.name, DosLibraryDef, config)
    self.mem      = mem
    self.alloc    = alloc
    self.path_mgr = path

  def setup_lib(self, ctx):
    AmigaLibrary.setup_lib(self, ctx)
    log_dos.info("open dos.library V%d", self.version)
    # init own state
    self.io_err = 0
    self.ctx = ctx
    self.mem_allocs = {}
    self.seg_lists = {}
    self.matches = {}
    self.rdargs = {}
    self.dos_objs = {}
    self.errstrings = {}
    self.path = []
    self.resident = []
    self.local_vars = {}
    # setup RootNode
    self.root_struct = ctx.alloc.alloc_struct("RootNode",RootNodeDef)
    self.access.w_s("dl_Root",self.root_struct.addr)
    # setup DosInfo
    self.dos_info = ctx.alloc.alloc_struct("DosInfo",DosInfoDef)
    self.root_struct.access.w_s("rn_Info",self.dos_info.addr)
    # setup dos list
    self.dos_list = DosList(self.path_mgr, self.path_mgr.assign_mgr, ctx.mem, ctx.alloc)
    baddr = self.dos_list.build_list(ctx.path_mgr)
    # create lock manager
    self.lock_mgr = LockManager(ctx.path_mgr, self.dos_list, ctx.alloc, ctx.mem)
    ctx.path_mgr.setup(self.lock_mgr)
    # equip the DosList with all the locks
    self.dos_list.add_locks(self.lock_mgr)
    # create file manager
    self.file_mgr = FileManager(ctx.path_mgr, ctx.alloc, ctx.mem)
    # currently we use a single fake port for all devices
    self.fs_handler_port = ctx.exec_lib.port_mgr.create_port("FakeFSPort",self.file_mgr)
    log_dos.info("dos fs handler port: %06x" % self.fs_handler_port)
    self.file_mgr.setup(self.fs_handler_port)

  def finish_lib(self, ctx):
    # free port
    ctx.exec_lib.port_mgr.free_port(self.fs_handler_port)
    # finish file manager
    self.file_mgr.finish(ctx.process.is_native_shell())
    # free dos list
    self.dos_list.free_list()
    # free path
    for path,lock in self.path:
      ctx.alloc.free_struct(path)
      self.lock_mgr.release_lock(lock)
    # free resident nodes
    for res in self.resident:
      self._free_mem(res)
    # free shell variables
    while len(self.local_vars) > 0:
      var = self.local_vars.values()[0]
      self.delete_var(ctx,var)
    # self.delete_var(ctx,var)
    # free RootNode
    ctx.alloc.free_struct(self.root_struct)
    # free DosInfo
    ctx.alloc.free_struct(self.dos_info)
    AmigaLibrary.finish_lib(self, ctx)

  # ----- IoErr -----

  def IoErr(self, ctx):
    if self.io_err in dos_error_strings:
      errstring = dos_error_strings[self.io_err]
    else:
      errstring = "%d" % self.io_err
    log_dos.info("IoErr: %d (%s)" % (self.io_err, errstring))
    return self.io_err

  def setioerr(self, ctx, err):
    self.io_err = err
    ctx.process.this_task.access.w_s("pr_Result2",err)

  def SetIoErr(self, ctx):
    old_io_err = self.io_err
    self.setioerr(ctx,ctx.cpu.r_reg(REG_D1))
    log_dos.info("SetIoErr: IoErr=%d old IoErr=%d", self.io_err, old_io_err)
    return old_io_err

  def Fault(self, ctx):
    errcode = ctx.cpu.r_reg(REG_D1)
    hdr_ptr = ctx.cpu.r_reg(REG_D2)
    buf_ptr = ctx.cpu.r_reg(REG_D3)
    buf_len = ctx.cpu.r_reg(REG_D4)
    if errcode >= 0x80000000:
      idx = errcode - 0x100000000
    else:
      idx = errcode
    if hdr_ptr != 0:
      hdr = ctx.mem.access.r_cstr(hdr_ptr)
    else:
      hdr = ""
    if dos_error_strings.has_key(idx):
      err_str = dos_error_strings[idx]
    else:
      err_str = "%d ERROR" % self.io_err
    log_dos.info("Fault: code=%d header='%s' err_str='%s'", self.io_err, hdr, err_str)
    # write to stdout
    if hdr_ptr != 0:
      txt = "%s: %s" % (hdr, err_str)
    else:
      txt = "%s" % err_str
    ctx.mem.access.w_cstr(buf_ptr,txt[:buf_len-1])
    return self.DOSTRUE

  def PrintFault(self, ctx):
    self.io_err = ctx.cpu.r_reg(REG_D1)
    hdr_ptr = ctx.cpu.r_reg(REG_D2)
    if self.io_err >= 0x80000000:
      idx = self.io_err - 0x100000000
    else:
      idx = self.io_err
    # get header string
    if hdr_ptr != 0:
      hdr = ctx.mem.access.r_cstr(hdr_ptr)
    else:
      hdr = ""
    # get error string
    if dos_error_strings.has_key(idx):
      err_str = dos_error_strings[idx]
    else:
      err_str = "%d ERROR" % self.io_err
    log_dos.info("PrintFault: code=%d header='%s' err_str='%s'", self.io_err, hdr, err_str)
    # write to stdout
    if hdr_ptr != 0:
      txt = "%s: %s\n" % (hdr, err_str)
    else:
      txt = "%s\n" % err_str
    fh = ctx.process.get_output()
    fh.write(txt)
    return self.DOSTRUE


  # ----- current dir

  def get_current_dir(self):
    cur_dir = self.ctx.process.get_current_dir()
    return self.lock_mgr.get_by_b_addr(cur_dir >> 2)

  # ----- dos API -----

  def DateStamp(self, ctx):
    ds_ptr = ctx.cpu.r_reg(REG_D1)
    ds = AccessStruct(ctx.mem,DateStampDef,struct_addr=ds_ptr)
    t = time.time()
    at = sys_to_ami_time(t)
    log_dos.info("DateStamp: ptr=%06x sys_time=%d time=%s", ds_ptr, t, at)
    ds.w_s("ds_Days",at.tday)
    ds.w_s("ds_Minute",at.tmin)
    ds.w_s("ds_Tick",at.tick)
    return ds_ptr

  def DateToStr(self, ctx):
    dt_ptr = ctx.cpu.r_reg(REG_D1)
    dt = AccessStruct(ctx.mem,DateTimeDef,struct_addr=dt_ptr)
    ds_day = dt.r_s("dat_Stamp.ds_Days")
    ds_min = dt.r_s("dat_Stamp.ds_Minute")
    ds_tick = dt.r_s("dat_Stamp.ds_Tick")
    format = dt.r_s("dat_Format")
    flags = dt.r_s("dat_Flags")
    str_day_ptr = dt.r_s("dat_StrDay")
    str_date_ptr = dt.r_s("dat_StrDate")
    str_time_ptr = dt.r_s("dat_StrTime")
    at = AmiTime(ds_day, ds_min, ds_tick)
    st = at.to_sys_time()
    log_dos.info("DateToStr: ptr=%06x format=%x flags=%x day_ptr=%06x date_ptr=%06x time_ptr=%06x %s => sys_time=%d", \
      dt_ptr, format, flags, str_day_ptr, str_date_ptr, str_time_ptr, at, st)
    t = time.gmtime(st)
    day_str = time.strftime("%A", t)
    date_str = time.strftime("%d-%m-%y", t)
    time_str = time.strftime("%H:%M:%S", t)
    log_dos.info("DateToStr: result day='%s' date='%s' time='%s'", day_str, date_str, time_str)
    if str_day_ptr != 0:
      ctx.mem.access.w_cstr(str_day_ptr, day_str)
    if str_date_ptr != 0:
      ctx.mem.access.w_cstr(str_date_ptr, date_str)
    if str_time_ptr != 0:
      ctx.mem.access.w_cstr(str_time_ptr, time_str)
    return self.DOSTRUE

  def SetFileDate(self, ctx):
    ds_ptr   = ctx.cpu.r_reg(REG_D2)
    ds       = AccessStruct(ctx.mem,DateStampDef,struct_addr=ds_ptr)
    name_ptr = ctx.cpu.r_reg(REG_D1)
    name     = ctx.mem.access.r_cstr(name_ptr)
    ticks    = ds.r_s("ds_Tick")
    minutes  = ds.r_s("ds_Minute")
    days     = ds.r_s("ds_Days")
    seconds  = ami_to_sys_time(AmiTime(days,minutes,ticks))
    log_dos.info("SetFileDate: file=%s date=%d" % (name,seconds))
    sys_path = self.path_mgr.ami_to_sys_path(self.get_current_dir(),name,searchMulti=True)
    if sys_path == None:
      log_file.info("file not found: '%s' -> '%s'" % (ami_path, sys_path))
      self.setioerr(ctx,ERROR_OBJECT_NOT_FOUND)
      return self.DOSFALSE
    else:
      os.utime(sys_path,(seconds,seconds))
      return self.DOSTRUE

  def SetComment(self, ctx):
    # the typical unixoid file system does not implement this
    log_dos.warn("SetComment: not implemented")
    return self.DOSTRUE

  def GetProgramName(self, ctx):
    buf_ptr = ctx.cpu.r_reg(REG_D1)
    max_len = ctx.cpu.r_reg(REG_D2)
    prog_name = ctx.process.get_program_name()
    n = len(prog_name)
    # return error if name is too long, but copy buffer size
    if n > max_len - 1:
      self.setioerr(ctx,ERROR_LINE_TOOL_LONG)
      ret = self.DOSFALSE
      prog_name = prog_name[0:max_len]
    else:
      ret = self.DOSTRUE
    ctx.mem.access.w_cstr(buf_ptr, prog_name)
    log_dos.info("GetProgramName() -> '%s' (%d)" % (prog_name, max_len))
    return ret

  # ----- Variables -----

  def find_var(self, ctx, name, flags):
    if (name.lower(),flags & 0xff) in self.local_vars:
      return self.local_vars[(name.lower(),flags & 0xff)]
    else:
      return None

  def create_var(self, ctx, name, flags):
    varlist   = ctx.process.get_local_vars()
    node_addr = self._alloc_mem("ShellVar(%s)" % name,LocalVarDef.get_size() + len(name) + 1)
    name_addr = node_addr + LocalVarDef.get_size()
    node      = ctx.alloc.map_struct("ShellVar(%s) % name", node_addr, LocalVarDef)
    ctx.mem.access.w_cstr(name_addr,name)
    node.access.w_s("lv_Node.ln_Name",name_addr)
    node.access.w_s("lv_Node.ln_Type",flags & 0xff)
    node.access.w_s("lv_Value",0)
    head_addr = varlist.access.r_s("mlh_Head")
    head      = AccessStruct(ctx.mem, NodeDef, head_addr)
    head.w_s("ln_Pred",node_addr)
    varlist.access.w_s("mlh_Head",node_addr)
    node.access.w_s("lv_Node.ln_Succ",head_addr)
    node.access.w_s("lv_Node.ln_Pred",varlist.access.s_get_addr("mlh_Head"))
    self.local_vars[(name.lower(),flags & 0xff)] = node.access
    return node.access

  def set_var(self,ctx,node,buff_ptr,size,value,flags):
    if node.r_s("lv_Value") != 0:
      self._free_mem(node.r_s("lv_Value"))
      node.w_s("lv_Value",0)
    buf_addr = self._alloc_mem("ShellVarBuffer",size)
    node.w_s("lv_Value",buf_addr)
    node.w_s("lv_Len",size)
    if flags & self.GVF_BINARY_VAR:
      ctx.mem.raw_mem.copy_block(buff_ptr,buf_addr,size)
    else:
      ctx.mem.access.w_cstr(buf_addr,value)

  def delete_var(self,ctx,node):
    buf_addr  = node.r_s("lv_Value")
    buf_len   = node.r_s("lv_Len")
    name_addr = node.r_s("lv_Node.ln_Name")
    name      = ctx.mem.access.r_cstr(name_addr)
    if buf_addr != 0:
      self._free_mem(buf_addr)
    node.w_s("lv_Value",0)
    succ = node.r_s("lv_Node.ln_Succ")
    pred = node.r_s("lv_Node.ln_Pred")
    AccessStruct(ctx.mem, NodeDef, pred).w_s("ln_Succ", succ)
    AccessStruct(ctx.mem, NodeDef, succ).w_s("ln_Pred", pred)
    self._free_mem(node.struct_addr)
    for k in self.local_vars.keys():
      if self.local_vars[k] == node:
        del self.local_vars[k]

  def GetVar(self, ctx):
    name_ptr = ctx.cpu.r_reg(REG_D1)
    buff_ptr = ctx.cpu.r_reg(REG_D2)
    size     = ctx.cpu.r_reg(REG_D3)
    flags    = ctx.cpu.r_reg(REG_D4)
    if size == 0:
      self.setioerr(ctx, ERROR_BAD_NUMBER)
      return self.DOSFALSE
    name = ctx.mem.access.r_cstr(name_ptr)
    if not flags & self.GVF_GLOBAL_ONLY:
      node = self.find_var(ctx,name,flags & 0xff)
      if node != None:
        nodelen = node.r_s("lv_Len")
        if flags & self.GVF_BINARY_VAR:
          ctx.mem.raw_mem.copy_block(node.r_s("lv_Value"),buff_ptr,min(nodelen,size))
          log_dos.info('GetVar("%s", 0x%x) -> %0x06x' % (name, flags, node.r_s("lv_Value")))
          self.setioerr(ctx,nodelen)
          return min(nodelen,size)
        else:
          value = ctx.mem.access.r_cstr(node.r_s("lv_Value"))
          ctx.mem.access.w_cstr(buff_ptr,value[:size-1])
          log_dos.info('GetVar("%s", 0x%x) -> %s' % (name, flags, value))
          self.setioerr(ctx,len(value))
          return min(nodelen-1,size-1)
    return self.DOSFALSE

  def FindVar(self, ctx):
    name_ptr  = ctx.cpu.r_reg(REG_D1)
    vtype     = ctx.cpu.r_reg(REG_D2)
    name      = ctx.mem.access.r_cstr(name_ptr)
    node      = self.find_var(ctx,name,vtype)
    if node == None:
      self.setioerr(ctx,ERROR_OBJECT_NOT_FOUND)
      log_dos.info('FindVar("%s", 0x%x) -> NULL' % (name, vtype))
      return 0
    else:
      log_dos.info('FindVar("%s", 0x%x) -> %06lx' % (name, vtype, node.struct_addr))
      return node.struct_addr

  def SetVar(self, ctx):
    name_ptr  = ctx.cpu.r_reg(REG_D1)
    buff_ptr  = ctx.cpu.r_reg(REG_D2)
    size      = ctx.cpu.r_reg(REG_D3)
    flags     = ctx.cpu.r_reg(REG_D4)
    name      = ctx.mem.access.r_cstr(name_ptr)
    if buff_ptr == 0:
      if not flags & self.GVF_GLOBAL_ONLY:
        node = self.find_var(ctx,name,vtype)
        if node != None:
          self.delete_var(ctx,node)
        return self.DOSTRUE
    else:
      if flags & self.GVF_BINARY_VAR:
        value = None
        log_dos.info('SetVar("%s") to %0x6x' % (name, buff_ptr))
      else:
        value = ctx.mem.access.r_cstr(buff_ptr)
        log_dos.info('SetVar("%s") to %s' % (name, value))
        size  = len(value) + 1
      if not flags & self.GVF_GLOBAL_ONLY:
        node = self.find_var(ctx,name,flags)
        if node == None and buff_ptr != 0:
          node = self.create_var(ctx,name,flags)
        if node != None:
          self.set_var(ctx,node,buff_ptr,size,value,flags)
        return self.DOSTRUE
    return 0

  def DeleteVar(self, ctx):
    name_ptr  = ctx.cpu.r_reg(REG_D1)
    flags     = ctx.cpu.r_reg(REG_D4)
    name      = ctx.mem.access.r_cstr(name_ptr)
    if not flags & self.GVF_GLOBAL_ONLY:
      node = self.find_var(ctx,name,flags)
      log_dos.info('DeleteVar("%s")' % name)
      if node != None:
        self.delete_var(ctx,node)
      return self.DOSTRUE

  # ----- Signals ----------------------

  def CheckSignal(self, ctx):
    sigmask = ctx.cpu.r_reg(REG_D1)
    # THOR: Fixme. We really need to get the signal
    # mask from the tty here.
    return 0

  # ----- Resident commands support ----

  def FindSegment(self, ctx):
    name_ptr = ctx.cpu.r_reg(REG_D1)
    needle   = ctx.mem.access.r_cstr(name_ptr)
    start    = ctx.cpu.r_reg(REG_D2)
    system   = ctx.cpu.r_reg(REG_D3)
    if start == 0:
      seg_addr = self.dos_info.access.r_s("di_NetHand")
    else:
      seg_addr = AccessStruct(ctx.mem, SegmentDef, start).r_s("seg_Next")
    log_dos.info("FindSegment(%s)" % needle)
    while seg_addr != 0:
      segment  = AccessStruct(ctx.mem, SegmentDef, seg_addr)
      name_addr= seg_addr + SegmentDef.get_offset_for_name("seg_Name")[0]
      name     = ctx.mem.access.r_bstr(name_addr)
      if name.lower() == needle.lower():
        if (system and segment.r_s("seg_UC") < 0) or (not system and segment.r_s("seg_UC") > 0):
          seg  = segment.r_s("seg_Seg")
          log_dos.info("FindSegment(%s) -> %06x" % (name,seg))
          return seg_addr
      seg_addr = segment.r_s("seg_Next")
    return 0

  def AddSegment(self,ctx):
    name_ptr  = ctx.cpu.r_reg(REG_D1)
    seglist   = ctx.cpu.r_reg(REG_D2) << 2
    system    = ctx.cpu.r_reg(REG_D3)
    name      = ctx.mem.access.r_cstr(name_ptr)
    seg_addr  = self._alloc_mem("Segment",SegmentDef.get_size() + len(name) + 1)
    name_addr = seg_addr + SegmentDef.get_offset_for_name("seg_Name")[0]
    segment   = ctx.alloc.map_struct("Segment", seg_addr, SegmentDef)
    head_addr = self.dos_info.access.r_s("di_NetHand")
    segment.access.w_s("seg_Next",head_addr)
    segment.access.w_s("seg_UC",system)
    segment.access.w_s("seg_Seg",seglist)
    ctx.mem.access.w_bstr(name_addr,name)
    self.dos_info.access.w_s("di_NetHand",seg_addr)
    log_dos.info("AddSegment(%s,%06x) -> %06x" % (name,seglist,seg_addr))
    self.resident.append(seg_addr)
    # Adding a resident command to the registered seglists.
    b_addr = seglist >> 2
    if b_addr not in self.seg_lists:
      self.seg_lists[b_addr] = (None,name)
    return -1

  # ----- File Ops -----

  def Cli(self, ctx):
    cli_addr = ctx.process.get_cli_struct()
    log_dos.info("Cli() -> %06x" % cli_addr)
    return cli_addr

  def Input(self, ctx):
    return ctx.process.this_task.access.r_s("pr_CIS") >> 2

  def Output(self, ctx):
    return ctx.process.this_task.access.r_s("pr_COS") >> 2

  def SelectInput(self, ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)
    fh = self.file_mgr.get_by_b_addr(fh_b_addr,False)
    log_dos.info("SelectInput(fh=%s)" % fh)
    cur_in = self.Input(ctx)
    ctx.process.set_input(fh)
    return cur_in

  def SelectOutput(self, ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)
    fh = self.file_mgr.get_by_b_addr(fh_b_addr,True)
    log_dos.info("SelectOutput(fh=%s)" % fh)
    cur_out = self.Output(ctx)
    ctx.process.set_output(fh)
    return cur_out

  def Open(self, ctx):
    name_ptr = ctx.cpu.r_reg(REG_D1)
    name = ctx.mem.access.r_cstr(name_ptr)
    mode = ctx.cpu.r_reg(REG_D2)

    # decode mode
    if mode == 1006:
      mode_name = "new"
      f_mode = "wb+"
    elif mode == 1005:
      mode_name = "old"
      f_mode = "rb+"
    elif mode == 1004:
      mode_name = "r/w"
      f_mode = "rwb+"
    else:
      mode_name = "?"

    fh = self.file_mgr.open(self.get_current_dir(), name, f_mode)
    log_dos.info("Open: name='%s' (%s/%d/%s) -> %s" % (name, mode_name, mode, f_mode, fh))

    if fh == None:
      self.setioerr(ctx,ERROR_OBJECT_NOT_FOUND)
      return 0
    else:
      return fh.b_addr

  def Close(self, ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)
    if fh_b_addr != 0:
      fh = self.file_mgr.get_by_b_addr(fh_b_addr)
      self.file_mgr.close(fh)
      log_dos.info("Close: %s" % fh)
      self.setioerr(ctx,0)
    return self.DOSTRUE

  def Read(self, ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)
    buf_ptr = ctx.cpu.r_reg(REG_D2)
    size = ctx.cpu.r_reg(REG_D3)

    fh = self.file_mgr.get_by_b_addr(fh_b_addr,False)
    data = fh.read(size)
    ctx.mem.access.w_data(buf_ptr, data)
    got = len(data)
    log_dos.info("Read(%s, %06x, %d) -> %d" % (fh, buf_ptr, size, got))
    return got

  def Write(self, ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)
    buf_ptr = ctx.cpu.r_reg(REG_D2)
    size = ctx.cpu.r_reg(REG_D3)

    fh = self.file_mgr.get_by_b_addr(fh_b_addr,True)
    data = ctx.mem.access.r_data(buf_ptr,size)
    fh.write(data)
    got = len(data)
    log_dos.info("Write(%s, %06x, %d) -> %d" % (fh, buf_ptr, size, got))
    return size

  def FWrite(self, ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)
    buf_ptr = ctx.cpu.r_reg(REG_D2)
    size = ctx.cpu.r_reg(REG_D3)
    number = ctx.cpu.r_reg(REG_D4)
    # Actually, this is buffered I/O, not unbuffered IO. For the
    # time being, keep it unbuffered.
    fh = self.file_mgr.get_by_b_addr(fh_b_addr,True)
    data = ctx.mem.access.r_data(buf_ptr,size * number)
    fh.write(data)
    got = len(data) / size
    log_dos.info("FWrite(%s, %06x, %d, %d) -> %d" % (fh, buf_ptr, size, number, got))
    return got

  def FRead(self, ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)
    buf_ptr = ctx.cpu.r_reg(REG_D2)
    size = ctx.cpu.r_reg(REG_D3)
    number = ctx.cpu.r_reg(REG_D4)
    # Again, this is actually buffered I/O and I should really
    # go through all the buffer logic. However, for the time
    # being, keep it unbuffered.
    fh = self.file_mgr.get_by_b_addr(fh_b_addr,True)
    data = fh.read(size * number)
    if data == -1:
      got = 0 # simple error handling
    else:
      got = len(data) / size
      ctx.mem.access.w_data(buf_ptr, data)
    log_dos.info("FRead(%s, %06x, %d, %d) -> %d" % (fh, buf_ptr, size, number, got))
    return got

  def Seek(self, ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)
    pos = ctx.cpu.r_reg(REG_D2)
    mode = ctx.cpu.r_reg(REG_D3)

    fh = self.file_mgr.get_by_b_addr(fh_b_addr)
    if mode == 0xffffffff:
      mode_str = "BEGINNING"
      whence = 0
    elif mode == 0:
      mode_str = "CURRENT"
      whence = 1
      if pos >= 0x80000000:
        pos = pos - 0x100000000
    elif mode == 1:
      mode_str = "END"
      if pos > 0:
        pos = pos - 0x100000000
      whence = 2
    else:
      raise UnsupportedFeatureError("Seek: mode=%d" % mode)

    old_pos = fh.tell()
    fh.seek(pos, whence)
    log_dos.info("Seek(%s, %06x, %s) -> old_pos=%06x" % (fh, pos, mode_str, old_pos))
    return old_pos

  def FGetC(self, ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)
    fh = self.file_mgr.get_by_b_addr(fh_b_addr,False)
    ch = fh.getc()
    if ch == -1:
      log_dos.info("FGetC(%s) -> EOF (%d)" % (fh, ch))
    else:
      log_dos.info("FGetC(%s) -> '%c' (%d)" % (fh, ch, ch))
    return ch

  def FPutC(self, ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)
    val = ctx.cpu.r_reg(REG_D2)
    fh = self.file_mgr.get_by_b_addr(fh_b_addr,True)
    log_dos.info("FPutC(%s, '%c' (%d))" % (fh, val, val))
    fh.write(chr(val))
    return val

  def UnGetC(self, ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)
    val = ctx.cpu.r_reg(REG_D2)
    fh = self.file_mgr.get_by_b_addr(fh_b_addr,False)
    ch = fh.ungetc(val)
    log_dos.info("UnGetC(%s, %d) -> ch=%d (%d)" % (fh, val, ch, ch))
    return ch

  # ----- StdOut -----

  def PutStr(self, ctx):
    str_ptr = ctx.cpu.r_reg(REG_D1)
    str_dat = ctx.mem.access.r_cstr(str_ptr)
    # write to stdout
    fh = ctx.process.get_output()
    ok = fh.write(str_dat)
    log_dos.info("PutStr: '%s'", str_dat)
    return 0 # ok

  def Flush(self, ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)
    fh = self.file_mgr.get_by_b_addr(fh_b_addr,True)
    fh.flush()
    return -1

  def VPrintf(self, ctx):
    format_ptr = ctx.cpu.r_reg(REG_D1)
    argv_ptr = ctx.cpu.r_reg(REG_D2)
    fmt = ctx.mem.access.r_cstr(format_ptr)
    # write on output
    fh = ctx.process.get_output()
    log_dos.info("VPrintf: format='%s' argv=%06x" % (fmt,argv_ptr))
    # now decode printf
    ps = dos.Printf.printf_parse_string(fmt)
    dos.Printf.printf_read_data(ps, ctx.mem.access, argv_ptr)
    log_dos.debug("VPrintf: parsed format: %s",ps)
    result = dos.Printf.printf_generate_output(ps)
    # write result
    fh.write(result)
    return len(result)

  def VFPrintf(self, ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)
    fh = self.file_mgr.get_by_b_addr(fh_b_addr,True)
    format_ptr = ctx.cpu.r_reg(REG_D2)
    argv_ptr = ctx.cpu.r_reg(REG_D3)
    fmt = ctx.mem.access.r_cstr(format_ptr)
    # write on output
    log_dos.info("VFPrintf: format='%s' argv=%06x" % (fmt,argv_ptr))
    # now decode printf
    ps = dos.Printf.printf_parse_string(fmt)
    dos.Printf.printf_read_data(ps, ctx.mem.access, argv_ptr)
    log_dos.debug("VFPrintf: parsed format: %s",ps)
    result = dos.Printf.printf_generate_output(ps)
    # write result
    fh.write(result)
    return len(result)

  def WriteChars(self, ctx):
    fh       = ctx.process.get_output()
    buf_addr = ctx.cpu.r_reg(REG_D1)
    siz      = ctx.cpu.r_reg(REG_D2)
    buf      = ctx.mem.access.r_cstr(buf_addr)[:siz]
    fh.write(buf)
    return len(buf)

  def VFWritef(self, ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)
    fh = self.file_mgr.get_by_b_addr(fh_b_addr,True)
    fmt_ptr = ctx.cpu.r_reg(REG_D2)
    args_ptr = ctx.cpu.r_reg(REG_D3)
    fmt = ctx.mem.access.r_cstr(fmt_ptr)
    log_dos.info("VFWritef: fh=%s format='%s' args_ptr=%06x" % (fh, fmt, args_ptr))
    out = ''
    pos = 0
    state = ''
    while pos < len(fmt):
      ch = fmt[pos].upper()
      pos = pos + 1
      if state[0:1] == 'x':
        n = ord(ch)
        if n >= ord('0') and n <= ord('9'):
          n = n - ord('0')
        elif n >= ord('A') and n <= ord('Z'):
          n = (n - ord('A')) + 10
        else:
          n = 0
        ch = state[1:2]
        if ch == 'T':
          out = out + ("%*s" % (-n, ctx.mem.access.r_cstr(val)))
        elif ch == 'O':
          out = out + ("%*O" % (-n, val))
        elif ch == 'X':
          out = out + ("%*X" % (-n, val))
        elif ch == 'I':
          out = out + ("%*ld" % (-n, ctypes.c_long(val).value))
        elif ch == 'U':
          out = out + ("%*lu" % (-n, ctypes.c_ulong(val).value))
        else:
          out = out + '%' + state[1] + state[0]
        state = ''
      elif state == '%':
        if ch == 'S':
          out = out + ctx.mem.access.r_cstr(val)
          state = ''
        elif ch == 'C':
          out = out + chr(val & 0xff)
          state = ''
        elif ch == 'N':
          out = out + ("%ld" % ctypes.c_long(val).value)
          state = ''
        elif ch == '$':
          state = ''
        elif ch == 'T' or ch == 'O' or ch == 'X' or ch == 'I' or ch == 'U':
          state = 'x' + ch
        else:
          out = out + '%' + ch
          state = ''
      else:
        if ch == '%':
          state = '%'
          val = ctx.mem.access.r32(args_ptr)
          args_ptr = args_ptr + 4
        else:
          out = out + ch
    fh.write(out)
    return len(out)

  # ----- Stdin --------

  def FGets(self,ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)
    bufaddr   = ctx.cpu.r_reg(REG_D2)
    buflen    = ctx.cpu.r_reg(REG_D3)
    fh   = self.file_mgr.get_by_b_addr(fh_b_addr,False)
    line = fh.gets(buflen)
    # Bummer! FIXME: There is currently no way this can communicate an I/O error
    self.setioerr(ctx,0)
    log_dos.info("FGetS(%s,%d) -> '%s'" % (fh, buflen, line))
    ctx.mem.access.w_cstr(bufaddr,line)
    if line == "":
      return 0
    return bufaddr

  # ----- File Ops -----

  def DeleteFile(self, ctx):
    name_ptr = ctx.cpu.r_reg(REG_D1)
    name = ctx.mem.access.r_cstr(name_ptr)
    self.setioerr(ctx,self.file_mgr.delete(self.get_current_dir(),name))
    log_dos.info("DeleteFile: '%s': err=%s" % (name, self.io_err))
    if self.io_err == NO_ERROR:
      return self.DOSTRUE
    else:
      return self.DOSFALSE

  def Rename(self, ctx):
    old_name_ptr = ctx.cpu.r_reg(REG_D1)
    old_name = ctx.mem.access.r_cstr(old_name_ptr)
    new_name_ptr = ctx.cpu.r_reg(REG_D2)
    new_name = ctx.mem.access.r_cstr(new_name_ptr)
    lock = self.get_current_dir()
    self.setioerr(ctx,self.file_mgr.rename(lock, old_name, new_name))
    log_dos.info("Rename: '%s' -> '%s': err=%s" % (old_name, new_name, self.io_err))
    if self.io_err == NO_ERROR:
      return self.DOSTRUE
    else:
      return self.DOSFALSE

  def SetProtection(self, ctx):
    name_ptr = ctx.cpu.r_reg(REG_D1)
    name = ctx.mem.access.r_cstr(name_ptr)
    mask = ctx.cpu.r_reg(REG_D2)
    lock = self.get_current_dir()
    self.setioerr(ctx,self.file_mgr.set_protection(lock, name, mask))
    log_dos.info("SetProtection: '%s' mask=%04x: err=%s", name, mask, self.io_err)
    if self.io_err == NO_ERROR:
      return self.DOSTRUE
    else:
      return self.DOSFALSE

  def IsInteractive(self, ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)
    fh = self.file_mgr.get_by_b_addr(fh_b_addr,False)
    res = fh.is_interactive()
    log_dos.info("IsInteractive(%s): %s" % (fh, res))
    if res:
      return self.DOSTRUE
    else:
      return self.DOSFALSE

  def IsFileSystem(self, ctx):
    name_ptr = ctx.cpu.r_reg(REG_D1)
    name = ctx.mem.access.r_cstr(name_ptr)
    log_dos.info("IsFileSystem('%s'):" % name)
    lock = self.get_current_dir()
    res  = self.file_mgr.is_file_system(lock,name)
    log_dos.info("IsFileSystem('%s'): %s" % (name, res))
    if res:
      return self.DOSTRUE
    else:
      return self.DOSFALSE

  # ----- Locks -----

  def Lock(self, ctx):
    name_ptr = ctx.cpu.r_reg(REG_D1)
    name = ctx.mem.access.r_cstr(name_ptr)
    mode = ctx.cpu.r_reg(REG_D2)

    if mode == 0xffffffff:
      lock_exclusive = True
    elif mode == 0xfffffffe:
      lock_exclusive = False
    else:
      raise UnsupportedFeatureError("Lock: mode=%x" % mode)

    lock = self.lock_mgr.create_lock(self.get_current_dir(), name, lock_exclusive)
    log_dos.info("Lock: (%s) '%s' exc=%s -> %s" % (self.get_current_dir(), name, lock_exclusive, lock))
    if lock == None:
      self.setioerr(ctx,ERROR_OBJECT_NOT_FOUND)
      return 0
    else:
      return lock.b_addr

  def UnLock(self, ctx):
    lock_b_addr = ctx.cpu.r_reg(REG_D1)
    if lock_b_addr == 0:
      log_dos.info("UnLock: NULL")
    else:
      lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
      log_dos.info("UnLock: %s" % (lock))
      self.lock_mgr.release_lock(lock)

  def DupLock(self, ctx):
    lock_b_addr = ctx.cpu.r_reg(REG_D1)
    lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
    dup_lock = self.lock_mgr.dup_lock(lock)
    log_dos.info("DupLock: %s -> %s",lock, dup_lock)
    self.setioerr(ctx,NO_ERROR)
    return dup_lock.b_addr

  def SameLock(self, ctx):
    lock1_b_addr = ctx.cpu.r_reg(REG_D1)
    lock2_b_addr = ctx.cpu.r_reg(REG_D1)
    lock1 = self.lock_mgr.get_by_b_addr(lock1_b_addr)
    lock2 = self.lock_mgr.get_by_b_addr(lock2_b_addr)
    if lock1 == lock2:
      return self.DOSTRUE
    if lock1 != None and lock2 != None:
      return lock1.key == lock2.key
    return self.DOSFALSE

  def Examine(self, ctx):
    lock_b_addr = ctx.cpu.r_reg(REG_D1)
    fib_ptr = ctx.cpu.r_reg(REG_D2)
    lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
    fib = AccessStruct(ctx.mem,FileInfoBlockDef,struct_addr=fib_ptr)
    err = lock.examine_lock(fib)
    name_addr = fib.s_get_addr('fib_FileName')
    name      = fib.r_cstr(name_addr)
    log_dos.info("Examine: %s fib=%06x(%s) -> %s" % (lock, fib_ptr, name, err))
    self.setioerr(ctx,err)
    if err == NO_ERROR:
      return self.DOSTRUE
    else:
      return self.DOSFALSE

  def Info(self, ctx):
    lock_b_addr = ctx.cpu.r_reg(REG_D1)
    info_ptr = ctx.cpu.r_reg(REG_D2)
    lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
    info = AccessStruct(ctx.mem,InfoDataDef,struct_addr=info_ptr)
    vol  = lock.find_volume_node(self.dos_list)
    if vol != None:
      info.w_s('id_NumSoftErrors',0)
      info.w_s('id_UnitNumber',0) #not that we really care...
      info.w_s('id_DiskState',0)  #disk is not write protected
      info.w_s('id_NumBlocks',0x7fffffff) #a really really big disk....
      info.w_s('id_NumBlocksUsed',0x0fffffff) #some...
      info.w_s('id_BytesPerBlock',512) #let's take regular FFS blocks
      info.w_s('id_DiskType',0x444F5303) #international FFS
      info.w_s('id_VolumeNode',vol)
      info.w_s('id_InUse',0)
      log_dos.info("Info: %s info=%06x -> true" % (lock, info_ptr))
      return self.DOSTRUE
    else:
      log_dos.info("Info: %s info=%06x -> false" % (lock, info_ptr))
      return self.DOSFALSE

  def ExNext(self, ctx):
    lock_b_addr = ctx.cpu.r_reg(REG_D1)
    fib_ptr = ctx.cpu.r_reg(REG_D2)
    lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
    fib = AccessStruct(ctx.mem,FileInfoBlockDef,struct_addr=fib_ptr)
    err = lock.examine_next(fib)
    name_addr = fib.s_get_addr('fib_FileName')
    name      = fib.r_cstr(name_addr)
    log_dos.info("ExNext: %s fib=%06x (%s) -> %s" % (lock, fib_ptr, name, err))
    self.setioerr(ctx,err)
    if err == NO_ERROR:
      return self.DOSTRUE
    else:
      return self.DOSFALSE

  def ParentDir(self, ctx):
    lock_b_addr = ctx.cpu.r_reg(REG_D1)
    lock        = self.lock_mgr.get_by_b_addr(lock_b_addr)
    parent_lock = self.lock_mgr.create_parent_lock(lock)
    log_dos.info("ParentDir: %s -> %s" % (lock, parent_lock))
    if parent_lock != None:
      return parent_lock.b_addr
    else:
      return 0

  def CurrentDir(self, ctx):
    lock_b_addr = ctx.cpu.r_reg(REG_D1)
    old_lock    = self.get_current_dir()
    new_lock    = self.lock_mgr.get_by_b_addr(lock_b_addr)
    log_dos.info("CurrentDir(b@%x): %s -> %s" % (lock_b_addr, old_lock, new_lock))
    if new_lock == None:
      ctx.process.set_current_dir(0)
    else:
      ctx.process.set_current_dir(new_lock.b_addr << 2)
    if old_lock == None:
      return 0
    else:
      return old_lock.b_addr

  def NameFromLock(self, ctx):
    lock_b_addr = ctx.cpu.r_reg(REG_D1)
    buf = ctx.cpu.r_reg(REG_D2)
    buf_len = ctx.cpu.r_reg(REG_D3)
    if lock_b_addr == 0:
      name = "SYS:"
      lock = None
    else:
      lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
      name = lock.ami_path
    log_dos.info("NameFromLock(%x,%d): %s -> %s", buf, buf_len, lock, name)
    if len(name) >= buf_len:
      self.setioerr(ctx,ERROR_LINE_TOO_LONG)
      return self.DOSFALSE
    else:
      ctx.mem.access.w_cstr(buf, name)
      return self.DOSTRUE

  def CreateDir(self, ctx):
    name_ptr = ctx.cpu.r_reg(REG_D1)
    name = ctx.mem.access.r_cstr(name_ptr)
    lock = self.get_current_dir()
    err  = self.file_mgr.create_dir(lock,name)
    if err != NO_ERROR:
      self.setioerr(ctx,err)
      return 0
    else:
      lock = self.lock_mgr.create_lock(lock, name, True)
      log_dos.info("CreateDir: '%s' -> %s" % (name, lock))
    if lock == None:
      self.setioerr(ctx,ERROR_OBJECT_NOT_FOUND)
      return 0
    else:
      return lock.b_addr

  # ----- DevProc -----

  def GetDeviceProc(self, ctx):
    name_ptr = ctx.cpu.r_reg(REG_D1)
    last_devproc = ctx.cpu.r_reg(REG_D2)
    name = ctx.mem.access.r_cstr(name_ptr)
    uname = name.upper()
    #
    # First filter out "real" devices.
    if uname.startswith('NIL:') or uname == '*' or uname.startswith('CONSOLE:'):
      log_dos.info("GetDeviceProc: %s -> None" % name)
      vol_lock = 0
    else:
      # Otherwise, create a lock for the path
      abs_name = ctx.path_mgr.ami_abs_path(self.get_current_dir(),name)
      volume   = ctx.path_mgr.ami_volume_of_path(abs_name)
      vol_lock = self.lock_mgr.create_lock(None,volume+":", False)
    fs_port  = self.file_mgr.get_fs_handler_port()
    addr     = self._alloc_mem("DevProc:%s" % name, DevProcDef.get_size())
    log_dos.info("GetDeviceProc: name='%s' devproc=%06x -> volume=%s devproc=%06x lock=%06x",
                 name, last_devproc, volume, addr, vol_lock.b_addr)
    devproc = AccessStruct(self.ctx.mem,DevProcDef,struct_addr=addr)
    devproc.w_s('dvp_Port', fs_port)
    if vol_lock == None:
      devproc.w_s('dvp_Lock', 0)
    else:
      devproc.w_s('dvp_Lock', vol_lock.b_addr << 2) #THOR: Compensate for BADDR adjustment.
    self.setioerr(ctx,NO_ERROR)
    return addr

  def FreeDeviceProc(self, ctx):
    addr     = ctx.cpu.r_reg(REG_D1)
    devproc  = AccessStruct(self.ctx.mem,DevProcDef,struct_addr=addr)
    vol_lock = devproc.r_s('dvp_Lock')
    if vol_lock != 0:
      lock = self.lock_mgr.get_by_b_addr(vol_lock >> 2)
      self.lock_mgr.release_lock(lock)
    self._free_mem(addr)
    log_dos.info("FreeDeviceProc: devproc=%06x", addr)

  # ----- Matcher -----

  def MatchFirst(self, ctx):
    pat_ptr = ctx.cpu.r_reg(REG_D1)
    pat     = ctx.mem.access.r_cstr(pat_ptr)
    anchor_ptr = ctx.cpu.r_reg(REG_D2)
    anchor = AccessStruct(self.ctx.mem,AnchorPathDef,struct_addr=anchor_ptr)

    # create MatchFirstNext instance
    mfn = MatchFirstNext(ctx.path_mgr, self.lock_mgr, self.get_current_dir(), pat, anchor)
    log_dos.info("MatchFirst: pat='%s' anchor=%06x strlen=%d flags=%02x-> ok=%s" \
      % (pat, anchor_ptr, mfn.str_len, mfn.flags, mfn.ok))
    if not mfn.ok:
      self.matches[anchor_ptr] = mfn
      self.setioerr(ctx,ERROR_BAD_TEMPLATE)
      return self.io_err
    log_dos.debug("MatchFirst: %s" % mfn.matcher)

    # try first match
    err = mfn.first(ctx)
    self.setioerr(ctx,err)
    if self.io_err == NO_ERROR:
      log_dos.info("MatchFirst: found name='%s' path='%s' -> parent lock %s, io_err=%d", mfn.name, mfn.path, mfn.dir_lock, self.io_err)
      self.matches[anchor_ptr] = mfn
    # no entry found or error
    elif self.io_err == ERROR_OBJECT_NOT_FOUND:
      log_dos.info("MatchFirst: none found")
      self.matches[anchor_ptr] = mfn
    else:
      #Dos also creates a matcher on failure...
      self.matches[anchor_ptr] = mfn
      log_dos.info("MatchFirst: error: %d", self.io_err)
    return self.io_err

  def MatchNext(self, ctx):
    anchor_ptr = ctx.cpu.r_reg(REG_D1)
    log_dos.info("MatchNext: anchor=%06x" % (anchor_ptr))
    # retrieve match
    if not self.matches.has_key(anchor_ptr):
      raise VamosInternalError("MatchNext: No matcher found for %06x" % anchor_ptr)
    mfn = self.matches[anchor_ptr]
    # has matches?
    if mfn != None:
      self.setioerr(ctx,mfn.next(ctx))
      if self.io_err == NO_ERROR:
        log_dos.info("MatchNext: found name='%s' path=%s -> parent lock %s, io_err=%d", mfn.name, mfn.path, mfn.dir_lock, self.io_err)
      elif self.io_err == ERROR_NO_MORE_ENTRIES:
        log_dos.info("MatchNext: no more entries!")
      else:
        log_dos.info("MatchNext: error: %d", self.io_err)
      return self.io_err

  def MatchEnd(self, ctx):
    anchor_ptr = ctx.cpu.r_reg(REG_D1)
    log_dos.info("MatchEnd: anchor=%06x " % (anchor_ptr))
    # retrieve match
    if not self.matches.has_key(anchor_ptr):
      raise VamosInternalError("MatchEnd: No matcher found for %06x" % anchor_ptr)
    mfn = self.matches[anchor_ptr]
    del self.matches[anchor_ptr]
    if mfn != None:
      mfn.end(ctx)

  # ----- Pattern Parsing and Matching -----

  def ParsePattern(self, ctx, ignore_case=False):
    src_ptr = ctx.cpu.r_reg(REG_D1)
    dst_ptr = ctx.cpu.r_reg(REG_D2)
    dst_len = ctx.cpu.r_reg(REG_D3)
    src = ctx.mem.access.r_cstr(src_ptr)
    pat = pattern_parse(src, ignore_case=ignore_case)
    log_dos.info("ParsePattern: src=%s ignore_case=%s -> pat=%s",src, ignore_case, pat)
    if pat == None:
      self.setioerr(ctx,ERROR_BAD_TEMPLATE)
      return -1
    else:
      self.setioerr(ctx,NO_ERROR)
      pat_str = pat.pat_str
      if len(pat_str) >= dst_len:
        return -1
      else:
        ctx.mem.access.w_cstr(dst_ptr, pat_str)
        if pat.has_wildcard:
          return 1
        else:
          return 0

  def ParsePatternNoCase(self, ctx):
    return self.ParsePattern(ctx, ignore_case=True)

  def MatchPattern(self, ctx, ignore_case=False):
    pat_ptr = ctx.cpu.r_reg(REG_D1)
    txt_ptr = ctx.cpu.r_reg(REG_D2)
    pat = ctx.mem.access.r_cstr(pat_ptr)
    txt = ctx.mem.access.r_cstr(txt_ptr)
    pattern = Pattern(None,pat,ignore_case,True)
    match   = pattern_match(pattern, txt, ignore_case)
    log_dos.info("MatchPattern: pat=%s txt=%s ignore_case=%s -> match=%s", pat, txt, ignore_case, match)
    if match:
      return -1
    else:
      return 0

  def MatchPatternNoCase(self, ctx):
    return self.MatchPattern(ctx, ignore_case=True)

  # ----- Args -----

  def FindArg(self, ctx):
    template_ptr = ctx.cpu.r_reg(REG_D1)
    keyword_ptr  = ctx.cpu.r_reg(REG_D2)
    template     = ctx.mem.access.r_cstr(template_ptr)
    keyword      = ctx.mem.access.r_cstr(keyword_ptr)
    args         = Args()
    args.parse_template(template)
    pos          = args.find_arg(keyword)
    log_dos.info("FindArgs: template=%s keyword=%s -> %d" % (template,keyword,pos))
    return pos

  def ReadArgs(self, ctx):
    template_ptr = ctx.cpu.r_reg(REG_D1)
    template     = ctx.mem.access.r_cstr(template_ptr)
    array_ptr    = ctx.cpu.r_reg(REG_D2)
    rdargs_ptr   = ctx.cpu.r_reg(REG_D3)

    # get args from process, unless we're running a native
    # shell. The shell leaves the arguments in the buffer
    # of the input file handle.
    args = Args()
    if ctx.process.bin_args is not None:
      bin_args = ctx.process.bin_args
    else:
      raw_args = ctx.process.get_input().getbuf()
      if raw_args == "?\n":
        ctx.process.get_output().write(template+": ")
        ctx.process.get_input().setbuf("")
        raw_args = ctx.process.get_input().gets(512)
      bin_args = args.split(raw_args)
    log_dos.info("ReadArgs: args=%s template='%s' array_ptr=%06x rdargs_ptr=%06x" % (bin_args, template, array_ptr, rdargs_ptr))
    # try to parse argument string
    args.parse_template(template)
    args.prepare_input(ctx.mem.access,array_ptr)
    ok = args.parse_string(bin_args)
    if not ok:
      self.setioerr(ctx,args.error)
      log_dos.info("ReadArgs: not matched -> io_err=%d/%s",self.io_err, dos_error_strings[self.io_err])
      return 0
    log_dos.debug("matched template: %s",args.get_result())
    # calc size of result
    size = args.calc_result_size()
    log_dos.debug("longs=%d chars=%d size=%d" % (args.num_longs,args.num_chars,size))
    # alloc result mem (extra longs and cstrs)
    if size > 0:
      addr = self._alloc_mem("ReadArgs(@%06x)" % self.get_callee_pc(ctx),size)
    else:
      addr = 0
    # fill result array and memory
    resarray = args.generate_result(ctx.mem.access,addr,array_ptr)
    # alloc RD_Args
    if rdargs_ptr == 0:
      rdargs = ctx.alloc.alloc_struct("RDArgs", RDArgsDef)
      own = True
    else:
      rdargs = ctx.alloc.map_struct("RDArgs", rdargs_ptr, RDArgsDef)
      own = False
    rdargs.access.w_s('RDA_Buffer',addr)
    rdargs.access.w_s('RDA_BufSiz',size)
    # store rdargs
    self.rdargs[rdargs.addr] = (rdargs, own)
    # result
    self.setioerr(ctx,NO_ERROR)
    log_dos.info("ReadArgs: matched! result_mem=%06x rdargs=%s", addr, resarray)
    return rdargs.addr

  def FreeArgs(self, ctx):
    rdargs_ptr = ctx.cpu.r_reg(REG_D1)
    log_dos.info("FreeArgs: %06x" % rdargs_ptr)
    # find rdargs
    if not self.rdargs.has_key(rdargs_ptr):
      raise VamosInternalError("Can't find RDArgs: %06x" % rdargs_ptr)
    rdargs, own = self.rdargs[rdargs_ptr]
    del self.rdargs[rdargs_ptr]
    # clean up rdargs
    addr = rdargs.access.r_s('RDA_Buffer')
    if addr != 0:
      self._free_mem(addr)
    # free our memory
    if own:
      self.alloc.free_struct(rdargs)

  def cs_get(self, ctx):
    if self.cs_input:
      ch = self.cs_input.getc()
    else:
      if self.cs_curchr < self.cs_length:
        ch = ctx.mem.access.r8(self.cs_buffer + self.cs_curchr)
        self.cs_curchr = self.cs_curchr + 1
      else:
        ch = -1
    return ch

  def cs_unget(self, ctx):
    if self.cs_input:
      self.cs_input.ungetc(-1)
    else:
      self.cs_curchr = self.cs_curchr - 1

  def ReadItem(self, ctx):
    buff_ptr = ctx.cpu.r_reg(REG_D1)
    maxchars = ctx.cpu.r_reg(REG_D2)
    csource_ptr = ctx.cpu.r_reg(REG_D3)
    log_dos.info("ReadItem: buff_ptr=%06x maxchars=%d csource_ptr=%06x" % (buff_ptr, maxchars, csource_ptr))
    if (csource_ptr):
      csource = ctx.alloc.map_struct("CSource", csource_ptr, CSourceDef)
      self.cs_input = None
      self.cs_buffer = csource.access.r_s('CS_Buffer')
      self.cs_length = csource.access.r_s('CS_Length')
      self.cs_curchr = csource.access.r_s('CS_CurChr')
    else:
      self.cs_input = ctx.process.get_input()

    if buff_ptr == 0:
        return 0 # ITEM_NOTHING

    # Well Known Bug: buff[0] = 0, even if maxchars == 0
    ctx.mem.access.w8(buff_ptr, 0)
    res = self._readItem(ctx,buff_ptr,maxchars)
    # Write back the updated csource ptr if we have one
    if (csource_ptr):
      csource.access.w_s('CS_CurChr',self.cs_curchr)
    result = ctx.mem.access.r_cstr(buff_ptr)
    return res

  def _readItem(self, ctx, buff_ptr, maxchars):
    # Skip leading whitespace
    while True:
      ch = self.cs_get(ctx)
      if ch != ord(" ") and ch != ord("\t"):
        break

    if ch == 0 or ch == ord("\n") or ch < 0 or ch == ord(";"):
      if ch >= 0:
        self.cs_unget(ctx)
      return 0 # ITEM_NOTHING

    if ch == ord("="):
      return -2 # ITEM_EQUAL

    if ch == ord("\""):
      while True:
        if maxchars <= 0:
          ctx.mem.access.w8(buff_ptr - 1, 0)
          return 0 # ITEM_NOTHING
        maxchars = maxchars - 1
        ch = self.cs_get(ctx)
        if ch == ord("*"):
          ch = self.cs_get(ctx)
          if ch == 0 or ch == ord("\n") or ch < 0:
            self.cs_unget(ctx)
            ctx.mem.access.w8(buff_ptr, 0)
            return -1 # ITEM_ERROR
          elif ch == ord("n") or ch == ord("N"):
            ch = ord("\n")
          elif ch == ord("e") or ch == ord("E"):
            ch = 0x1b
        elif ch == 0 or ch == ord("\n") or ch < 0:
          self.cs_ungetc(ctx)
          ctx.mem.access.w8(buff_ptr, 0)
          return -1 # ITEM_ERROR
        elif ch == ord("\""):
          ctx.mem.access.w8(buff_ptr, 0)
          return 2 # ITEM_QUOTED
        ctx.mem.access.w8(buff_ptr, ch)
        buff_ptr = buff_ptr + 1
      pass
    else:
      if maxchars <= 0:
        ctx.mem.access.w8(buff_ptr - 1, 0)
        return -1 # ITEM_ERROR
      maxchars = maxchars - 1
      ctx.mem.access.w8(buff_ptr, ch)
      buff_ptr = buff_ptr + 1
      while True:
        if maxchars <= 0:
          ctx.mem.access.w8(buff_ptr - 1, 0)
          return -1 # ITEM_ERROR
        maxchar = maxchars - 1
        ch = self.cs_get(ctx)
        if ch == 0 or ch == ord("\n") or ch == ord(" ") or ch == ord("\t") or ch == ord("=") or ch < 0:
          # Know Bug: Don't UNGET for a space or equals sign
          if ch != ord("=") and ch != ord(" ") and ch != ord("\t"):
            self.cs_unget(ctx)
          ctx.mem.access.w8(buff_ptr, 0)
          return 1 # ITEM_UNQUOTED
        ctx.mem.access.w8(buff_ptr, ch)
        buff_ptr = buff_ptr + 1

  # ----- System/Execute -----

  def SystemTagList(self, ctx):
    cmd_ptr = ctx.cpu.r_reg(REG_D1)
    tagitem_ptr = ctx.cpu.r_reg(REG_D2)
    cmd = ctx.mem.access.r_cstr(cmd_ptr)
    tag_list = taglist_parse_tagitem_ptr(ctx.mem, tagitem_ptr, DosTags)
    log_dos.info("SystemTagList: cmd='%s' tags=%s", cmd, tag_list)
    # cmd is at this point a full string of commands to execute.
    # If we're running from the Amiga shell, forward this to the shell
    # anyhow.
    if ctx.process.is_native_shell():
      cli_addr = ctx.process.get_cli_struct()
      cli      = AccessStruct(ctx.mem,CLIDef,struct_addr=cli_addr)
      new_input = self.file_mgr.open(None,"NIL:","r")
      if new_input == None:
        log_dos.warn("SystemTagList: can't create new input file handle for SystemTagList('%s')", cmd)
        return 0xffffffff
      #Push-back the commands into the input buffer.
      new_input.setbuf(cmd)
      new_stdin = self.file_mgr.open(None,"*","rw")
      outtag    = tag_list.find_tag('SYS_Output')
      # print "setting new input to %s" % new_input
      # and install this as current input. The shell will read from that
      # instead until it hits the EOF
      input_fhsi  = cli.r_s("cli_StandardInput")
      input_fhci  = cli.r_s("cli_CurrentInput")
      if outtag != None and outtag.data != 0:
        output_fhci = cli.r_s("cli_StandardOutput")
        cli.w_s("cli_StandardOutput",outtag.data << 2)
      else:
        output_fhci = None
      cli.w_s("cli_CurrentInput",new_input.mem.addr)
      cli.w_s("cli_StandardInput",new_stdin.mem.addr)
      cli.w_s("cli_Background",self.DOSTRUE)
      # Create the Packet for the background process.
      packet      = self.ctx.process.run_system()
      stacksize   = cli.r_s("cli_DefaultStack") << 2
      current_dir = self.ctx.process.get_current_dir()
      cur_lock    = self.lock_mgr.get_by_b_addr(current_dir >> 2)
      dup_lock    = self.lock_mgr.dup_lock(self.get_current_dir())
      cur_module  = cli.r_s("cli_Module")
      cur_setname = ctx.mem.access.r_bstr(cli.r_s("cli_SetName"))
      cli.w_s("cli_Module",0)
      self.ctx.process.set_current_dir(dup_lock.mem.addr)
      self.cur_dir_lock = dup_lock
      # print "*** Current input is %s" % input_fh
      # trap to clean up sub process resources
      def trap_stop_run_command(ret_code):
        cli.w_s("cli_CurrentInput",input_fhci)
        cli.w_s("cli_StandardInput",input_fhsi)
        cli.w_s("cli_Background",self.DOSFALSE)
        cli.w_s("cli_Module",cur_module)
        if output_fhci != None:
          cli.w_s("cli_StandardOutput",output_fhci)
        # Channels are closed by the dying shell
        ctx.mem.access.w_bstr(cli.r_s("cli_SetName"),cur_setname)
        ctx.process.this_task.access.w_s("pr_CIS",input_fhci)
        #infile = self.file_mgr.get_by_b_addr(input_fhci >> 2,False)
        #infile.setbuf("")
        self.ctx.process.set_current_dir(current_dir)
        self.cur_dir_lock = self.lock_mgr.get_by_b_addr(current_dir >> 2)
        ctx.cpu.w_reg(REG_D0,0)
        self.setioerr(ctx, ret_code)
        log_dos.info("SystemTagList returned: cmd='%s' tags=%s", cmd, tag_list)
        return 0
      # The return code remains in d0 as is
      ctx.run_shell(ctx.process.shell_start,packet,stacksize,trap_stop_run_command)
      return self.DOSTRUE
    else:
      # parse "command line"
      cl = CommandLine()
      if not cl.parse_string(cmd):
        log_dos.info("SystemTagList: error parsing command: '%s'", cmd)
        return 10 # RETURN_ERROR
      args = cl.args
      if len(args) == 0:
        log_dos.info("SystemTagList: error parsing command: '%s'", cmd)
        return 10 # RETURN_ERROR
      bin = args[0]
      args = args[1:]
      # TODO: redirs
      log_dos.info("SystemTagList: bin='%s' args=%s", bin, args)
      # fetch current dir for current process
      cur_proc = ctx.get_current_process()
      cwd_lock = cur_proc.cwd_lock
      cwd = cur_proc.cwd
      # create a process and run it...
      proc = Process(ctx, bin, args, cwd=cwd, cwd_lock=cwd_lock)
      if not proc.ok:
        log_dos.warn("SystemTagList: can't create process for '%s' args=%s", bin, args)
        return self.DOSTRUE
      ctx.start_sub_process(proc)

  def LoadSeg(self, ctx):
    name_ptr = ctx.cpu.r_reg(REG_D1)
    name     = ctx.mem.access.r_cstr(name_ptr)
    lock     = self.get_current_dir()
    seg_list = self.ctx.seg_loader.load_seg(lock,name,False,True)
    if seg_list == None:
      log_dos.warn("LoadSeg: '%s' -> not found!" % (name))
      return 0
    else:
      log_dos.info("LoadSeg: '%s' -> %s" % (name, seg_list))
      b_addr = seg_list.b_addr
      self.seg_lists[b_addr] = (seg_list,name)
      return b_addr

  def UnLoadSeg(self, ctx):
    b_addr = ctx.cpu.r_reg(REG_D1)
    if b_addr != 0:
      if not self.seg_lists.has_key(b_addr):
        raise VamosInternalError("Trying to unload unknown LoadSeg seg_list: b_addr=%06x" % b_addr)
      else:
        seg_list = self.seg_lists[b_addr][0]
        del self.seg_lists[b_addr]
        self.ctx.seg_loader.unload_seg(seg_list,False)
        log_dos.info("UnLoadSeg:  %s" % seg_list)
    else:
      log_dos.info("UnLoadSeg:  NULL")

  def InternalLoadSeg(self, ctx):
    fh_baddr  = ctx.cpu.r_reg(REG_D0)
    table_ptr = ctx.cpu.r_reg(REG_A0)
    func_ptr  = ctx.cpu.r_reg(REG_A1)
    stack_ptr = ctx.cpu.r_reg(REG_A2)
    # FIXME: For now, just fail
    log_dos.warn("InternalLoadSeg: fh=%06x table=%06x funcptr=%06x stack_ptr=%06x -> not implemented!" %
                 (fh_baddr,table_ptr,func_ptr,stack_ptr))
    self.setioerr(ctx, ERROR_OBJECT_WRONG_TYPE)
    return 0

  def RunCommand(self, ctx):
    b_addr   = ctx.cpu.r_reg(REG_D1)
    if not b_addr in self.seg_lists:
      raise VamosInternalError("Trying to run unknown LoadSeg seg_list: b_addr=%06x" % b_addr)
    else:
      name = self.seg_lists[b_addr][1]
    stack    = ctx.cpu.r_reg(REG_D2)
    args     = ctx.cpu.r_reg(REG_D3)
    length   = ctx.cpu.r_reg(REG_D4)
    fh       = ctx.process.get_input()
    cmdline  = ctx.mem.access.r_cstr(args)
    ctx.process.get_input().setbuf(cmdline)
    log_dos.info("RunCommand: seglist=%06x(%s) stack=%d args=%s" % (b_addr, name, stack, cmdline))
    # round up the stack
    stack    = (stack + 3) & -4
    ctx.run_command((b_addr << 2) + 4,args,length,stack)

  # ----- Path Helper -----

  def FilePart(self, ctx):
    addr = ctx.cpu.r_reg(REG_D1)
    path = ctx.mem.access.r_cstr(addr)
    pos  = dos.PathPart.file_part(path)
    if pos < len(path):
      log_dos.info("FilePart: path='%s' -> result='%s'", path, path[pos:])
    else:
      log_dos.info("FilePart: path='%s' -> pos=NULL", path)
    return addr + pos

  def PathPart(self, ctx):
    addr = ctx.cpu.r_reg(REG_D1)
    path = ctx.mem.access.r_cstr(addr)
    pos  = dos.PathPart.path_part(path)
    if pos < len(path):
      log_dos.info("PathPart: path='%s' -> result='%s'", path, path[:pos])
    else:
      log_dos.info("PathPart: path='%s' -> pos=NULL", path)
    return addr + pos

  def AddPart(self, ctx):
    dn_addr = ctx.cpu.r_reg(REG_D1)
    fn_addr = ctx.cpu.r_reg(REG_D2)
    size    = ctx.cpu.r_reg(REG_D3)
    dn      = ctx.mem.access.r_cstr(dn_addr)
    fn      = ctx.mem.access.r_cstr(fn_addr)
    np      = dos.PathPart.add_part(dn,fn,size)
    log_dos.info("AddPart: dn='%s' fn='%s' size=%d -> np='%s'", dn, fn, size, np)
    if np != None:
      ctx.mem.access.w_cstr(dn_addr, np)
      return self.DOSTRUE
    else:
      return self.DOSFALSE

  # ----- DosObjects -----

  def AllocDosObject(self, ctx):
    obj_type = ctx.cpu.r_reg(REG_D1)
    tags_ptr = ctx.cpu.r_reg(REG_D2)
    if obj_type == 0: # DOS_FILEHANDLE
      name = "DOS_FILEHANDLE"
      struct_def = FileHandleDef
    elif obj_type == 1: # DOS_EXALLCONTROL
      name = "DOS_EXALLCONTROL"
      struct_def = None
    elif obj_type == 2: # DOS_FIB
      name = "DOS_FIB"
      struct_def = FileInfoBlockDef
    elif obj_type == 3: # DOS_STDPKT
      name = "DOS_STDPKT"
      struct_def = DosPacketDef
    elif obj_type == 4: # DOS_CLI
      name = "DOS_CLI"
      struct_def = CLIDef
    elif obj_type == 5: # DOS_RDARGS
      name = "DOS_RDARGS"
      struct_def = RDArgsDef
    else:
      log_dos.error("AllocDosObject: invalid type=%d", obj_type)
      return 0
    if struct_def is None:
      log_dos.warn("AllocDosObject: unsupported type=%d/%s", obj_type, name)
      return 0
    # allocate struct
    dos_obj = ctx.alloc.alloc_struct(name, struct_def)
    log_dos.info("AllocDosObject: type=%d/%s tags_ptr=%08x -> dos_obj=%s",
      obj_type, name, tags_ptr, dos_obj)
    # store struct
    ptr = dos_obj.addr
    self.dos_objs[ptr] = (dos_obj, obj_type)
    # pre fill struct
    if obj_type == 0:
      dos_obj.access.w_s('fh_Pos',0xffffffff)
      dos_obj.access.w_s('fh_End',0xffffffff)
    elif obj_type == 4:
      raise UnsupportedFeatureError("AllocDosObject: DOS_CLI fill TBD")
    return ptr

  def FreeDosObject(self, ctx):
    obj_type = ctx.cpu.r_reg(REG_D1)
    ptr = ctx.cpu.r_reg(REG_D2)
    # retrieve struct
    if ptr in self.dos_objs:
      entry = self.dos_objs[ptr]
      del self.dos_objs[ptr]
      # check type
      if obj_type != entry[1]:
        log_dos.warn("FreeDosObject: type mismatch %d != %d", obj_type, entry[1])
      # free struct
      ctx.alloc.free_struct(entry[0])
    else:
      log_dos.error("FreeDosObject: type=%d ptr=%08x -> NOT FOUND!", obj_type, ptr)

  # ----- Cli support ---

  def CliInit(self,ctx):
    log_dos.info("CliInit")
    clip_addr = self.Cli(ctx)
    clip      = AccessStruct(ctx.mem,CLIDef,clip_addr)
    clip.w_s("cli_FailLevel",10)
    clip.w_s("cli_DefaultStack", ctx.process.stack_size >> 2) # in longs
    # Typically, the creator of the CLI would also initialize
    # the prompt and command name arguments. Unfortunately,
    # vamos does not necessarily do that, so cover this here.
    prompt_ptr = clip.r_s("cli_Prompt")
    ctx.mem.access.w_bstr(prompt_ptr,"%N.%S> ")
    # Get the current dir and install it.
    setname = clip.r_s("cli_SetName")
    ctx.mem.access.w_bstr(setname,"SYS:")
    # The native CliInit opens the CON window here. Don't do that
    # instead use Input and Output.
    # cli_CurrentInput would also be set to the input handle of
    # the S:Startup-Sequence
    infh  = self.Input(ctx)  << 2
    outfh = self.Output(ctx) << 2
    clip.w_s("cli_StandardInput",infh)
    clip.w_s("cli_CurrentInput",infh)
    clip.w_s("cli_StandardOutput",outfh)
    clip.w_s("cli_CurrentOutput",outfh)
    fh = self.file_mgr.open(self.get_current_dir(), "S:Vamos-Startup", "rb+")
    if fh != None:
      clip.w_s("cli_CurrentInput",fh.mem.addr)
    #
    # Create the path
    cmd_dir_addr = clip.r_s("cli_CommandDir")
    for p in ctx.path_mgr.get_paths():
      if p != "C:" and p != "c:":
        lock = self.lock_mgr.create_lock(None, p, False)
        if lock != None:
          path = ctx.alloc.alloc_struct("Path(%s)" % p,PathDef)
          path.access.w_s("path_Lock",lock.mem.addr)
          path.access.w_s("path_Next",cmd_dir_addr)
          cmd_dir_addr = path.addr
          clip.w_s("cli_CommandDir",cmd_dir_addr)
          self.path.append((path,lock))
        else:
          log_dos.warning("Path %s does not exist, expect problems!", p)
    return 0

  def CliInitRun(self, ctx):
    clip_addr = self.Cli(ctx)
    clip      = AccessStruct(ctx.mem,CLIDef,struct_addr=clip_addr)
    pkt       = ctx.cpu.r_reg(REG_A0)
    log_dos.info("CliInitRun (0x%06x)" % pkt)
    # This would typically initialize the CLI for running a command
    # from the packet. Anyhow, this is already done, so do nothing here
    return 0x80000004 #valid, and a System() call.

  # ----- DosList -------------

  def LockDosList(self, ctx):
    flags = ctx.cpu.r_reg(REG_D1)
    node  = self.dos_list.lock_dos_list(flags)
    return node

  def UnLockDosList(self, ctx):
    flags = ctx.cpu.r_reg(REG_D1)
    self.dos_list.unlock_dos_list(flags)

  def NextDosEntry(self, ctx):
    flags = ctx.cpu.r_reg(REG_D2)
    node  = ctx.cpu.r_reg(REG_D1)
    return self.dos_list.next_dos_entry(flags,node)

  def AssignLock(self, ctx):
    name_ptr  = ctx.cpu.r_reg(REG_D1)
    lockbaddr = ctx.cpu.r_reg(REG_D2)
    name      = ctx.mem.access.r_cstr(name_ptr)
    if lockbaddr == 0:
      log_dos.info("AssignLock (%s -> null)" % name)
      self.dos_list.remove_assign(name)
      return -1
    else:
      lock = self.lock_mgr.get_by_b_addr(lockbaddr)
      log_dos.info("AssignLock (%s -> %s)" % (name,lock))
      if self.dos_list.create_assign(name,lock) != None:
        return -1
      return 0

  # ----- misc --------

  def StrToLong(self, ctx):
    str_addr = ctx.cpu.r_reg(REG_D1)
    val_addr = ctx.cpu.r_reg(REG_D2)
    string   = ctx.mem.access.r_cstr(str_addr)
    match    = re.search("(\+|\-|)[0-9]*",string)
    if len(match.group(0)) > 0:
      ctx.mem.access.w32(val_addr,int(match.group(0)))
      return len(match.group(0))
    else:
      return 0

  def SetCurrentDirName(self,ctx):
    str_addr = ctx.cpu.r_reg(REG_D1)
    string   = ctx.mem.access.r_cstr(str_addr)[:79]
    cli_addr = self.Cli(ctx)
    cli      = AccessStruct(ctx.mem,CLIDef,struct_addr=cli_addr)
    setaddr  = cli.r_s("cli_SetName")
    ctx.mem.access.w_bstr(setaddr,string)
    return self.DOSTRUE

  def SetPrompt(self,ctx):
    str_addr = ctx.cpu.r_reg(REG_D1)
    string   = ctx.mem.access.r_cstr(str_addr)[:59]
    cli_addr = self.Cli(ctx)
    cli      = AccessStruct(ctx.mem,CLIDef,struct_addr=cli_addr)
    setaddr  = cli.r_s("cli_Prompt")
    ctx.mem.access.w_bstr(setaddr,string)
    return self.DOSTRUE

  def DosGetString(self,ctx):
    errno = ctx.cpu.r_reg(REG_D1)
    if errno >= 0x80000000:
      errno = errno - 0x100000000
    if errno in dos_error_strings:
      if errno in self.errstrings:
        return self.errstrings[errno]
      self.errstrings[errno] = self._alloc_mem("Error %d" % errno,len(dos_error_strings[errno]) + 1)
      ctx.mem.access.w_cstr(self.errstrings[errno],dos_error_strings[errno])
      return self.errstrings[errno]
    else:
      return 0

  # As we only have one file system (though with multiple assigns)
  # it does not really matter what we do here...
  def GetFileSysTask(self,ctx):
    return ctx.process.this_task.access.r_s("pr_FileSystemTask")

  def SetFileSysTask(self,ctx):
    port = ctx.cpu.r_reg(REG_D1)
    ctx.process.this_task.access.w_s("pr_FileSystemTask",port)

  # ----- Helpers -----

  def _alloc_mem(self, name, size):
    mem = self.alloc.alloc_memory(name,size)
    self.mem_allocs[mem.addr] = mem
    return mem.addr

  def _free_mem(self, addr):
    if self.mem_allocs.has_key(addr):
      mem = self.mem_allocs[addr]
      self.alloc.free_memory(mem)
      del self.mem_allocs[addr]
    else:
      raise VamosInternalError("Invalid DOS free mem: %06x" % addr)
