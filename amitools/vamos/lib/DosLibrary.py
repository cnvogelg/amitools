import types

from amitools.vamos.AmigaLibrary import *
from amitools.vamos.structure.DosStruct import DosLibraryDef

from dos.Args import *

class DosLibrary(AmigaLibrary):
  name = "dos.library"
  version = 39
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
  
  def __init__(self, alloc):
    AmigaLibrary.__init__(self, self.name, self.version, self.dos_calls, DosLibraryDef)
    self.alloc = alloc
    
    dos_funcs = (
       (798, self.ReadArgs),
       (858, self.FreeArgs),
    )
    self.set_funcs(dos_funcs)
    
  def ReadArgs(self, mem_lib, ctx):
    template_ptr = ctx.cpu.r_reg(REG_D1)
    template = ctx.mem.r_cstr(template_ptr)
    array_ptr = ctx.cpu.r_reg(REG_D2)
    rdargs_ptr = ctx.cpu.r_reg(REG_D3)
    
    self.trace_log("ReadArgs: args=%s template=%s" % (ctx.bin_args, template))
    targs = gen_dos_args(template)
    
    # read org values
    in_val = []
    ptr = array_ptr
    for t in targs:
      raw = ctx.mem.read_mem(2,ptr)
      # prefill toggle
      if t['t']:
        in_val.append(bool(raw))
      else:
        in_val.append(None)
    
    # parse
    result = parse_dos_args(targs, ctx.bin_args, in_val)
    self.trace_log("parse: %s" % result)
    
    # calc size of result
    n = len(result)
    num_longs = 0
    num_chars = 0
    for i in xrange(n):
      r = result[i]
      if r == None: # null pointer
        pass
      elif type(r) is types.StringType: # string key 'k'
        num_chars += len(r) + 1
      elif type(r) is types.IntType: # numerical key 'kn'
        num_longs += 1
      elif type(r) is types.ListType: # string list 'm'
        num_longs += len(r) + 1
        for s in r:
          num_chars += len(s) + 1
    
    # calc total size
    size = num_longs * 4 + num_chars
    self.trace_log("longs=%d chars=%d size=%d" % (num_longs,num_chars,size))
    
    # alloc mem
    mem = self.alloc.alloc_memory("ReadArgs(@%06x)" % self.get_callee_pc(ctx),size)
    
    # fill mem
    addr = mem.addr
    char_ptr = addr + num_longs * 4
    long_ptr = addr
    base_ptr = array_ptr
    for i in xrange(n):
      r = result[i]
      if r == None: # optional value not set ('k')
        base_val = 0
      elif type(r) is types.StringType:
        # pointer to string
        base_val = char_ptr
        # append string
        mem.w_cstr(char_ptr, r)
        char_ptr += len(r) + 1        
      elif type(r) is types.IntType:
        # pointer to long
        base_val = long_ptr
        # write long
        mem.write_mem(2,long_ptr,r)
        long_ptr += 4
      elif type(r) is types.ListType:
        # pointer to array
        base_val = long_ptr
        # array with longs + strs
        for s in r:
          mem.write_mem(2,long_ptr,char_ptr)
          mem.w_cstr(char_ptr,s)
          long_ptr += 4
          char_ptr += len(s) + 1
        mem.write_mem(2,long_ptr,0)
        long_ptr += 4
      else:
        # direct value
        base_val = r
      
      ctx.mem.write_mem(2,base_ptr,base_val)
      base_ptr += 4
    
    # TODO: return real RDArgs
    return mem.addr
    
  def FreeArgs(self, mem_lib, ctx):
    rdargs_ptr = ctx.cpu.r_reg(REG_D1)
    self.trace_log("FreeArgs: %06x" % rdargs_ptr)
    mem = self.alloc.get_range_by_addr(rdargs_ptr)
    if mem == None:
      self.trace_log("NOT FOUND?!")
    else:
      self.alloc.free_memory(mem)

