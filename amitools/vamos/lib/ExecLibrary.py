from amitools.vamos.AmigaLibrary import *
from lexec.ExecStruct import *
from amitools.vamos.Log import log_exec
from amitools.vamos.Exceptions import *
from amitools.vamos.AccessStruct import AccessStruct
from lexec.PortManager import PortManager
from lexec.Pool import Pool
import dos.Printf

class ExecLibrary(AmigaLibrary):
  name = "exec.library"
  _pools = {}
  _poolid = 0x1000

  def __init__(self, lib_mgr, alloc, config):
    AmigaLibrary.__init__(self, self.name, ExecLibraryDef, config)
    log_exec.info("open exec.library V%d", self.version)
    self.lib_mgr = lib_mgr
    self.alloc = alloc
    self._pools = {}
    self._poolid = 0x1000

  def setup_lib(self, ctx):
    # set some system contants
    if ctx.cpu_type == '68020':
      self.access.w_s("AttnFlags",2)
    else:
      self.access.w_s("AttnFlags",0)
    self.access.w_s("MaxLocMem", ctx.ram_size)
    # create the port manager
    self.port_mgr = PortManager(ctx.alloc)

  def finish_lib(self, ctx):
    pass

  def set_this_task(self, process):
    self.access.w_s("ThisTask",process.this_task.addr)
    self.stk_lower = process.stack_base
    self.stk_upper = process.stack_end

  # ----- System -----

  def Disable(self, ctx):
    log_exec.info("Disable")
  def Enable(self, ctx):
    log_exec.info("Enable")
  def Forbid(self, ctx):
    log_exec.info("Forbid")
  def Permit(self, ctx):
    log_exec.info("Permit")

  def FindTask(self, ctx):
    task_ptr = ctx.cpu.r_reg(REG_A1)
    if task_ptr == 0:
      addr = self.access.r_s("ThisTask")
      log_exec.info("FindTask: me=%06x" % addr)
      return addr
    else:
      task_name = ctx.mem.access.r_cstr(task_ptr)
      log_exec.info("Find Task: %s" % task_name)
      raise UnsupportedFeatureError("FindTask: other task!");

  def SetSignal(self, ctx):
    new_signals = ctx.cpu.r_reg(REG_D0)
    signal_mask = ctx.cpu.r_reg(REG_D1)
    old_signals = 0
    log_exec.info("SetSignals: new_signals=%08x signal_mask=%08x old_signals=%08x" % (new_signals, signal_mask, old_signals))
    return old_signals

  def StackSwap(self, ctx):
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
    # is a label attached to new addr
    label = ctx.label_mgr.get_label(new_lower)
    if label is not None:
      label.name = label.name + "=Stack"
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

  def OpenLibrary(self, ctx):
    ver = ctx.cpu.r_reg(REG_D0)
    name_ptr = ctx.cpu.r_reg(REG_A1)
    name = ctx.mem.access.r_cstr(name_ptr)
    lib = self.lib_mgr.open_lib(name, ver, ctx)
    log_exec.info("OpenLibrary: '%s' V%d -> %s" % (name, ver, lib))
    if lib == None:
      return 0
    else:
      return lib.addr_base_open

  def OldOpenLibrary(self, ctx):
    name_ptr = ctx.cpu.r_reg(REG_A1)
    name = ctx.mem.access.r_cstr(name_ptr)
    lib = self.lib_mgr.open_lib(name, 0, ctx)
    log_exec.info("OldOpenLibrary: '%s' -> %s" % (name, lib))
    return lib.addr_base_open

  def CloseLibrary(self, ctx):
    lib_addr = ctx.cpu.r_reg(REG_A1)
    lib = self.lib_mgr.close_lib(lib_addr,ctx)
    if lib != None:
      log_exec.info("CloseLibrary: '%s' -> %06x" % (lib, lib.addr_base))
    else:
      raise VamosInternalError("CloseLibrary: Unknown library to close: ptr=%06x" % lib_addr)

  def FindResident(self, ctx):
    name_ptr = ctx.cpu.r_reg(REG_A1)
    name = ctx.mem.access.r_cstr(name_ptr)
    log_exec.info("FindResident: '%s'" % (name))
    return 0

  def CreatePool(self, ctx):
    # need some sort of uniq id.
    # HACK: this is a hack to produce private uniq ids
    poolid = self._poolid
    self._poolid += 4;
    flags = ctx.cpu.r_reg(REG_D0);
    size = ctx.cpu.r_reg(REG_D1);
    thresh = ctx.cpu.r_reg(REG_D2)
    pool = Pool(self.alloc, flags, size, thresh)
    self._pools[poolid] = pool
    return poolid

  def AllocPooled(self, ctx):
    poolid = ctx.cpu.r_reg(REG_A0)
    size = ctx.cpu.r_reg(REG_D0)
    pc = self.get_callee_pc(ctx)
    tag = ctx.label_mgr.get_mem_str(pc)
    name = "AllocPooled(%06x = %s)" % (pc,tag)
    pool = self._pools[poolid]
    if pool is not None:
      return pool.AllocPooled(name, size)
    else:
      raise VamosInternalError("AllocPooled: invalid memory pool: ptr=%06x" % poolid)

  def DeletePool(self, ctx):
    log_exec.info("DeletePool")
    poolid = ctx.cpu.r_reg(REG_A0)
    pool = self._pools[poolid]
    del self._pools[poolid]
    if pool is not None:
      del pool

  # ----- Memory Handling -----

  def AllocMem(self, ctx):
    size = ctx.cpu.r_reg(REG_D0)
    flags = ctx.cpu.r_reg(REG_D1)
    # label alloc
    pc = self.get_callee_pc(ctx)
    tag = ctx.label_mgr.get_mem_str(pc)
    name = "AllocMem(%06x = %s)" % (pc,tag)
    mb = self.alloc.alloc_memory(name,size)
    log_exec.info("AllocMem: %s" % mb)
    return mb.addr

  def FreeMem(self, ctx):
    size = ctx.cpu.r_reg(REG_D0)
    addr = ctx.cpu.r_reg(REG_A1)
    if addr == 0 or size == 0:
      log_exec.info("FreeMem: freeing NULL")
      return
    mb = self.alloc.get_memory(addr)
    if mb != None:
      log_exec.info("FreeMem: %s" % mb)
      self.alloc.free_memory(mb)
    else:
      raise VamosInternalError("FreeMem: Unknown memory to free: ptr=%06x size=%06x" % (addr, size))

  def AllocVec(self, ctx):
    size = ctx.cpu.r_reg(REG_D0)
    flags = ctx.cpu.r_reg(REG_D1)
    mb = self.alloc.alloc_memory("AllocVec(@%06x)" % self.get_callee_pc(ctx),size)
    log_exec.info("AllocVec: %s" % mb)
    return mb.addr

  def FreeVec(self, ctx):
    addr = ctx.cpu.r_reg(REG_A1)
    if addr == 0:
      log_exec.info("FreeVec: freeing NULL")
      return
    mb = self.alloc.get_memory(addr)
    if mb != None:
      log_exec.info("FreeVec: %s" % mb)
      self.alloc.free_memory(mb)
    else:
      raise VamosInternalError("FreeVec: Unknown memory to free: ptr=%06x" % (addr))

  # ----- Misc -----

  def RawDoFmt(self, ctx):
    format_ptr = ctx.cpu.r_reg(REG_A0)
    format     = ctx.mem.access.r_cstr(format_ptr)
    data_ptr   = ctx.cpu.r_reg(REG_A1)
    putch_ptr  = ctx.cpu.r_reg(REG_A2)
    pdata_ptr  = ctx.cpu.r_reg(REG_A3)
    log_exec.info("RawDoFmt: format='%s' data=%06x putch=%06x pdata=%06x" % (format, data_ptr, putch_ptr, pdata_ptr))

  # ----- Message Passing -----

  def PutMsg(self, ctx):
    port_addr = ctx.cpu.r_reg(REG_A0)
    msg_addr = ctx.cpu.r_reg(REG_A1)
    log_exec.info("PutMsg: port=%06x msg=%06x" % (port_addr, msg_addr))
    has_port = self.port_mgr.has_port(port_addr)
    if not has_port:
      raise VamosInternalError("PutMsg: on invalid Port (%06x) called!" % port_addr)
    self.port_mgr.put_msg(port_addr, msg_addr)

  def GetMsg(self, ctx):
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

  def WaitPort(self, ctx):
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

  def AddTail(self, ctx):
    list_addr = ctx.cpu.r_reg(REG_A0)
    node_addr = ctx.cpu.r_reg(REG_A1)
    log_exec.info("AddTail(%06x, %06x)" % (list_addr, node_addr))
    l = AccessStruct(ctx.mem, ListDef, list_addr)
    n = AccessStruct(ctx.mem, NodeDef, node_addr)
    n.w_s("ln_Succ", l.s_get_addr("lh_Tail"))
    tp = l.r_s("lh_TailPred")
    n.w_s("ln_Pred", tp)
    AccessStruct(ctx.mem, NodeDef, tp).w_s("ln_Succ", node_addr)
    l.w_s("lh_TailPred", node_addr)

  def AddHead(self, ctx):
    list_addr = ctx.cpu.r_reg(REG_A0)
    node_addr = ctx.cpu.r_reg(REG_A1)
    log_exec.info("AddHead(%06x, %06x)" % (list_addr, node_addr))
    l = AccessStruct(ctx.mem, ListDef, list_addr)
    n = AccessStruct(ctx.mem, NodeDef, node_addr)
    n.w_s("ln_Pred", l.s_get_addr("lh_TailPred"))
    h = l.r_s("lh_Head")
    n.w_s("ln_Succ", h)
    AccessStruct(ctx.mem, NodeDef, h).w_s("ln_Pred", node_addr)
    l.w_s("lh_Head", node_addr)

  def Remove(self, ctx):
    node_addr = ctx.cpu.r_reg(REG_A1)
    n = AccessStruct(ctx.mem, NodeDef, node_addr)
    succ = n.r_s("ln_Succ")
    pred = n.r_s("ln_Pred")
    log_exec.info("Remove(%06x): ln_Pred=%06x ln_Succ=%06x" % (node_addr, pred, succ))
    AccessStruct(ctx.mem, NodeDef, pred).w_s("ln_Succ", succ)
    AccessStruct(ctx.mem, NodeDef, succ).w_s("ln_Pred", pred)
    return node_addr

  def RemHead(self, ctx):
    list_addr = ctx.cpu.r_reg(REG_A0)
    l = AccessStruct(ctx.mem, ListDef, list_addr)
    node_addr = l.r_s("lh_Head")
    n = AccessStruct(ctx.mem, NodeDef, node_addr)
    succ = n.r_s("ln_Succ")
    pred = n.r_s("ln_Pred")
    if succ == 0:
      log_exec.info("RemHead(%06x): null" % list_addr)
      return 0
    AccessStruct(ctx.mem, NodeDef, pred).w_s("ln_Succ", succ)
    AccessStruct(ctx.mem, NodeDef, succ).w_s("ln_Pred", pred)
    log_exec.info("RemHead(%06x): %06x" % (list_addr, node_addr))
    return node_addr
  
  def RemTail(self, ctx):
    list_addr = ctx.cpu.r_reg(REG_A0)
    l = AccessStruct(ctx.mem, ListDef, list_addr)
    node_addr = l.r_s("lh_TailPred")
    n = AccessStruct(ctx.mem, NodeDef, node_addr)
    succ = n.r_s("ln_Succ")
    pred = n.r_s("ln_Pred")
    if pred == 0:
      log_exec.info("RemTail(%06x): null" % list_addr)
      return 0
    AccessStruct(ctx.mem, NodeDef, pred).w_s("ln_Succ", succ)
    AccessStruct(ctx.mem, NodeDef, succ).w_s("ln_Pred", pred)
    log_exec.info("RemTail(%06x): %06x" % (list_addr, node_addr))
    return node_addr

  def CopyMem(self, ctx):
    source = ctx.cpu.r_reg(REG_A0)
    dest   = ctx.cpu.r_reg(REG_A1)
    length = ctx.cpu.r_reg(REG_D0)
    log_exec.info("CopyMem: source=%06x dest=%06x len=%06x" % (source,dest,length))
    ctx.mem.raw_mem.copy_block(source, dest, length)

  def CopyMemQuick(self, ctx):
    source = ctx.cpu.r_reg(REG_A0)
    dest   = ctx.cpu.r_reg(REG_A1)
    length = ctx.cpu.r_reg(REG_D0)
    log_exec.info("CopyMemQuick: source=%06x dest=%06x len=%06x" % (source,dest,length))
    ctx.mem.raw_mem.copy_block(source, dest, length)

  def TypeOfMem(self, ctx):
    addr = ctx.cpu.r_reg(REG_A1)
    log_exec.info("TypeOfMem: source=%06x -> %s" % (addr,self.alloc.is_valid_address(addr)))
    if self.alloc.is_valid_address(addr):
      return 1 #MEMF_PUBLIC
    return 0

  def RawDoFmt(self, ctx):
    fmtString  = ctx.cpu.r_reg(REG_A0)
    dataStream = ctx.cpu.r_reg(REG_A1)
    putProc    = ctx.cpu.r_reg(REG_A2)
    putData    = ctx.cpu.r_reg(REG_A3)
    fmt        = ctx.mem.access.r_cstr(fmtString)
    # If the putProc is the typical move.b d0,(a3)+:rts, then place the data formatted in the output
    # buffer. Otherwise, we would need to run a Trampoline.
    putproc    = ctx.mem.access.r32(putProc)
    valid      = False
    if putproc == 0x16c04e75:
      valid    = True
    elif putproc == 0x4e55fffc: #link #-4,a5
      putproc2 = ctx.mem.access.r32(putProc+4)
      putproc3 = ctx.mem.access.r32(putProc+8)
      putproc4 = ctx.mem.access.r16(putProc+12)
      if putproc2 == 0x2b40fffc and putproc3 == 0x16c04e5d and putproc4 == 0x4e75:
        valid = True
    if not valid:
      log_exec.warn("RawDoFmt: unsupported PutProc: fmtString=%s putProc=%06x(%08lx)" % (fmt,putProc,putproc))
      # This should really run a trampoline instead.
      return dataStream
    ps = dos.Printf.printf_parse_string(fmt)
    dataStream = dos.Printf.printf_read_data(ps, ctx.mem.access, dataStream)
    result = dos.Printf.printf_generate_output(ps)
    ctx.mem.access.w_cstr(putData,result)
    log_exec.info("RawDoFmt: fmtString=%s -> %s" % (fmt,result))
    return dataStream
