from amitools.vamos.AmigaLibrary import *
from amitools.vamos.structure.ExecStruct import ExecLibraryDef

class ExecLibrary(AmigaLibrary):
  
  _exec_calls = (
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

  def __init__(self, version, context, lib_mgr, alloc):
    AmigaLibrary.__init__(self,"exec.library", version, self._exec_calls, ExecLibraryDef, context)
    self.lib_mgr = lib_mgr
    self.alloc = alloc

    _exec_funcs = (
      (408, self.OldOpenLibrary),
      (414, self.CloseLibrary),
      (552, self.OpenLibrary),
      (198, self.AllocMem),
      (210, self.FreeMem)
    )
    self.set_funcs(_exec_funcs)
    
  def OpenLibrary(self):
    ver = self.cpu.r_reg(REG_D0)
    name_ptr = self.cpu.r_reg(REG_A1)
    name = self.mem.read_cstring(name_ptr)
    addr = self.lib_mgr.open_lib(name, ver)
    self.log("'%s' V%d -> %06x" % (name, ver, addr))
    return addr
  
  def OldOpenLibrary(self):
    name_ptr = self.cpu.r_reg(REG_A1)
    name = self.mem.read_cstring(name_ptr)
    addr = self.lib_mgr.open_lib(name, 0)
    self.log("'%s' -> %06x" % (name, addr))
    return addr
  
  def CloseLibrary(self):
    lib_addr = self.cpu.r_reg(REG_A1)
    lib = self.lib_mgr.close_lib(lib_addr)
    if lib != None:
      self.log("'%s' V%d -> %06x" % (lib.name, lib.version, lib_addr))
    else:
      self.log("INVALID")
  
  def AllocMem(self):
    size = self.cpu.r_reg(REG_D0)
    flags = self.cpu.r_reg(REG_D1)
    mb = self.alloc.allocMemory("AllocMem(@%06x)" % self.get_callee_pc(),size)
    self.log("flags=%08x" % flags)
    return mb.addr
  
  def FreeMem(self):
    size = self.cpu.r_reg(REG_D0)
    addr = self.cpu.r_reg(REG_A1)
    


