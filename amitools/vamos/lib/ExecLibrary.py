from amitools.vamos.AmigaLibrary import *
from lexec.ExecStruct import *
from amitools.vamos.Log import log_exec
from amitools.vamos.Exceptions import *
from amitools.vamos.AccessStruct import AccessStruct

class ExecLibrary(AmigaLibrary):
  name = "exec.library"
  exec_calls = (
    (30, 'Supervisor', (('userFunction', 'a5'),)),
    (36, 'execPrivate1', None),
    (42, 'execPrivate2', None),
    (48, 'execPrivate3', None),
    (54, 'execPrivate4', None),
    (60, 'execPrivate5', None),
    (66, 'execPrivate6', None),
    (72, 'InitCode', (('startClass', 'd0'), ('version', 'd1'))),
    (78, 'InitStruct', (('initTable', 'a1'), ('memory', 'a2'), ('size', 'd0'))),
    (84, 'MakeLibrary', (('funcInit', 'a0'), ('structInit', 'a1'), ('libInit', 'a2'), ('dataSize', 'd0'), ('segList', 'd1'))),
    (90, 'MakeFunctions', (('target', 'a0'), ('functionArray', 'a1'), ('funcDispBase', 'a2'))),
    (96, 'FindResident', (('name', 'a1'),)),
    (102, 'InitResident', (('resident', 'a1'), ('segList', 'd1'))),
    (108, 'Alert', (('alertNum', 'd7'),)),
    (114, 'Debug', (('flags', 'd0'),)),
    (120, 'Disable', None),
    (126, 'Enable', None),
    (132, 'Forbid', None),
    (138, 'Permit', None),
    (144, 'SetSR', (('newSR', 'd0'), ('mask', 'd1'))),
    (150, 'SuperState', None),
    (156, 'UserState', (('sysStack', 'd0'),)),
    (162, 'SetIntVector', (('intNumber', 'd0'), ('interrupt', 'a1'))),
    (168, 'AddIntServer', (('intNumber', 'd0'), ('interrupt', 'a1'))),
    (174, 'RemIntServer', (('intNumber', 'd0'), ('interrupt', 'a1'))),
    (180, 'Cause', (('interrupt', 'a1'),)),
    (186, 'Allocate', (('freeList', 'a0'), ('byteSize', 'd0'))),
    (192, 'Deallocate', (('freeList', 'a0'), ('memoryBlock', 'a1'), ('byteSize', 'd0'))),
    (198, 'AllocMem', (('byteSize', 'd0'), ('requirements', 'd1'))),
    (204, 'AllocAbs', (('byteSize', 'd0'), ('location', 'a1'))),
    (210, 'FreeMem', (('memoryBlock', 'a1'), ('byteSize', 'd0'))),
    (216, 'AvailMem', (('requirements', 'd1'),)),
    (222, 'AllocEntry', (('entry', 'a0'),)),
    (228, 'FreeEntry', (('entry', 'a0'),)),
    (234, 'Insert', (('list', 'a0'), ('node', 'a1'), ('pred', 'a2'))),
    (240, 'AddHead', (('list', 'a0'), ('node', 'a1'))),
    (246, 'AddTail', (('list', 'a0'), ('node', 'a1'))),
    (252, 'Remove', (('node', 'a1'),)),
    (258, 'RemHead', (('list', 'a0'),)),
    (264, 'RemTail', (('list', 'a0'),)),
    (270, 'Enqueue', (('list', 'a0'), ('node', 'a1'))),
    (276, 'FindName', (('list', 'a0'), ('name', 'a1'))),
    (282, 'AddTask', (('task', 'a1'), ('initPC', 'a2'), ('finalPC', 'a3'))),
    (288, 'RemTask', (('task', 'a1'),)),
    (294, 'FindTask', (('name', 'a1'),)),
    (300, 'SetTaskPri', (('task', 'a1'), ('priority', 'd0'))),
    (306, 'SetSignal', (('newSignals', 'd0'), ('signalSet', 'd1'))),
    (312, 'SetExcept', (('newSignals', 'd0'), ('signalSet', 'd1'))),
    (318, 'Wait', (('signalSet', 'd0'),)),
    (324, 'Signal', (('task', 'a1'), ('signalSet', 'd0'))),
    (330, 'AllocSignal', (('signalNum', 'd0'),)),
    (336, 'FreeSignal', (('signalNum', 'd0'),)),
    (342, 'AllocTrap', (('trapNum', 'd0'),)),
    (348, 'FreeTrap', (('trapNum', 'd0'),)),
    (354, 'AddPort', (('port', 'a1'),)),
    (360, 'RemPort', (('port', 'a1'),)),
    (366, 'PutMsg', (('port', 'a0'), ('message', 'a1'))),
    (372, 'GetMsg', (('port', 'a0'),)),
    (378, 'ReplyMsg', (('message', 'a1'),)),
    (384, 'WaitPort', (('port', 'a0'),)),
    (390, 'FindPort', (('name', 'a1'),)),
    (396, 'AddLibrary', (('library', 'a1'),)),
    (402, 'RemLibrary', (('library', 'a1'),)),
    (408, 'OldOpenLibrary', (('libName', 'a1'),)),
    (414, 'CloseLibrary', (('library', 'a1'),)),
    (420, 'SetFunction', (('library', 'a1'), ('funcOffset', 'a0'), ('newFunction', 'd0'))),
    (426, 'SumLibrary', (('library', 'a1'),)),
    (432, 'AddDevice', (('device', 'a1'),)),
    (438, 'RemDevice', (('device', 'a1'),)),
    (444, 'OpenDevice', (('devName', 'a0'), ('unit', 'd0'), ('ioRequest', 'a1'), ('flags', 'd1'))),
    (450, 'CloseDevice', (('ioRequest', 'a1'),)),
    (456, 'DoIO', (('ioRequest', 'a1'),)),
    (462, 'SendIO', (('ioRequest', 'a1'),)),
    (468, 'CheckIO', (('ioRequest', 'a1'),)),
    (474, 'WaitIO', (('ioRequest', 'a1'),)),
    (480, 'AbortIO', (('ioRequest', 'a1'),)),
    (486, 'AddResource', (('resource', 'a1'),)),
    (492, 'RemResource', (('resource', 'a1'),)),
    (498, 'OpenResource', (('resName', 'a1'),)),
    (504, 'execPrivate7', None),
    (510, 'execPrivate8', None),
    (516, 'execPrivate9', None),
    (522, 'RawDoFmt', (('formatString', 'a0'), ('dataStream', 'a1'), ('putChProc', 'a2'), ('putChData', 'a3'))),
    (528, 'GetCC', None),
    (534, 'TypeOfMem', (('address', 'a1'),)),
    (540, 'Procure', (('sigSem', 'a0'), ('bidMsg', 'a1'))),
    (546, 'Vacate', (('sigSem', 'a0'), ('bidMsg', 'a1'))),
    (552, 'OpenLibrary', (('libName', 'a1'), ('version', 'd0'))),
    (558, 'InitSemaphore', (('sigSem', 'a0'),)),
    (564, 'ObtainSemaphore', (('sigSem', 'a0'),)),
    (570, 'ReleaseSemaphore', (('sigSem', 'a0'),)),
    (576, 'AttemptSemaphore', (('sigSem', 'a0'),)),
    (582, 'ObtainSemaphoreList', (('sigSem', 'a0'),)),
    (588, 'ReleaseSemaphoreList', (('sigSem', 'a0'),)),
    (594, 'FindSemaphore', (('sigSem', 'a1'),)),
    (600, 'AddSemaphore', (('sigSem', 'a1'),)),
    (606, 'RemSemaphore', (('sigSem', 'a1'),)),
    (612, 'SumKickData', None),
    (618, 'AddMemList', (('size', 'd0'), ('attributes', 'd1'), ('pri', 'd2'), ('base', 'a0'), ('name', 'a1'))),
    (624, 'CopyMem', (('source', 'a0'), ('dest', 'a1'), ('size', 'd0'))),
    (630, 'CopyMemQuick', (('source', 'a0'), ('dest', 'a1'), ('size', 'd0'))),
    (636, 'CacheClearU', None),
    (642, 'CacheClearE', (('address', 'a0'), ('length', 'd0'), ('caches', 'd1'))),
    (648, 'CacheControl', (('cacheBits', 'd0'), ('cacheMask', 'd1'))),
    (654, 'CreateIORequest', (('port', 'a0'), ('size', 'd0'))),
    (660, 'DeleteIORequest', (('iorequest', 'a0'),)),
    (666, 'CreateMsgPort', None),
    (672, 'DeleteMsgPort', (('port', 'a0'),)),
    (678, 'ObtainSemaphoreShared', (('sigSem', 'a0'),)),
    (684, 'AllocVec', (('byteSize', 'd0'), ('requirements', 'd1'))),
    (690, 'FreeVec', (('memoryBlock', 'a1'),)),
    (696, 'CreatePool', (('requirements', 'd0'), ('puddleSize', 'd1'), ('threshSize', 'd2'))),
    (702, 'DeletePool', (('poolHeader', 'a0'),)),
    (708, 'AllocPooled', (('poolHeader', 'a0'), ('memSize', 'd0'))),
    (714, 'FreePooled', (('poolHeader', 'a0'), ('memory', 'a1'), ('memSize', 'd0'))),
    (720, 'AttemptSemaphoreShared', (('sigSem', 'a0'),)),
    (726, 'ColdReboot', None),
    (732, 'StackSwap', (('newStack', 'a0'),)),
    (738, 'ChildFree', (('tid', 'd0'),)),
    (744, 'ChildOrphan', (('tid', 'd0'),)),
    (750, 'ChildStatus', (('tid', 'd0'),)),
    (756, 'ChildWait', (('tid', 'd0'),)),
    (762, 'CachePreDMA', (('address', 'a0'), ('length', 'a1'), ('flags', 'd0'))),
    (768, 'CachePostDMA', (('address', 'a0'), ('length', 'a1'), ('flags', 'd0'))),
    (774, 'AddMemHandler', (('memhand', 'a1'),)),
    (780, 'RemMemHandler', (('memhand', 'a1'),)),
    (786, 'ObtainQuickVector', (('interruptCode', 'a0'),)),
    (792, 'execPrivate10', None),
    (798, 'execPrivate11', None),
    (804, 'execPrivate12', None),
    (810, 'execPrivate13', None),
    (816, 'execPrivate14', None),
    (822, 'execPrivate15', None),
  )

  def __init__(self, lib_mgr, alloc, version=39):
    AmigaLibrary.__init__(self, self.name, version, self.exec_calls, ExecLibraryDef)
    log_exec.info("open exec.library V%d", self.version)
    self.lib_mgr = lib_mgr
    self.alloc = alloc

    exec_funcs = (
      (408, self.OldOpenLibrary),
      (414, self.CloseLibrary),
      (552, self.OpenLibrary),
      (198, self.AllocMem),
      (210, self.FreeMem),
      (294, self.FindTask),
      (306, self.SetSignals),
      (366, self.PutMsg),
      (372, self.GetMsg),
      (384, self.WaitPort),
      (522, self.RawDoFmt),
      (684, self.AllocVec),
      (690, self.FreeVec),
      (732, self.StackSwap)
    )
    self.set_funcs(exec_funcs)
  
  def set_stack(self, lower, upper):
    self.stk_lower = lower
    self.stk_upper = upper
  
  def set_managers(self, port_mgr):
    self.port_mgr = port_mgr
  
  def setup_lib(self, lib, ctx):
    # setup exec memory
    lib.access.w_s("ThisTask",ctx.this_task.addr)
    lib.access.w_s("LibNode.lib_Version", self.version)
  
  # ----- System -----
  
  def FindTask(self, lib, ctx):
    task_ptr = ctx.cpu.r_reg(REG_A1)
    if task_ptr == 0:
      log_exec.info("FindTask: me=%06x" % ctx.this_task.addr)
      return ctx.this_task.addr
    else:
      task_name = ctx.mem.access.r_cstr(task_ptr)
      log_exec.info("Find Task: %s" % task_name)
      raise UnsupportedFeatureError("FindTask: other task!");
  
  def SetSignals(self, lib, ctx):
    new_signals = ctx.cpu.r_reg(REG_D0)
    signal_mask = ctx.cpu.r_reg(REG_D1)
    old_signals = 0
    log_exec.info("SetSignals: new_signals=%08x signal_mask=%08x old_signals=%08x" % (new_signals, signal_mask, old_signals))
    return old_signals
  
  def StackSwap(self, lib, ctx):
    stsw_ptr = ctx.cpu.r_reg(REG_A0)
    stsw = AccessStruct(ctx.mem,StackSwapDef,struct_addr=stsw_ptr)
    # get new stack values
    new_lower = stsw.r_s('stk_Lower')
    new_upper = stsw.r_s('stk_Upper')
    new_pointer = stsw.r_s('stk_Pointer')
    # retrieve current (old) stack
    old_lower = self.stk_lower
    old_upper = self.stk_upper
    old_pointer = ctx.cpu.r_reg(REG_A7) # addr of sys call return
    # get adress of callee
    callee = ctx.mem.access.r32(old_pointer)
    # we report the old stack befor callee
    old_pointer += 4
    log_exec.info("StackSwap: old(lower=%06x,upper=%06x,ptr=%06x) new(lower=%06x,upper=%06x,ptr=%06x)" % (old_lower,old_upper,old_pointer,new_lower,new_upper,new_pointer))
    stsw.w_s('stk_Lower', old_lower)
    stsw.w_s('stk_Upper', old_upper)
    stsw.w_s('stk_Pointer', old_pointer)
    self.stk_lower = new_lower
    self.stk_upper = new_upper
    # put callee's address on new stack
    new_pointer -= 4
    ctx.mem.access.w32(new_pointer,callee)
    # activate new stack
    ctx.cpu.w_reg(REG_A7, new_pointer)
    
  # ----- Libraries -----
  
  def OpenLibrary(self, lib, ctx):
    ver = ctx.cpu.r_reg(REG_D0)
    name_ptr = ctx.cpu.r_reg(REG_A1)
    name = ctx.mem.access.r_cstr(name_ptr)
    lib = self.lib_mgr.open_lib(name, ver, ctx)
    log_exec.info("OpenLibrary: '%s' V%d -> %s" % (name, ver, lib))
    if lib == None:
      return 0
    else:
      return lib.lib_base
  
  def OldOpenLibrary(self, lib, ctx):
    name_ptr = ctx.cpu.r_reg(REG_A1)
    name = ctx.mem.access.r_cstr(name_ptr)
    lib = self.lib_mgr.open_lib(name, 0, ctx)
    log_exec.info("OldOpenLibrary: '%s' -> %s" % (name, lib))
    return lib.lib_base
  
  def CloseLibrary(self, lib, ctx):
    lib_addr = ctx.cpu.r_reg(REG_A1)
    lib = self.lib_mgr.close_lib(lib_addr,ctx)
    if lib != None:
      log_exec.info("CloseLibrary: '%s' -> %06x" % (lib, lib.lib_base))
    else:
      raise VamosInternalError("CloseLibrary: Unknown library to close: ptr=%06x" % lib_addr)
  
  # ----- Memory Handling -----
  
  def AllocMem(self, lib, ctx):
    size = ctx.cpu.r_reg(REG_D0)
    flags = ctx.cpu.r_reg(REG_D1)
    # label alloc
    pc = self.get_callee_pc(ctx)
    tag = ctx.label_mgr.get_mem_str(pc)
    name = "AllocMem(%06x = %s)" % (pc,tag)
    mb = self.alloc.alloc_memory(name,size)
    log_exec.info("AllocMem: %s" % mb)
    return mb.addr
  
  def FreeMem(self, lib, ctx):
    size = ctx.cpu.r_reg(REG_D0)
    addr = ctx.cpu.r_reg(REG_A1)
    mb = self.alloc.get_memory(addr)
    if mb != None:
      log_exec.info("FreeMem: %s" % mb)
      self.alloc.free_memory(mb)
    else:
      raise VamosInternalError("FreeMem: Unknown memory to free: ptr=%06x size=%06x" % (addr, size))

  def AllocVec(self, lib, ctx):
    size = ctx.cpu.r_reg(REG_D0)
    flags = ctx.cpu.r_reg(REG_D1)
    mb = self.alloc.alloc_memory("AllocVec(@%06x)" % self.get_callee_pc(ctx),size)
    log_exec.info("AllocVec: %s" % mb)
    return mb.addr
    
  def FreeVec(self, lib, ctx):
    addr = ctx.cpu.r_reg(REG_A1)
    mb = self.alloc.get_memory(addr)
    if mb != None:
      log_exec.info("FreeVec: %s" % mb)
      self.alloc.free_memory(mb)
    else:
      raise VamosInternalError("FreeVec: Unknown memory to free: ptr=%06x" % (addr))
  
  # ----- Misc -----
  
  def RawDoFmt(self, lib, ctx):
    format_ptr = ctx.cpu.r_reg(REG_A0)
    format     = ctx.mem.access.r_cstr(format_ptr)
    data_ptr   = ctx.cpu.r_reg(REG_A1)
    putch_ptr  = ctx.cpu.r_reg(REG_A2)
    pdata_ptr  = ctx.cpu.r_reg(REG_A3)
    log_exec.info("RawDoFmt: format='%s' data=%06x putch=%06x pdata=%06x" % (format, data_ptr, putch_ptr, pdata_ptr))
  
  # ----- Message Passing -----
  
  def PutMsg(self, lib, ctx):
    port_addr = ctx.cpu.r_reg(REG_A0)
    msg_addr = ctx.cpu.r_reg(REG_A1)
    log_exec.info("PutMsg: port=%06x msg=%06x" % (port_addr, msg_addr))
    has_port = self.port_mgr.has_port(port_addr)
    if not has_port:
      raise VamosInternalError("PutMsg: on invalid Port (%06x) called!" % port_addr)
    self.port_mgr.put_msg(port_addr, msg_addr)
      
  def GetMsg(self, lib, ctx):
    port_addr = ctx.cpu.r_reg(REG_A0)
    log_exec.info("GetMsg: port=%06x" % (port_addr))
    has_port = self.port_mgr.has_port(port_addr)
    if not has_port:
      raise VamosInternalError("GetMsg: on invalid Port (%06x) called!" % port_addr)
    msg_addr = self.port_mgr.get_msg(port_addr)
    if msg_addr != None:
      log_exec.info("GetMsg: got message %06x" % (msg_addr))
      return msg_addr
    else:
      log_exec.info("GetMsg: no message available!")
      return 0
  
  def WaitPort(self, lib, ctx):
    port_addr = ctx.cpu.r_reg(REG_A0)
    log_exec.info("WaitPort: port=%06x" % (port_addr))
    has_port = self.port_mgr.has_port(port_addr)
    if not has_port:
      raise VamosInternalError("WaitPort: on invalid Port (%06x) called!" % port_addr)
    has_msg = self.port_mgr.has_msg(port_addr)
    if not has_msg:
      raise UnsupportedFeatureError("WaitPort on empty message queue called: Port (%06x)" % port_addr)
    msg_addr = self.port_mgr.get_msg(port_addr)
    log_exec.info("WaitPort: got message %06x" % (msg_addr))
    return msg_addr
