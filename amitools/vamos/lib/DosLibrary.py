import time

from amitools.vamos.AmigaLibrary import *
from dos.DosStruct import *
from lexec.ExecStruct import *
from amitools.vamos.Exceptions import *
from amitools.vamos.Log import log_dos
from amitools.vamos.AccessStruct import AccessStruct
from dos.Args import *
from dos.Error import *
from dos.AmiTime import *
from util.TagList import *
import dos.Printf
from dos.DosTags import DosTags
from dos.PatternMatch import pattern_parse, pattern_match
from dos.PathMatch import PathMatch
from amitools.vamos.LabelStruct import LabelStruct

class DosLibrary(AmigaLibrary):
  name = "dos.library"
  dos_calls = (
   (30, 'Open', (('name', 'd1'), ('accessMode', 'd2'))),
   (36, 'Close', (('file', 'd1'),)),
   (42, 'Read', (('file', 'd1'), ('buffer', 'd2'), ('length', 'd3'))),
   (48, 'Write', (('file', 'd1'), ('buffer', 'd2'), ('length', 'd3'))),
   (54, 'Input', None),
   (60, 'Output', None),
   (66, 'Seek', (('file', 'd1'), ('position', 'd2'), ('offset', 'd3'))),
   (72, 'DeleteFile', (('name', 'd1'),)),
   (78, 'Rename', (('oldName', 'd1'), ('newName', 'd2'))),
   (84, 'Lock', (('name', 'd1'), ('type', 'd2'))),
   (90, 'UnLock', (('lock', 'd1'),)),
   (96, 'DupLock', (('lock', 'd1'),)),
   (102, 'Examine', (('lock', 'd1'), ('fileInfoBlock', 'd2'))),
   (108, 'ExNext', (('lock', 'd1'), ('fileInfoBlock', 'd2'))),
   (114, 'Info', (('lock', 'd1'), ('parameterBlock', 'd2'))),
   (120, 'CreateDir', (('name', 'd1'),)),
   (126, 'CurrentDir', (('lock', 'd1'),)),
   (132, 'IoErr', None),
   (138, 'CreateProc', (('name', 'd1'), ('pri', 'd2'), ('segList', 'd3'), ('stackSize', 'd4'))),
   (144, 'Exit', (('returnCode', 'd1'),)),
   (150, 'LoadSeg', (('name', 'd1'),)),
   (156, 'UnLoadSeg', (('seglist', 'd1'),)),
   (162, 'dosPrivate1', None),
   (168, 'dosPrivate2', None),
   (174, 'DeviceProc', (('name', 'd1'),)),
   (180, 'SetComment', (('name', 'd1'), ('comment', 'd2'))),
   (186, 'SetProtection', (('name', 'd1'), ('protect', 'd2'))),
   (192, 'DateStamp', (('date', 'd1'),)),
   (198, 'Delay', (('timeout', 'd1'),)),
   (204, 'WaitForChar', (('file', 'd1'), ('timeout', 'd2'))),
   (210, 'ParentDir', (('lock', 'd1'),)),
   (216, 'IsInteractive', (('file', 'd1'),)),
   (222, 'Execute', (('string', 'd1'), ('file', 'd2'), ('file2', 'd3'))),
   (228, 'AllocDosObject', (('type', 'd1'), ('tags', 'd2'))),
   (234, 'FreeDosObject', (('type', 'd1'), ('ptr', 'd2'))),
   (240, 'DoPkt', (('port', 'd1'), ('action', 'd2'), ('arg1', 'd3'), ('arg2', 'd4'), ('arg3', 'd5'), ('arg4', 'd6'), ('arg5', 'd7'))),
   (246, 'SendPkt', (('dp', 'd1'), ('port', 'd2'), ('replyport', 'd3'))),
   (252, 'WaitPkt', None),
   (258, 'ReplyPkt', (('dp', 'd1'), ('res1', 'd2'), ('res2', 'd3'))),
   (264, 'AbortPkt', (('port', 'd1'), ('pkt', 'd2'))),
   (270, 'LockRecord', (('fh', 'd1'), ('offset', 'd2'), ('length', 'd3'), ('mode', 'd4'), ('timeout', 'd5'))),
   (276, 'LockRecords', (('recArray', 'd1'), ('timeout', 'd2'))),
   (282, 'UnLockRecord', (('fh', 'd1'), ('offset', 'd2'), ('length', 'd3'))),
   (288, 'UnLockRecords', (('recArray', 'd1'),)),
   (294, 'SelectInput', (('fh', 'd1'),)),
   (300, 'SelectOutput', (('fh', 'd1'),)),
   (306, 'FGetC', (('fh', 'd1'),)),
   (312, 'FPutC', (('fh', 'd1'), ('ch', 'd2'))),
   (318, 'UnGetC', (('fh', 'd1'), ('character', 'd2'))),
   (324, 'FRead', (('fh', 'd1'), ('block', 'd2'), ('blocklen', 'd3'), ('number', 'd4'))),
   (330, 'FWrite', (('fh', 'd1'), ('block', 'd2'), ('blocklen', 'd3'), ('number', 'd4'))),
   (336, 'FGets', (('fh', 'd1'), ('buf', 'd2'), ('buflen', 'd3'))),
   (342, 'FPuts', (('fh', 'd1'), ('str', 'd2'))),
   (348, 'VFWritef', (('fh', 'd1'), ('format', 'd2'), ('argarray', 'd3'))),
   (354, 'VFPrintf', (('fh', 'd1'), ('format', 'd2'), ('argarray', 'd3'))),
   (360, 'Flush', (('fh', 'd1'),)),
   (366, 'SetVBuf', (('fh', 'd1'), ('buff', 'd2'), ('type', 'd3'), ('size', 'd4'))),
   (372, 'DupLockFromFH', (('fh', 'd1'),)),
   (378, 'OpenFromLock', (('lock', 'd1'),)),
   (384, 'ParentOfFH', (('fh', 'd1'),)),
   (390, 'ExamineFH', (('fh', 'd1'), ('fib', 'd2'))),
   (396, 'SetFileDate', (('name', 'd1'), ('date', 'd2'))),
   (402, 'NameFromLock', (('lock', 'd1'), ('buffer', 'd2'), ('len', 'd3'))),
   (408, 'NameFromFH', (('fh', 'd1'), ('buffer', 'd2'), ('len', 'd3'))),
   (414, 'SplitName', (('name', 'd1'), ('seperator', 'd2'), ('buf', 'd3'), ('oldpos', 'd4'), ('size', 'd5'))),
   (420, 'SameLock', (('lock1', 'd1'), ('lock2', 'd2'))),
   (426, 'SetMode', (('fh', 'd1'), ('mode', 'd2'))),
   (432, 'ExAll', (('lock', 'd1'), ('buffer', 'd2'), ('size', 'd3'), ('data', 'd4'), ('control', 'd5'))),
   (438, 'ReadLink', (('port', 'd1'), ('lock', 'd2'), ('path', 'd3'), ('buffer', 'd4'), ('size', 'd5'))),
   (444, 'MakeLink', (('name', 'd1'), ('dest', 'd2'), ('soft', 'd3'))),
   (450, 'ChangeMode', (('type', 'd1'), ('fh', 'd2'), ('newmode', 'd3'))),
   (456, 'SetFileSize', (('fh', 'd1'), ('pos', 'd2'), ('mode', 'd3'))),
   (462, 'SetIoErr', (('result', 'd1'),)),
   (468, 'Fault', (('code', 'd1'), ('header', 'd2'), ('buffer', 'd3'), ('len', 'd4'))),
   (474, 'PrintFault', (('code', 'd1'), ('header', 'd2'))),
   (480, 'ErrorReport', (('code', 'd1'), ('type', 'd2'), ('arg1', 'd3'), ('device', 'd4'))),
   (492, 'Cli', None),
   (498, 'CreateNewProc', (('tags', 'd1'),)),
   (504, 'RunCommand', (('seg', 'd1'), ('stack', 'd2'), ('paramptr', 'd3'), ('paramlen', 'd4'))),
   (510, 'GetConsoleTask', None),
   (516, 'SetConsoleTask', (('task', 'd1'),)),
   (522, 'GetFileSysTask', None),
   (528, 'SetFileSysTask', (('task', 'd1'),)),
   (534, 'GetArgStr', None),
   (540, 'SetArgStr', (('string', 'd1'),)),
   (546, 'FindCliProc', (('num', 'd1'),)),
   (552, 'MaxCli', None),
   (558, 'SetCurrentDirName', (('name', 'd1'),)),
   (564, 'GetCurrentDirName', (('buf', 'd1'), ('len', 'd2'))),
   (570, 'SetProgramName', (('name', 'd1'),)),
   (576, 'GetProgramName', (('buf', 'd1'), ('len', 'd2'))),
   (582, 'SetPrompt', (('name', 'd1'),)),
   (588, 'GetPrompt', (('buf', 'd1'), ('len', 'd2'))),
   (594, 'SetProgramDir', (('lock', 'd1'),)),
   (600, 'GetProgramDir', None),
   (606, 'SystemTagList', (('command', 'd1'), ('tags', 'd2'))),
   (612, 'AssignLock', (('name', 'd1'), ('lock', 'd2'))),
   (618, 'AssignLate', (('name', 'd1'), ('path', 'd2'))),
   (624, 'AssignPath', (('name', 'd1'), ('path', 'd2'))),
   (630, 'AssignAdd', (('name', 'd1'), ('lock', 'd2'))),
   (636, 'RemAssignList', (('name', 'd1'), ('lock', 'd2'))),
   (642, 'GetDeviceProc', (('name', 'd1'), ('dp', 'd2'))),
   (648, 'FreeDeviceProc', (('dp', 'd1'),)),
   (654, 'LockDosList', (('flags', 'd1'),)),
   (660, 'UnLockDosList', (('flags', 'd1'),)),
   (666, 'AttemptLockDosList', (('flags', 'd1'),)),
   (672, 'RemDosEntry', (('dlist', 'd1'),)),
   (678, 'AddDosEntry', (('dlist', 'd1'),)),
   (684, 'FindDosEntry', (('dlist', 'd1'), ('name', 'd2'), ('flags', 'd3'))),
   (690, 'NextDosEntry', (('dlist', 'd1'), ('flags', 'd2'))),
   (696, 'MakeDosEntry', (('name', 'd1'), ('type', 'd2'))),
   (702, 'FreeDosEntry', (('dlist', 'd1'),)),
   (708, 'IsFileSystem', (('name', 'd1'),)),
   (714, 'Format', (('filesystem', 'd1'), ('volumename', 'd2'), ('dostype', 'd3'))),
   (720, 'Relabel', (('drive', 'd1'), ('newname', 'd2'))),
   (726, 'Inhibit', (('name', 'd1'), ('onoff', 'd2'))),
   (732, 'AddBuffers', (('name', 'd1'), ('number', 'd2'))),
   (738, 'CompareDates', (('date1', 'd1'), ('date2', 'd2'))),
   (744, 'DateToStr', (('datetime', 'd1'),)),
   (750, 'StrToDate', (('datetime', 'd1'),)),
   (756, 'InternalLoadSeg', (('fh', 'd0'), ('table', 'a0'), ('funcarray', 'a1'), ('stack', 'a2'))),
   (762, 'InternalUnLoadSeg', (('seglist', 'd1'), ('freefunc', 'a1'))),
   (768, 'NewLoadSeg', (('file', 'd1'), ('tags', 'd2'))),
   (774, 'AddSegment', (('name', 'd1'), ('seg', 'd2'), ('system', 'd3'))),
   (780, 'FindSegment', (('name', 'd1'), ('seg', 'd2'), ('system', 'd3'))),
   (786, 'RemSegment', (('seg', 'd1'),)),
   (792, 'CheckSignal', (('mask', 'd1'),)),
   (798, 'ReadArgs', (('arg_template', 'd1'), ('array', 'd2'), ('args', 'd3'))),
   (804, 'FindArg', (('keyword', 'd1'), ('arg_template', 'd2'))),
   (810, 'ReadItem', (('name', 'd1'), ('maxchars', 'd2'), ('cSource', 'd3'))),
   (816, 'StrToLong', (('string', 'd1'), ('value', 'd2'))),
   (822, 'MatchFirst', (('pat', 'd1'), ('anchor', 'd2'))),
   (828, 'MatchNext', (('anchor', 'd1'),)),
   (834, 'MatchEnd', (('anchor', 'd1'),)),
   (840, 'ParsePattern', (('pat', 'd1'), ('buf', 'd2'), ('buflen', 'd3'))),
   (846, 'MatchPattern', (('pat', 'd1'), ('str', 'd2'))),
   (852, 'dosPrivate3', None),
   (858, 'FreeArgs', (('args', 'd1'),)),
   (870, 'FilePart', (('path', 'd1'),)),
   (876, 'PathPart', (('path', 'd1'),)),
   (882, 'AddPart', (('dirname', 'd1'), ('filename', 'd2'), ('size', 'd3'))),
   (888, 'StartNotify', (('notify', 'd1'),)),
   (894, 'EndNotify', (('notify', 'd1'),)),
   (900, 'SetVar', (('name', 'd1'), ('buffer', 'd2'), ('size', 'd3'), ('flags', 'd4'))),
   (906, 'GetVar', (('name', 'd1'), ('buffer', 'd2'), ('size', 'd3'), ('flags', 'd4'))),
   (912, 'DeleteVar', (('name', 'd1'), ('flags', 'd2'))),
   (918, 'FindVar', (('name', 'd1'), ('type', 'd2'))),
   (924, 'dosPrivate4', None),
   (930, 'CliInitNewcli', (('dp', 'a0'),)),
   (936, 'CliInitRun', (('dp', 'a0'),)),
   (942, 'WriteChars', (('buf', 'd1'), ('buflen', 'd2'))),
   (948, 'PutStr', (('str', 'd1'),)),
   (954, 'VPrintf', (('format', 'd1'), ('argarray', 'd2'))),
   (966, 'ParsePatternNoCase', (('pat', 'd1'), ('buf', 'd2'), ('buflen', 'd3'))),
   (972, 'MatchPatternNoCase', (('pat', 'd1'), ('str', 'd2'))),
   (978, 'dosPrivate5', None),
   (984, 'SameDevice', (('lock1', 'd1'), ('lock2', 'd2'))),
   (990, 'ExAllEnd', (('lock', 'd1'), ('buffer', 'd2'), ('size', 'd3'), ('data', 'd4'), ('control', 'd5'))),
   (996, 'SetOwner', (('name', 'd1'), ('owner_info', 'd2'))),
  )
  
  DOSFALSE = 0
  DOSTRUE = 0xffffffff
  
  def __init__(self, mem, alloc, version=39):
    AmigaLibrary.__init__(self, self.name, version, self.dos_calls, DosLibraryDef)
    self.mem = mem
    self.alloc = alloc
    
    dos_funcs = (
      (30, self.Open),
      (36, self.Close),
      (42, self.Read),
      (48, self.Write),
      (54, self.Input),
      (60, self.Output),
      (66, self.Seek),
      (72, self.DeleteFile),
      (78, self.Rename),
      (84, self.Lock),
      (90, self.UnLock),
      (96, self.DupLock),
      (102, self.Examine),
      (126, self.CurrentDir),
      (132, self.IoErr),
      (150, self.LoadSeg),
      (156, self.UnLoadSeg),
      (192, self.DateStamp),
      (210, self.ParentDir),
      (216, self.IsInteractive),
      (306, self.FGetC),
      (462, self.SetIoErr),
      (474, self.PrintFault),
      (606, self.SystemTagList),
      (642, self.GetDeviceProc),
      (648, self.FreeDeviceProc),
      (798, self.ReadArgs),
      (822, self.MatchFirst),
      (828, self.MatchNext),
      (834, self.MatchEnd),
      (840, self.ParsePattern),
      (846, self.MatchPattern),
      (858, self.FreeArgs),
      (870, self.FilePart),
      (948, self.PutStr),
      (954, self.VPrintf),
      (966, self.ParsePatternNoCase),
      (972, self.MatchPatternNoCase)
    )
    self.set_funcs(dos_funcs)
  
  def set_managers(self, path_mgr, lock_mgr, file_mgr, port_mgr, seg_loader):
    self.path_mgr = path_mgr
    self.lock_mgr = lock_mgr
    self.file_mgr = file_mgr
    self.port_mgr = port_mgr
    self.seg_loader = seg_loader;
    # create fs handler port
    self.fs_handler_port = port_mgr.add_int_port(self)
    log_dos.info("dos fs handler port: %06x" % self.fs_handler_port)
    file_mgr.set_fs_handler_port(self.fs_handler_port)
  
  def setup_lib(self, lib, ctx):
    log_dos.info("open dos.library V%d", self.version)
    # setup lib struct
    lib.access.w_s("lib.lib_Version", self.version)
    # init own state
    self.io_err = 0
    self.cur_dir_lock = None
    self.ctx = ctx
    self.mem_allocs = {}
    self.seg_lists = {}
    self.matches = {}
    self.rdargs = {}
    # setup RootNode
    self.root_struct = ctx.alloc.alloc_struct("RootNode",RootNodeDef)
    lib.access.w_s("dl_Root",self.root_struct.addr)
    # setup DosInfo
    self.dos_info = ctx.alloc.alloc_struct("DosInfo",DosInfoDef)
    self.root_struct.access.w_s("rn_Info",self.dos_info.addr)
  
  def finish_lib(self, lib, ctx):
    ctx.alloc.free_struct(self.root_struct)
    ctx.alloc.free_struct(self.dos_info)
  
  # ----- Direct Handler Access -----
  
  # callback from port manager for fs handler port
  # -> Async I/O
  def put_msg(self, port_mgr, msg_addr):
    msg = AccessStruct(self.ctx.mem,MessageDef,struct_addr=msg_addr)
    dos_pkt_addr = msg.r_s("mn_Node.ln_Name")
    dos_pkt = AccessStruct(self.ctx.mem,DosPacketDef,struct_addr=dos_pkt_addr)
    reply_port_addr = dos_pkt.r_s("dp_Port")
    pkt_type = dos_pkt.r_s("dp_Type")
    log_dos.info("DosPacket: msg=%06x -> pkt=%06x: reply_port=%06x type=%06x", msg_addr, dos_pkt_addr, reply_port_addr, pkt_type)
    # handle packet
    if pkt_type == ord('R'): # read
      fh_b_addr = dos_pkt.r_s("dp_Arg1")
      buf_ptr   = dos_pkt.r_s("dp_Arg2")
      size      = dos_pkt.r_s("dp_Arg3")
      # get fh and read
      fh = self.file_mgr.get_by_b_addr(fh_b_addr)
      data = self.file_mgr.read(fh, size)
      self.ctx.mem.access.w_data(buf_ptr, data)
      got = len(data)
      log_dos.info("DosPacket: Read fh_b_addr=%06x buf=%06x len=%06x -> got=%06x fh=%s", fh_b_addr, buf_ptr, size, got, fh)
      dos_pkt.w_s("dp_Res1", got)
    elif pkt_type == ord('W'): # write
      fh_ptr  = dos_pkt.r_s("dp_Arg1")
      buf_ptr = dos_pkt.r_s("dp_Arg2")
      size    = dos_pkt.r_s("dp_Arg3")
      log_dos.info("DosPacket: Write fh=%06x buf=%06x len=%06x", fh_ptr, buf_ptr, size)
      # TBD
      raise UnsupportedFeatureException("Unsupported DosPacket: type=%d" % pkt_type)
    else:
      raise UnsupportedFeatureException("Unsupported DosPacket: type=%d" % pkt_type)
    # do reply
    if not self.port_mgr.has_port(reply_port_addr):
      self.port_mgr.add_port(reply_port_addr)
    self.port_mgr.put_msg(reply_port_addr, msg_addr)
    
  # ----- IoErr -----
  
  def IoErr(self, lib, ctx):
    log_dos.info("IoErr: %d" % self.io_err)
    return self.io_err
  
  def SetIoErr(self, lib, ctx):
    old_io_err = self.io_err
    self.io_err = ctx.cpu.r_reg(REG_D1)
    log_dos.info("SetIoErr: IoErr=%d old IoErr=%d", self.io_err, old_io_err)
    return old_io_err
  
  def PrintFault(self, lib, ctx):
    self.io_err = ctx.cpu.r_reg(REG_D1)
    hdr_ptr = ctx.cpu.r_reg(REG_D2)
    # get header string
    if hdr_ptr != 0:
      hdr = ctx.mem.access.r_cstr(hdr_ptr)
    else:
      hdr = ""
    # get error string
    if dos_error_strings.has_key(self.io_err):
      err_str = dos_error_strings[self.io_err]
    else:
      err_str = "??? ERROR"
    log_dos.info("PrintFault: code=%d header='%s' err_str='%s'", self.io_err, hdr, err_str)
    # write to stdout
    txt = "%s%s\n" % (hdr, err_str) 
    fh = self.file_mgr.get_output()
    self.file_mgr.write(fh, txt)
    return self.DOSTRUE
  
  # ----- dos API -----
  
  def DateStamp(self, lib, ctx):
    ds_ptr = ctx.cpu.r_reg(REG_D1)
    ds = AccessStruct(ctx.mem,DateStampDef,struct_addr=ds_ptr)
    t = time.time()
    at = sys_to_ami_time(t)
    log_dos.info("DateStamp: ptr=%06x time=%s" % (ds_ptr, at))
    ds.w_s("ds_Days",at.tday)
    ds.w_s("ds_Minute",at.tmin)
    ds.w_s("ds_Tick",at.tick)
    return ds_ptr
    
  # ----- File Ops -----
  
  def Input(self, lib, ctx):
    std_input = self.file_mgr.get_input()
    log_dos.info("Input: %s" % std_input)
    return std_input.b_addr
  
  def Output(self, lib, ctx):
    std_output = self.file_mgr.get_output()
    log_dos.info("Output: %s" % std_output)
    return std_output.b_addr
  
  def Open(self, lib, ctx):
    name_ptr = ctx.cpu.r_reg(REG_D1)
    name = ctx.mem.access.r_cstr(name_ptr)
    mode = ctx.cpu.r_reg(REG_D2)

    # decode mode
    if mode == 1006:
      mode_name = "new"
      f_mode = "wb"
    elif mode == 1005:
      mode_name = "old"
      f_mode = "rb"
    elif mode == 1004:
      mode_name = "r/w"
      f_mode = "ab"
    else:
      mode_name = "?"
    
    fh = self.file_mgr.open(name, f_mode)
    log_dos.info("Open: name='%s' (%s/%d/%s) -> %s" % (name, mode_name, mode, f_mode, fh))
      
    if fh == None:
      self.io_err = ERROR_OBJECT_NOT_FOUND
      return 0
    else:
      return fh.b_addr
  
  def Close(self, lib, ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)

    fh = self.file_mgr.get_by_b_addr(fh_b_addr)
    self.file_mgr.close(fh)
    log_dos.info("Close: %s" % fh)

    return self.DOSTRUE
  
  def Read(self, lib, ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)
    buf_ptr = ctx.cpu.r_reg(REG_D2)
    size = ctx.cpu.r_reg(REG_D3)

    fh = self.file_mgr.get_by_b_addr(fh_b_addr)
    data = self.file_mgr.read(fh, size)
    ctx.mem.access.w_data(buf_ptr, data)
    got = len(data)
    log_dos.info("Read(%s, %06x, %d) -> %d" % (fh, buf_ptr, size, got))
    return got
    
  def Write(self, lib, ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)
    buf_ptr = ctx.cpu.r_reg(REG_D2)
    size = ctx.cpu.r_reg(REG_D3)
    
    fh = self.file_mgr.get_by_b_addr(fh_b_addr)
    data = ctx.mem.access.r_data(buf_ptr,size)
    self.file_mgr.write(fh, data)
    got = len(data)
    log_dos.info("Write(%s, %06x, %d) -> %d" % (fh, buf_ptr, size, got))
    return size

  def Seek(self, lib, ctx):
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
    elif mode == 1:
      mode_str = "END"
      whence = 2
    else:
      raise UnsupportedFeatureException("Seek: mode=%d" % mode)

    old_pos = self.file_mgr.tell(fh)
    self.file_mgr.seek(fh, pos, whence)
    log_dos.info("Seek(%s, %06x, %s) -> old_pos=%06x" % (fh, pos, mode_str, old_pos))
    return old_pos
  
  def FGetC(self, lib, ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)
    fh = self.file_mgr.get_by_b_addr(fh_b_addr)
    # TODO: use buffered I/O
    ch = self.file_mgr.read(fh, 1)
    log_dos.info("FGetC(%s) -> ch=%s" % (fh, ch))
    if ch == None or ch == "":
      return -1
    else:
      return ord(ch)
  
  # ----- StdOut -----
  
  def PutStr(self, lib, ctx):
    str_ptr = ctx.cpu.r_reg(REG_D1)
    str_dat = ctx.mem.access.r_cstr(str_ptr)
    # write to stdout
    fh = self.file_mgr.get_output()
    ok = self.file_mgr.write(fh, str_dat)
    log_dos.info("PutStr: '%s'", str_dat)
    return 0 # ok

  def VPrintf(self, lib, ctx):
    format_ptr = ctx.cpu.r_reg(REG_D1)
    argv_ptr = ctx.cpu.r_reg(REG_D2)
    format = ctx.mem.access.r_cstr(format_ptr)
    # write on output
    fh = self.file_mgr.get_output()
    log_dos.info("VPrintf: format='%s' argv=%06x" % (format,argv_ptr))
    # now decode printf
    ps = dos.Printf.printf_parse_string(format)
    dos.Printf.printf_read_data(ps, ctx.mem.access, argv_ptr)
    log_dos.debug("VPrintf: parsed format: %s",ps)
    result = dos.Printf.printf_generate_output(ps)
    # write result
    self.file_mgr.write(fh, result)
    return len(result)
  
  # ----- File Ops -----

  def DeleteFile(self, lib, ctx):
    name_ptr = ctx.cpu.r_reg(REG_D1)
    name = ctx.mem.access.r_cstr(name_ptr)
    self.io_err = self.file_mgr.delete(name)
    log_dos.info("DeleteFile: '%s': err=%s" % (name, self.io_err))
    if self.io_err == 0:
      return self.DOSTRUE
    else:
      return self.DOSFALSE

  def Rename(self, lib, ctx):
    old_name_ptr = ctx.cpu.r_reg(REG_D1)
    old_name = ctx.mem.access.r_cstr(old_name_ptr)
    new_name_ptr = ctx.cpu.r_reg(REG_D2)
    new_name = ctx.mem.access.r_cstr(new_name_ptr)
    self.io_err = self.file_mgr.rename(old_name, new_name)
    log_dos.info("Rename: '%s' -> '%s': err=%s" % (old_name, new_name, self.io_err))
    if self.io_err == 0:
      return self.DOSTRUE
    else:
      return self.DOSFALSE

  def IsInteractive(self, lib, ctx):
    fh_b_addr = ctx.cpu.r_reg(REG_D1)
    fh = self.file_mgr.get_by_b_addr(fh_b_addr)
    res = self.file_mgr.is_interactive(fh)
    log_dos.info("IsInteractive(%s): %s" % (fh, res))
    if res:
      return self.DOSTRUE
    else:
      return self.DOSFALSE
    
  # ----- Locks -----
  
  def Lock(self, lib, ctx):
    name_ptr = ctx.cpu.r_reg(REG_D1)
    name = ctx.mem.access.r_cstr(name_ptr)
    mode = ctx.cpu.r_reg(REG_D2)

    if mode == 0xffffffff:
      lock_exclusive = True
    elif mode == 0xfffffffe:
      lock_exclusive = False
    else:
      raise UnsupportedFeatureException("Lock: mode=%x" % mode)
    
    lock = self.lock_mgr.create_lock(name, lock_exclusive)
    log_dos.info("Lock: '%s' exc=%s -> %s" % (name, lock_exclusive, lock))
    if lock == None:
      self.io_err = ERROR_OBJECT_NOT_FOUND
      return 0
    else:
      return lock.b_addr
  
  def UnLock(self, lib, ctx):
    lock_b_addr = ctx.cpu.r_reg(REG_D1)
    lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
    log_dos.info("UnLock: %s" % (lock))
    self.lock_mgr.release_lock(lock)
    self.io_err = NO_ERROR    
    return self.DOSTRUE
  
  def DupLock(self, lib, ctx):
    lock_b_addr = ctx.cpu.r_reg(REG_D1)
    lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
    dup_lock = self.lock_mgr.create_lock(lock.ami_path, False)
    log_dos.info("DupLock: %s -> %s",lock, dup_lock)
    self.io_err = NO_ERROR
    return dup_lock.b_addr
  
  def Examine(self, lib, ctx):
    lock_b_addr = ctx.cpu.r_reg(REG_D1)
    fib_ptr = ctx.cpu.r_reg(REG_D2)
    lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
    log_dos.info("Examine: %s fib=%06x" % (lock, fib_ptr))
    fib = AccessStruct(ctx.mem,FileInfoBlockDef,struct_addr=fib_ptr)
    self.lock_mgr.examine_lock(lock, fib)
    self.io_err = NO_ERROR
    return self.DOSTRUE
  
  def ParentDir(self, lib, ctx):
    lock_b_addr = ctx.cpu.r_reg(REG_D1)
    lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
    parent_lock = self.lock_mgr.create_parent_lock(lock)
    log_dos.info("ParentDir: %s -> %s" % (lock, parent_lock))
    if parent_lock != None:
      return parent_lock.b_addr
    else:
      return 0

  def CurrentDir(self, lib, ctx):
    lock_b_addr = ctx.cpu.r_reg(REG_D1)
    old_lock = self.cur_dir_lock
    if lock_b_addr == 0:
      new_lock = None
    else:
      new_lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
    self.cur_dir_lock = new_lock
    log_dos.info("CurrentDir: %s -> %s" % (old_lock, new_lock))
    # set current path in path mgr
    if new_lock != None:
      self.path_mgr.set_cur_path(new_lock.ami_path)
    else:
      self.path_mgr.set_default_cur_path()
    if old_lock == None:
      return 0
    else:
      return old_lock.b_addr

  # ----- DevProc -----

  def GetDeviceProc(self, lib, ctx):
    name_ptr = ctx.cpu.r_reg(REG_D1)
    last_devproc = ctx.cpu.r_reg(REG_D2)
    name = ctx.mem.access.r_cstr(name_ptr)

    # get volume of path 
    abs_name = self.path_mgr.ami_abs_path(name)
    volume = self.path_mgr.ami_volume_of_path(abs_name)
    vol_lock = self.lock_mgr.create_lock(volume+":", False)
    fs_port = self.file_mgr.get_fs_handler_port()
    addr = self._alloc_mem("DevProc:%s" % name, DevProcDef.get_size())
    log_dos.info("GetDeviceProc: name='%s' devproc=%06x -> volume=%s devproc=%06x", name, last_devproc, volume, addr)
    devproc = AccessStruct(self.ctx.mem,DevProcDef,struct_addr=addr)
    devproc.w_s('dvp_Port', fs_port)
    devproc.w_s('dvp_Lock', vol_lock.b_addr)
    self.io_err = NO_ERROR
    return addr

  def FreeDeviceProc(self, lib, ctx):
    addr = ctx.cpu.r_reg(REG_D1)
    self._free_mem(addr)
    log_dos.info("FreeDeviceProc: devproc=%06x", addr)

  # ----- Matcher -----
  
  def MatchFirst(self, lib, ctx):
    pat_ptr = ctx.cpu.r_reg(REG_D1)
    pat = ctx.mem.access.r_cstr(pat_ptr)
    anchor_ptr = ctx.cpu.r_reg(REG_D2)
    # get total size of struct
    anchor = AccessStruct(self.ctx.mem,AnchorPathDef,struct_addr=anchor_ptr)
    str_len = anchor.r_s('ap_Strlen')
    total_size = AnchorPathDef.get_size() + str_len
    # setup matcher
    matcher = PathMatch(self.path_mgr)
    ok = matcher.parse(pat)
    log_dos.info("MatchFirst: pat='%s' anchor=%06x strlen=%d -> ok=%s" % (pat, anchor_ptr, str_len, ok))
    if not ok:
      self.io_err = ERROR_BAD_TEMPLATE
      return self.io_err
    # get first entry
    path = matcher.begin()
    # no entry found
    if path == None:
      log_dos.info("MatchFirst: none found!")
      self.matches[anchor_ptr] = {}
      self.io_err = ERROR_OBJECT_NOT_FOUND
    else:
      # replace label of struct
      old_label = ctx.label_mgr.get_label(anchor_ptr)
      if old_label != None:
        ctx.label_mgr.remove_label(old_label)
      new_label = LabelStruct("MatchAnchor", anchor_ptr, AnchorPathDef, size=total_size)
      ctx.label_mgr.add_label(new_label)
      
      # get parent dir of first match
      abs_path = self.path_mgr.ami_abs_path(path)
      voldir_path = self.path_mgr.ami_voldir_of_path(abs_path)
      dir_lock = self.lock_mgr.create_lock(voldir_path, False)
      log_dos.info("MatchFirst: found path='%s' -> dir path=%s -> parent lock %s", path, voldir_path, dir_lock)
      
      # create last achain and set dir lock
      achain_last = ctx.alloc.alloc_struct("AChain_Last", AChainDef)
      anchor.w_s('ap_Last', achain_last.addr)
      achain_last.access.w_s('an_Lock', dir_lock.addr)
      
      # fill FileInfo of first match in anchor
      lock = self.lock_mgr.create_lock(abs_path, False)
      fib_ptr = anchor.s_get_addr('ap_Info')
      fib = AccessStruct(ctx.mem,FileInfoBlockDef,struct_addr=fib_ptr)
      self.lock_mgr.examine_lock(lock, fib)
      self.lock_mgr.release_lock(lock)
      # store path name of first name at end of structure
      if str_len > 0:
        path_ptr = anchor.s_get_addr('ap_Buf')
        abs_path = self.path_mgr.ami_abs_path(path)
        anchor.w_cstr(path_ptr, abs_path)
      
      # store the match
      match = {
        'old_label' : old_label,
        'new_label' : new_label,
        'matcher' : matcher,
        'achain_last' : achain_last
      }
      self.matches[anchor_ptr] = match
      # ok
      self.io_err = NO_ERROR
    return self.io_err
  
  def MatchNext(self, lib, ctx):
    anchor_ptr = ctx.cpu.r_reg(REG_D1)
    anchor = AccessStruct(self.ctx.mem,AnchorPathDef,struct_addr=anchor_ptr)
    log_dos.info("MatchNext: anchor=%06x " % (anchor_ptr))
    # retrieve match
    if not self.matches.has_key(anchor_ptr):
      raise VamosInternalError("No matcher found for %06x" % anchor_ptr)
    match = self.matches[anchor_ptr]
    if match.has_key('matcher'):
      matcher = match['matcher']
      # get next match
    
    
    return ERROR_NO_MORE_ENTRIES
  
  def MatchEnd(self, lib, ctx):
    anchor_ptr = ctx.cpu.r_reg(REG_D1)
    anchor = AccessStruct(self.ctx.mem,AnchorPathDef,struct_addr=anchor_ptr)
    log_dos.info("MatchEnd: anchor=%06x " % (anchor_ptr))
    # retrieve match
    if not self.matches.has_key(anchor_ptr):
      raise VamosInternalError("No matcher found for %06x" % anchor_ptr)
    match = self.matches[anchor_ptr]
    del self.matches[anchor_ptr]
    # valid non empty match
    if match.has_key('matcher'):
      # restore label
      old_label = match['old_label']
      new_label = match['new_label']
      ctx.label_mgr.remove_label(new_label)
      if old_label != None:
        ctx.label_mgr.add_label(old_label)
      # free last lock & achain
      achain_last = match['achain_last']
      lock_addr = achain_last.access.r_s('an_Lock')
      lock = self.lock_mgr.get_by_b_addr(lock_addr >> 2)
      self.lock_mgr.release_lock(lock)
      ctx.alloc.free_struct(achain_last)
  
  # ----- Pattern Parsing and Matching -----
  
  def ParsePattern(self, lib, ctx, ignore_case=False):
    src_ptr = ctx.cpu.r_reg(REG_D1)
    dst_ptr = ctx.cpu.r_reg(REG_D2)
    dst_len = ctx.cpu.r_reg(REG_D3)
    src = ctx.mem.access_r_cstr(src_ptr)
    pat = pattern_parse(src, ignore_case=ignore_case)
    log_dos.info("ParsePattern: src=%s ignore_case=%s -> pat=%s",src, ignore_case, pat)
    if pat == None:
      self.io_err = ERROR_BAD_TEMPLATE
      return -1
    else:
      self.io_err = NO_ERROR
      pat_str = pat.pat_str
      if len(pat_str) >= dst_len:
        return -1
      else:
        ctx.mem.access.w_cstr(dst_ptr, pat_str)
        if pat.has_wildcard:
          return 1
        else:
          return 0

  def ParsePatternNoCase(self, lib, ctx):
    return self.ParsePattern(lib, ctx, ignore_case=True)
  
  def MatchPattern(self, lib, ctx, ignore_case=False):
    pat_ptr = ctx.cpu.r_reg(REG_D1)
    txt_ptr = ctx.cpu.r_reg(REG_D2)
    pat = ctx.mem.access.r_cstr(pat_ptr)
    txt = ctx.mem.access.r_cstr(txt_ptr)
    match = pattern_match(pat, txt)
    log_dos.info("MatchPattern: pat=%s txt=%s ignore_case=%s -> match=%s", pat, txt, ignore_case, match)
    if match:
      return -1
    else:
      return 0
  
  def MatchPatternNoCase(self, lib, ctx):
    return self.MatchPattern(lib, ctx, ignore_case=True)
  
  # ----- Args -----
  
  def ReadArgs(self, lib, ctx):
    template_ptr = ctx.cpu.r_reg(REG_D1)
    template = ctx.mem.access.r_cstr(template_ptr)
    array_ptr = ctx.cpu.r_reg(REG_D2)
    rdargs_ptr = ctx.cpu.r_reg(REG_D3)
    
    log_dos.info("ReadArgs: args=%s template='%s' array_ptr=%06x rdargs_ptr=%06x" % (ctx.bin_args, template, array_ptr, rdargs_ptr))
    # try to parse argument string
    args = Args()
    args.parse_template(template)
    args.prepare_input(ctx.mem.access,array_ptr)
    ok = args.parse_string(ctx.bin_args)
    if not ok:
      self.io_err = args.error
      log_dos.info("ReadArgs: not matched -> io_err=%d/%s",self.io_err, dos_error_strings[self.io_err])
      return 0
    log_dos.debug("matched template: %s",args.result)
    # calc size of result
    size = args.calc_result_size()
    log_dos.debug("longs=%d chars=%d size=%d" % (args.num_longs,args.num_chars,size))
    # alloc result mem
    addr = self._alloc_mem("ReadArgs(@%06x)" % self.get_callee_pc(ctx),size)
    # fill result memory
    args.generate_result(ctx.mem.access,addr,array_ptr)
    # alloc RD_Args
    rdargs = ctx.alloc.alloc_struct("RDArgs", RDArgsDef)
    rdargs.access.w_s('RDA_Buffer',addr)
    rdargs.access.w_s('RDA_BufSiz',size)
    # store rdargs
    self.rdargs[rdargs.addr] = rdargs
    # result
    self.io_err = NO_ERROR
    log_dos.info("ReadArgs: matched! result_mem=%06x rdargs=%s", addr, rdargs)
    return rdargs.addr
    
  def FreeArgs(self, lib, ctx):
    rdargs_ptr = ctx.cpu.r_reg(REG_D1)
    log_dos.info("FreeArgs: %06x" % rdargs_ptr)
    # find rdargs
    if not self.rdargs.has_key(rdargs_ptr):
      raise VamosInternalError("Can't find RDArgs: %06x" % rdargs_ptr)
    rdargs = self.rdargs[rdargs_ptr]
    del self.rdargs[rdargs_ptr]
    # clean up rdargs
    addr = rdargs.access.r_s('RDA_Buffer')
    self._free_mem(addr)
    self.alloc.free_struct(rdargs)

  # ----- System/Execute -----
  
  def SystemTagList(self, lib, ctx):
    cmd_ptr = ctx.cpu.r_reg(REG_D1)
    tagitem_ptr = ctx.cpu.r_reg(REG_D2)
    cmd = ctx.mem.access.r_cstr(cmd_ptr)
    tag_list = taglist_parse_tagitem_ptr(ctx.mem, tagitem_ptr, DosTags)
    log_dos.info("SystemTagList: cmd='%s' tags=%s" % (cmd, tag_list))

  def LoadSeg(self, lib, ctx):
    name_ptr = ctx.cpu.r_reg(REG_D1)
    name = ctx.mem.access.r_cstr(name_ptr)
    seg_list = self.seg_loader.load_seg(name)
    if seg_list == None:
      log_dos.warn("LoadSeg: '%s' -> not found!" % (name))
      return 0
    else:
      log_dos.warn("LoadSeg: '%s' -> %s" % (name, seg_list))
      b_addr = seg_list.b_addr
      self.seg_lists[b_addr] = seg_list
      return b_addr
    
  def UnLoadSeg(self, lib, ctx):
    b_addr = ctx.cpu.r_reg(REG_D1)
    if not self.seg_lists.has_key(b_addr):
      raise VamosInternalError("Unknown LoadSeg seg_list: b_addr=%06x" % b_addr)
    else:
      seg_list = self.seg_lists[b_addr]
      del self.seg_lists[b_addr]
      self.seg_loader.unload_seg(seg_list)

  # ----- Path Helper -----
  
  def FilePart(self, lib, ctx):
    addr = ctx.cpu.r_reg(REG_D1)
    path = ctx.mem.access.r_cstr(addr)
    pos = path.rfind('/')
    if pos != -1:
      pos += 1
    else:
      pos = path.find(':')
      if pos == -1:
        pos = 0
      else:
        pos += 1
    log_dos.info("FilePart: path='%s' -> pos=%d", path, pos)
    return addr + pos

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
    
    
    