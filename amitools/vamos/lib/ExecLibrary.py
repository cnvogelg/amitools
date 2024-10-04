from amitools.vamos.astructs import AccessStruct
from amitools.vamos.error import VamosInternalError, UnsupportedFeatureError
from amitools.vamos.lib.intuition import IntuiMessageStruct
from amitools.vamos.libcore import LibImpl
from amitools.vamos.libnative import MakeFuncs, InitStruct, MakeLib, LibFuncs, InitRes
from amitools.vamos.libstructs import (
    ExecLibraryStruct,
    StackSwapStruct,
    IORequestStruct,
    ListStruct,
    NodeStruct,
    NodeType,
    SignalSemaphoreStruct,
    MsgPortStruct,
    MessageStruct,
)
from amitools.vamos.libtypes import ExecLibrary as ExecLibraryType
from amitools.vamos.libtypes import List
from amitools.vamos.log import log_exec
from amitools.vamos.machine.regs import REG_A7, REG_A1, REG_D0, REG_D1, REG_A0, REG_A2, REG_D2, REG_A3

from .lexec import Alloc
from .lexec.Pool import Pool
from .lexec.PortManager import PortManager
from .lexec.RawDoFmt import raw_do_fmt
from .lexec.SemaphoreManager import SemaphoreManager
import threading

class ExecLibrary(LibImpl):
    def get_struct_def(self):
        return ExecLibraryStruct

    def setup_lib(self, ctx, base_addr):
        log_exec.info("setup exec.library")
        self.lib_mgr = ctx.lib_mgr
        self.alloc = ctx.alloc
        self._pools = {}
        self._poolid = 0x1000
        self.exec_lib = ExecLibraryType(ctx.mem, base_addr)
        # init lib list
        self.exec_lib.lib_list.new_list(NodeType.NT_LIBRARY)
        self.exec_lib.device_list.new_list(NodeType.NT_DEVICE)
        # set some system contants
        attn_flags = 0
        if ctx.cpu_name == "68030(fake)":
            attn_flags = 7
        elif ctx.cpu_name == "68020":
            attn_flags = 3
        elif ctx.cpu_name == "68040":
            attn_flags = 127
        self.exec_lib.attn_flags.val = attn_flags
        self.exec_lib.max_loc_mem.val = ctx.ram_size
        # create the port manager
        self.port_mgr = PortManager(ctx.alloc)
        self.semaphore_mgr = SemaphoreManager(ctx.alloc, ctx.mem)
        self.mem = ctx.mem
        
        self.signals = 0
        self.intuition_lib = None
        
        self._msg_lock = threading.Lock()
        
        ctx.exec_lib = self

    def set_this_task(self, process):
        self.exec_lib.this_task.aptr = process.this_task.addr
        self.stk_lower = process.get_stack().get_lower()
        self.stk_upper = process.get_stack().get_upper()

    # helper

    def get_callee_pc(self, ctx):
        """a call stub log helper to extract the callee's pc"""
        sp = ctx.cpu.r_reg(REG_A7)
        return ctx.mem.r32(sp)

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
            addr = self.exec_lib.this_task.aptr
            log_exec.info("FindTask: me=%06x" % addr)
            return addr
        else:
            task_name = ctx.mem.r_cstr(task_ptr)
            log_exec.info("Find Task: %s" % task_name)
            raise UnsupportedFeatureError("FindTask: other task!")

    # ---------- 68k ABI entry points ----------

    def Signal(self, ctx):
        """
        Amiga: Signal(task, signal_mask)
        A1 = task address
        D0 = signal_mask
        Return value is undefined in AmigaOS.
        """
        task_addr   = ctx.cpu.r_reg(REG_A1)
        signal_mask = ctx.cpu.r_reg(REG_D0)

        self._signal_core(ctx, task_addr, signal_mask)
        # No defined return; leave D0 as-is or set if you want

    def Wait(self, ctx):
        """
        Amiga: received = Wait(mask)
        D0 = mask
        Returns received signal bits in D0.
        """
        mask = ctx.cpu.r_reg(REG_D0)
        received = self._wait_core(ctx, mask)
        ctx.cpu.w_reg(REG_D0, received)
        return received

    def SetSignal(self, ctx):
        """
        Amiga: old = SetSignal(new, mask)
        D0 = new signals
        D1 = mask
        Returns old signal state in D0.
        """
        new_signals = ctx.cpu.r_reg(REG_D0)
        signal_mask = ctx.cpu.r_reg(REG_D1)

        old_signals = self._set_signal_core(ctx, new_signals, signal_mask)

        ctx.cpu.w_reg(REG_D0, old_signals)
        return old_signals

    def StackSwap(self, ctx):
        stsw_ptr = ctx.cpu.r_reg(REG_A0)
        stsw = AccessStruct(ctx.mem, StackSwapStruct, struct_addr=stsw_ptr)
        # get new stack values
        new_lower = stsw.r_s("stk_Lower")
        new_upper = stsw.r_s("stk_Upper")
        new_pointer = stsw.r_s("stk_Pointer")
        # retrieve current (old) stack
        old_lower = self.stk_lower
        old_upper = self.stk_upper
        old_pointer = ctx.cpu.r_reg(REG_A7)  # addr of sys call return
        # get adress of callee
        callee = ctx.mem.r32(old_pointer)
        # is a label attached to new addr
        if ctx.label_mgr:
            label = ctx.label_mgr.get_label(new_lower)
            if label is not None:
                label.name = label.name + "=Stack"
        # we report the old stack befor callee
        old_pointer += 4
        log_exec.info(
            "StackSwap: old(lower=%06x,upper=%06x,ptr=%06x) new(lower=%06x,upper=%06x,ptr=%06x)"
            % (old_lower, old_upper, old_pointer, new_lower, new_upper, new_pointer)
        )
        stsw.w_s("stk_Lower", old_lower)
        stsw.w_s("stk_Upper", old_upper)
        stsw.w_s("stk_Pointer", old_pointer)
        self.stk_lower = new_lower
        self.stk_upper = new_upper
        # put callee's address on new stack
        new_pointer -= 4
        ctx.mem.w32(new_pointer, callee)
        # activate new stack
        ctx.cpu.w_reg(REG_A7, new_pointer)

    # ----- Libraries -----

    def MakeFunctions(self, ctx):
        target = ctx.cpu.r_reg(REG_A0)
        func_array = ctx.cpu.r_reg(REG_A1)
        func_disp = ctx.cpu.r_reg(REG_A2)
        log_exec.info(
            "MakeFunctions: target=%06x, func_array=%06x, func_disp=%06x",
            target,
            func_array,
            func_disp,
        )
        mf = MakeFuncs(ctx.mem)
        return mf.make_functions(target, func_array, func_disp)

    def InitStruct(self, ctx):
        init_tab = ctx.cpu.r_reg(REG_A1)
        memory = ctx.cpu.r_reg(REG_A2)
        size = ctx.cpu.r_reg(REG_D0)
        log_exec.info(
            "InitStruct: init_tab=%06x, memory=%06x, size=%06x", init_tab, memory, size
        )
        i = InitStruct(ctx.mem)
        i.init_struct(init_tab, memory, size)

    def MakeLibrary(self, ctx):
        vectors = ctx.cpu.r_reg(REG_A0)
        struct = ctx.cpu.r_reg(REG_A1)
        init = ctx.cpu.r_reg(REG_A2)
        dsize = ctx.cpu.r_reg(REG_D0)
        seglist = ctx.cpu.r_reg(REG_D1)
        ml = MakeLib(ctx.machine, ctx.alloc)
        lib_base, mobj = ml.make_library(vectors, struct, init, dsize, seglist)
        log_exec.info(
            "MakeLibrary: vectors=%06x, struct=%06x, init=%06x, "
            "dsize=%06x seglist=%06x -> lib_base=%06x, mobj=%s",
            vectors,
            struct,
            init,
            dsize,
            seglist,
            lib_base,
            mobj,
        )
        return lib_base

    def InitResident(self, ctx):
        resident = ctx.cpu.r_reg(REG_A1)
        seglist = ctx.cpu.r_reg(REG_D1)
        ir = InitRes(ctx.machine, ctx.alloc)
        base, mobj = ir.init_resident(resident, seglist)
        log_exec.info(
            "InitResident: res=%06x, seglist=%06x -> base=%06x, mobj=%s",
            resident,
            seglist,
            base,
            mobj,
        )
        return base

    def AddLibrary(self, ctx):
        lib_addr = ctx.cpu.r_reg(REG_A1)
        log_exec.info("AddLibrary: lib=%06x", lib_addr)
        lf = LibFuncs(ctx.machine, ctx.alloc)
        lf.add_library(lib_addr, exec_lib=self.exec_lib)

    def SumLibrary(self, ctx):
        lib_addr = ctx.cpu.r_reg(REG_A1)
        lf = LibFuncs(ctx.machine, ctx.alloc)
        lib_sum = lf.sum_library(lib_addr)
        log_exec.info("SumLibrary: lib=%06x -> sum=%08x", lib_addr, lib_sum)

    def SetFunction(self, ctx):
        lib_addr = ctx.cpu.r_reg(REG_A1)
        lvo = ctx.cpu.rs_reg(REG_A0)
        new_func = ctx.cpu.r_reg(REG_D0)
        lf = LibFuncs(ctx.machine, ctx.alloc)
        old_func = lf.set_function(lib_addr, lvo, new_func)
        log_exec.info(
            "SetFunction: lib=%06x, lvo=%d, new_func=%06x -> old_func=%06x",
            lib_addr,
            lvo,
            new_func,
            old_func,
        )
        return old_func

    def RemLibrary(self, ctx):
        lib_addr = ctx.cpu.r_reg(REG_A1)
        lf = LibFuncs(ctx.machine, ctx.alloc)
        seglist = lf.rem_library(lib_addr, ctx.seg_loader)
        log_exec.info("RemLibrary: lib=%06x -> seglist=%06x", lib_addr, seglist)

    def OpenLibrary(self, ctx):
        ver = ctx.cpu.r_reg(REG_D0)
        name_ptr = ctx.cpu.r_reg(REG_A1)
        name = ctx.mem.r_cstr(name_ptr)
        proc = ctx.process
        if proc:
            cwd = proc.get_current_dir_lock()
            pd = proc.get_home_dir_lock()
        else:
            cwd, pd = None, None
        addr = self.lib_mgr.open_lib(name, ver, cwd_lock=cwd, progdir_lock=pd)
        log_exec.info("OpenLibrary: '%s' V%d -> %06x", name, ver, addr)
        return addr

    def TaggedOpenLibrary(self, ctx):
        tag = ctx.cpu.r_reg(REG_D0)
        tags = [
            "graphics.library",
            "layers.library",
            "intuition.library",
            "dos.library",
            "icon.library",
            "expansion.library",
            "utility.library",
            "keymap.library",
            "gadtools.library",
            "workbench.library",
        ]
        if tag > 0 and tag <= len(tags):
            name = tags[tag - 1]
            addr = self.lib_mgr.open_lib(name, 0)
            log_exec.info("TaggedOpenLibrary: %d('%s') -> %06x", tag, name, addr)
            return addr
        else:
            log_exec.warning("TaggedOpenLibrary: %d invalid tag -> NULL" % tag)
            return 0

    def OldOpenLibrary(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_A1)
        name = ctx.mem.r_cstr(name_ptr)
        proc = ctx.process
        if proc:
            cwd = proc.get_current_dir_lock()
            pd = proc.get_home_dir_lock()
        else:
            cwd, pd = None, None
        addr = self.lib_mgr.open_lib(name, 0, cwd_lock=cwd, progdir_lock=pd)
        log_exec.info("OldOpenLibrary: '%s' -> %06x", name, addr)
        return addr

    def CloseLibrary(self, ctx):
        lib_addr = ctx.cpu.r_reg(REG_A1)
        if lib_addr != 0:
            log_exec.info("CloseLibrary: %06x", lib_addr)
            self.lib_mgr.close_lib(lib_addr)

    def FindResident(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_A1)
        name = ctx.mem.r_cstr(name_ptr)
        log_exec.info("FindResident: '%s'" % (name))
        return 0

    def CreatePool(self, ctx):
        # need some sort of uniq id.
        # HACK: this is a hack to produce private uniq ids
        poolid = self._poolid
        self._poolid += 4
        flags = ctx.cpu.r_reg(REG_D0)
        size = (ctx.cpu.r_reg(REG_D1) + 7) & -8
        thresh = ctx.cpu.r_reg(REG_D2)
        pool = Pool(self.mem, self.alloc, flags, size, thresh, poolid)
        self._pools[poolid] = pool
        log_exec.info("CreatePool: pool 0x%x" % poolid)
        return poolid

    def AllocPooled(self, ctx):
        poolid = ctx.cpu.r_reg(REG_A0)
        size = (ctx.cpu.r_reg(REG_D0) + 7) & -8
        pc = self.get_callee_pc(ctx)
        name = "AllocPooled(%06x)" % pc
        if poolid in self._pools:
            pool = self._pools[poolid]
            mem = pool.AllocPooled(ctx.label_mgr, name, size)
            log_exec.info(
                "AllocPooled: from pool 0x%x size %d -> 0x%06x"
                % (poolid, size, mem.addr)
            )
            return mem.addr
        else:
            raise VamosInternalError(
                "AllocPooled: invalid memory pool: ptr=%06x" % poolid
            )

    def FreePooled(self, ctx):
        poolid = ctx.cpu.r_reg(REG_A0)
        size = (ctx.cpu.r_reg(REG_D0) + 7) & -8
        mem_ptr = ctx.cpu.r_reg(REG_A1)
        if poolid in self._pools:
            pool = self._pools[poolid]
            pool.FreePooled(mem_ptr, size)
            log_exec.info(
                "FreePooled: to pool 0x%x mem 0x%06x size %d" % (poolid, mem_ptr, size)
            )
        else:
            raise VamosInternalError(
                "FreePooled: invalid memory pool: ptr=%06x" % poolid
            )

    def DeletePool(self, ctx):
        log_exec.info("DeletePool")
        poolid = ctx.cpu.r_reg(REG_A0)
        if poolid in self._pools:
            pool = self._pools[poolid]
            del self._pools[poolid]
            pool.__del__()
            log_exec.info("DeletePooled: pool 0x%x" % poolid)
        else:
            raise VamosInternalError(
                "DeletePooled: invalid memory pool: ptr=%06x" % poolid
            )

    # ----- Memory Handling -----

    def AllocMem(self, ctx):
        size = ctx.cpu.r_reg(REG_D0)
        #flags = ctx.cpu.r_reg(REG_D1) # always cleared
        # label alloc
        pc = self.get_callee_pc(ctx)
        name = "AllocMem(%06x)" % pc
        mb = self.alloc.alloc_memory(size, label=name)
        log_exec.info("AllocMem: %s -> 0x%06x %d bytes" % (mb, mb.addr, size))
        return mb.addr

    def FreeMem(self, ctx):
        size = ctx.cpu.r_reg(REG_D0)
        addr = ctx.cpu.r_reg(REG_A1)
        if addr == 0 or size == 0:
            log_exec.info("FreeMem: freeing NULL")
            return
        mb = self.alloc.get_memory(addr)
        if mb != None:
            log_exec.info("FreeMem: 0x%06x %d bytes -> %s" % (addr, size, mb))
            self.alloc.free_memory(mb)
        else:
            raise VamosInternalError(
                "FreeMem: Unknown memory to free: ptr=%06x size=%06x" % (addr, size)
            )

    def AllocVec(self, ctx):
        size = ctx.cpu.r_reg(REG_D0)
        flags = ctx.cpu.r_reg(REG_D1)
        name = "AllocVec(@%06x)" % self.get_callee_pc(ctx)
        mb = self.alloc.alloc_memory(size, label=name)
        log_exec.info("AllocVec: %s, flags=%08x", name, flags)
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
            raise VamosInternalError(
                "FreeVec: Unknown memory to free: ptr=%06x" % (addr)
            )

    def AvailMem(self, ctx):
        reqments = ctx.cpu.r_reg(REG_D1)
        if reqments & 2:
            return 0  # no chip memory
        if reqments & (1 << 17):
            return self.alloc.largest_chunk()
        elif reqments & (1 << 19):
            return self.alloc.total()
        else:
            return self.alloc.available()

    # ----- Message Passing -----
    # ----- 68k ABI entry points -----

    def PutMsg(self, ctx):
        port_addr = ctx.cpu.r_reg(REG_A0)
        msg_addr  = ctx.cpu.r_reg(REG_A1)
        self._put_msg_core(ctx, port_addr, msg_addr)

    def GetMsg(self, ctx):
        port_addr = ctx.cpu.r_reg(REG_A0)
        msg_addr  = self._get_msg_core(ctx, port_addr)
        ctx.cpu.w_reg(REG_D0, msg_addr)
        return msg_addr

    def ReplyMsg(self, ctx):
        msg_addr = ctx.cpu.r_reg(REG_A1)
        result   = self._reply_msg_core(ctx, msg_addr)
        ctx.cpu.w_reg(REG_D0, result)
        return result

    def CreateMsgPort(self, ctx):
        port = self.port_mgr.create_port("exec_port", None)
        log_exec.info("CreateMsgPort: -> port=%06x" % (port))
        return port

    def DeleteMsgPort(self, ctx):
        port = ctx.cpu.r_reg(REG_A0)
        log_exec.info("DeleteMsgPort(%06x)" % port)
        self.port_mgr.free_port(port)
        return 0

    def CreateIORequest(self, ctx):
        port = ctx.cpu.r_reg(REG_A0)
        size = ctx.cpu.r_reg(REG_D0)
        # label alloc
        pc = self.get_callee_pc(ctx)
        name = "CreateIORequest(%06x)" % pc
        mb = self.alloc.alloc_memory(size, label=name)
        log_exec.info(
            "CreateIORequest: (%s,%s,%s) -> 0x%06x %d bytes"
            % (mb, port, size, mb.addr, size)
        )
        return mb.addr

    def DeleteIORequest(self, ctx):
        req = ctx.cpu.r_reg(REG_A0)
        mb = self.alloc.get_memory(req)
        if mb != None:
            log_exec.info("DeleteIOREquest: 0x%06x -> %s" % (req, mb))
            self.alloc.free_memory(mb)
        else:
            raise VamosInternalError(
                "DeleteIORequest: Unknown IORequest to delete: ptr=%06x" % req
            )

    def OpenDevice(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_A0)
        unit = ctx.cpu.r_reg(REG_D0)
        io_addr = ctx.cpu.r_reg(REG_A1)
        io = AccessStruct(ctx.mem, IORequestStruct, io_addr)
        flags = ctx.cpu.r_reg(REG_D1)
        name = ctx.mem.r_cstr(name_ptr)
        addr = self.lib_mgr.open_lib(name)
        io.w_s("io_Device", addr)
        if addr == 0:
            log_exec.info(
                "OpenDevice: '%s' unit %d flags %d -> NULL", name, unit, flags
            )
            return -1
        else:
            log_exec.info(
                "OpenDevice: '%s' unit %d flags %d -> %06x", name, unit, flags, addr
            )
            return 0

    def CloseDevice(self, ctx):
        io_addr = ctx.cpu.r_reg(REG_A1)
        if io_addr != 0:
            io = AccessStruct(ctx.mem, IORequestStruct, io_addr)
            dev_addr = io.r_s("io_Device")
            if dev_addr != 0:
                log_exec.info("CloseDevice: %06x", dev_addr)
                self.lib_mgr.close_lib(dev_addr)
                io.w_s("io_Device", 0)

    def WaitPort(self, ctx):
        port_addr = ctx.cpu.r_reg(REG_A0)
        log_exec.info("WaitPort: port=%06x" % (port_addr))
        has_port = self.port_mgr.has_port(port_addr)
        if not has_port:
            raise VamosInternalError(
                "WaitPort: on invalid Port (%06x) called!" % port_addr
            )
        has_msg = self.port_mgr.has_msg(port_addr)
        if not has_msg:
            mp = MsgPortStruct(ctx.mem, port_addr)            
            self._wait_core(ctx, 1 << mp.mp_SigBit.get())
            
        msg_addr = self.port_mgr.get_msg(port_addr)
        log_exec.info("WaitPort: got message %06x" % (msg_addr))
        return msg_addr

    def AddTail(self, ctx):
        list_addr = ctx.cpu.r_reg(REG_A0)
        node_addr = ctx.cpu.r_reg(REG_A1)
        log_exec.info("AddTail(%06x, %06x)" % (list_addr, node_addr))
        l = AccessStruct(ctx.mem, ListStruct, list_addr)
        n = AccessStruct(ctx.mem, NodeStruct, node_addr)
        n.w_s("ln_Succ", l.s_get_addr("lh_Tail"))
        tp = l.r_s("lh_TailPred")
        n.w_s("ln_Pred", tp)
        AccessStruct(ctx.mem, NodeStruct, tp).w_s("ln_Succ", node_addr)
        l.w_s("lh_TailPred", node_addr)

    def AddHead(self, ctx):
        list_addr = ctx.cpu.r_reg(REG_A0)
        node_addr = ctx.cpu.r_reg(REG_A1)
        log_exec.info("AddHead(%06x, %06x)" % (list_addr, node_addr))
        l = AccessStruct(ctx.mem, ListStruct, list_addr)
        n = AccessStruct(ctx.mem, NodeStruct, node_addr)
        n.w_s("ln_Pred", l.s_get_addr("lh_Head"))
        h = l.r_s("lh_Head")
        n.w_s("ln_Succ", h)
        AccessStruct(ctx.mem, NodeStruct, h).w_s("ln_Pred", node_addr)
        l.w_s("lh_Head", node_addr)

    def Remove(self, ctx):
        node_addr = ctx.cpu.r_reg(REG_A1)
        n = AccessStruct(ctx.mem, NodeStruct, node_addr)
        succ = n.r_s("ln_Succ")
        pred = n.r_s("ln_Pred")
        log_exec.info(
            "Remove(%06x): ln_Pred=%06x ln_Succ=%06x" % (node_addr, pred, succ)
        )
        AccessStruct(ctx.mem, NodeStruct, pred).w_s("ln_Succ", succ)
        AccessStruct(ctx.mem, NodeStruct, succ).w_s("ln_Pred", pred)
        return node_addr

    def RemHead(self, ctx):
        list_addr = ctx.cpu.r_reg(REG_A0)
        l = AccessStruct(ctx.mem, ListStruct, list_addr)
        node_addr = l.r_s("lh_Head")
        n = AccessStruct(ctx.mem, NodeStruct, node_addr)
        succ = n.r_s("ln_Succ")
        pred = n.r_s("ln_Pred")
        if succ == 0:
            log_exec.info("RemHead(%06x): null" % list_addr)
            return 0
        AccessStruct(ctx.mem, NodeStruct, pred).w_s("ln_Succ", succ)
        AccessStruct(ctx.mem, NodeStruct, succ).w_s("ln_Pred", pred)
        log_exec.info("RemHead(%06x): %06x" % (list_addr, node_addr))
        return node_addr

    def RemTail(self, ctx):
        list_addr = ctx.cpu.r_reg(REG_A0)
        l = AccessStruct(ctx.mem, ListStruct, list_addr)
        node_addr = l.r_s("lh_TailPred")
        n = AccessStruct(ctx.mem, NodeStruct, node_addr)
        succ = n.r_s("ln_Succ")
        pred = n.r_s("ln_Pred")
        if pred == 0:
            log_exec.info("RemTail(%06x): null" % list_addr)
            return 0
        AccessStruct(ctx.mem, NodeStruct, pred).w_s("ln_Succ", succ)
        AccessStruct(ctx.mem, NodeStruct, succ).w_s("ln_Pred", pred)
        log_exec.info("RemTail(%06x): %06x" % (list_addr, node_addr))
        return node_addr

    def FindName(self, ctx):
        list_addr = ctx.cpu.r_reg(REG_A0)
        name_ptr = ctx.cpu.r_reg(REG_A1)
        name = ctx.mem.r_cstr(name_ptr)
        list_t = List(ctx.mem, list_addr)
        match = list_t.find_name(name)
        log_exec.info("FindName: start=%s, name='%s' -> match=%s", list_t, name, match)
        if match:
            return match.get_addr()
        else:
            return 0

    def CopyMem(self, ctx):
        source = ctx.cpu.r_reg(REG_A0)
        dest = ctx.cpu.r_reg(REG_A1)
        length = ctx.cpu.r_reg(REG_D0)
        log_exec.info(
            "CopyMem: source=%06x dest=%06x len=%06x" % (source, dest, length)
        )
        ctx.mem.copy_block(source, dest, length)

    def CopyMemQuick(self, ctx):
        source = ctx.cpu.r_reg(REG_A0)
        dest = ctx.cpu.r_reg(REG_A1)
        length = ctx.cpu.r_reg(REG_D0)
        log_exec.info(
            "CopyMemQuick: source=%06x dest=%06x len=%06x" % (source, dest, length)
        )
        ctx.mem.copy_block(source, dest, length)

    def TypeOfMem(self, ctx):
        addr = ctx.cpu.r_reg(REG_A1)
        log_exec.info(
            "TypeOfMem: source=%06x -> %s" % (addr, self.alloc.is_valid_address(addr))
        )
        if self.alloc.is_valid_address(addr):
            return 1  # MEMF_PUBLIC
        return 0

    def CacheClearU(self, ctx):
        return 0

    def RawDoFmt(self, ctx):
        fmtString = ctx.cpu.r_reg(REG_A0)
        dataStream = ctx.cpu.r_reg(REG_A1)
        putProc = ctx.cpu.r_reg(REG_A2)
        putData = ctx.cpu.r_reg(REG_A3)
        dataStream, fmt, resultstr, known = raw_do_fmt(
            ctx, fmtString, dataStream, putProc, putData
        )
        log_exec.info(
            "RawDoFmt: fmtString=%s -> %s (known=%s, dataStream=%06x)"
            % (fmt, resultstr, known, dataStream)
        )
        return dataStream

    # ----- Semaphore Handling -----

    def InitSemaphore(self, ctx):
        addr = ctx.cpu.r_reg(REG_A0)
        self.semaphore_mgr.InitSemaphore(addr)
        log_exec.info("InitSemaphore(%06x)" % addr)

    def AddSemaphore(self, ctx):
        addr = ctx.cpu.r_reg(REG_A1)
        sstruct = AccessStruct(ctx.mem, SignalSemaphoreStruct, addr)
        name_ptr = sstruct.r_s("ss_Link.ln_Name")
        name = ctx.mem.r_cstr(name_ptr)
        self.semaphore_mgr.AddSemaphore(addr, name)
        log_exec.info("AddSemaphore(%06x,%s)" % (addr, name))

    def RemSemaphore(self, ctx):
        addr = ctx.cpu.r_reg(REG_A1)
        self.semaphore_mgr.RemSemaphore(addr)
        log_exec.info("RemSemaphore(%06x)" % addr)

    def FindSemaphore(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_A1)
        name = ctx.mem.r_cstr(name_ptr)
        semaphore = self.semaphore_mgr.FindSemaphore(name)
        log_exec.info("FindSemaphore(%s) -> %s" % (name, semaphore))
        if semaphore != None:
            return semaphore.addr
        else:
            return 0

    def ObtainSemaphore(self, ctx):
        addr = ctx.cpu.r_reg(REG_A0)
        # nop for now
        log_exec.info("ObtainSemaphore(%06x) ignored" % addr)

    def ObtainSemaphoreShared(self, ctx):
        addr = ctx.cpu.r_reg(REG_A0)
        # nop for now
        log_exec.info("ObtainSemaphoreShared(%06x) ignored" % addr)

    def AttemptSemaphore(self, ctx):
        addr = ctx.cpu.r_reg(REG_A0)
        # nop for now
        log_exec.info("AttemptSemaphore(%06x) ignored" % addr)
        return 1

    def ReleaseSemaphore(self, ctx):
        addr = ctx.cpu.r_reg(REG_A0)
        # nop for now
        log_exec.info("ReleaseSemaphore(%06x) ignored" % addr)

    # ----- Resources -----

    def OpenResource(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_A1)
        name = ctx.mem.r_cstr(name_ptr)
        log_exec.info("OpenResource(%s) ignored" % name)
        return 0

    # ----- Allocate/Deallocate -----

    def Allocate(self, ctx):
        mh_addr = ctx.cpu.r_reg(REG_A0)
        num_bytes = ctx.cpu.r_reg(REG_D0)
        blk_addr = Alloc.allocate(ctx, mh_addr, num_bytes)
        log_exec.info("Allocate(%06x, %06x) -> %06x" % (mh_addr, num_bytes, blk_addr))
        return blk_addr

    def Deallocate(self, ctx):
        mh_addr = ctx.cpu.r_reg(REG_A0)
        blk_addr = ctx.cpu.r_reg(REG_A1)
        num_bytes = ctx.cpu.r_reg(REG_D0)
        Alloc.deallocate(ctx, mh_addr, blk_addr, num_bytes)
        log_exec.info("Deallocate(%06x, %06x, %06x)" % (mh_addr, blk_addr, num_bytes))

    # ---------- Core helpers (no register access) ----------

    def _put_msg_core(self, ctx, port_addr, msg_addr):
        """
        Core PutMsg logic: assumes valid ctx, port_addr, msg_addr.
        Does NOT touch CPU registers.
        Thread-safe via _msg_lock.
        """
        log_exec.info("PutMsg(core): port=%06x msg=%06x", port_addr, msg_addr)

        with self._msg_lock:
            if not self.port_mgr.has_port(port_addr):
                raise VamosInternalError(
                    "PutMsg: on invalid Port (%06x) called!" % port_addr
                )

            self.port_mgr.put_msg(port_addr, msg_addr)

            # Signal the task that owns the port
            port = MsgPortStruct(ctx.mem, port_addr)
            sigbit = port.mp_SigBit.get()
            sigtask = port.mp_SigTask.get()

            self._signal_core(ctx, sigtask, 1 << sigbit)

    def _get_msg_core(self, ctx, port_addr):
        """
        Core GetMsg logic. Returns msg_addr or 0.
        Does NOT touch CPU registers.
        Thread-safe via _msg_lock.
        """
        log_exec.info("GetMsg(core): port=%06x", port_addr)

        with self._msg_lock:
            if not self.port_mgr.has_port(port_addr):
                raise VamosInternalError(
                    "GetMsg: on invalid Port (%06x) called!" % port_addr
                )

            msg_addr = self.port_mgr.get_msg(port_addr)
            if msg_addr is None:
                log_exec.info("GetMsg(core): no message available!")
                return 0

            log_exec.info("GetMsg(core): got message %06x", msg_addr)
            return msg_addr

    def _reply_msg_core(self, ctx, msg_addr):
        """
        Core ReplyMsg logic. Returns msg_addr or 0.
        Does NOT touch CPU registers.
        Thread-safe via _msg_lock (through _put_msg_core).
        """
        log_exec.info("ReplyMsg(core): msg=%06x", msg_addr)

        if msg_addr == 0:
            log_exec.warning("ReplyMsg(core): null message")
            return 0

        msg = MessageStruct(ctx.mem, msg_addr)
        reply_port_addr = msg.mn_ReplyPort.get()

        # internal IntuiMessageStruct
        if reply_port_addr == 0xFFEDCB:
            # Intuition-only message, free it and stop.
            ctx.alloc.free_mem(msg_addr, IntuiMessageStruct.get_size())
            return 0

        if reply_port_addr == 0:
            raise VamosInternalError("ReplyMsg: message has no ReplyPort")

        # Use core PutMsg (no CPU register access)
        self._put_msg_core(ctx, reply_port_addr, msg_addr)

        return msg_addr

    def _signal_core(self, ctx, task_addr, signal_mask):
        """
        Core signal logic.
        Amiga: Signal(task, mask)
        Here: task_addr is ignored (single-task scenario).
        """
        # In a multi-task world you'd look up the task and update its signal word.
        # For now we just OR into the single global.
        self.signals |= signal_mask
        log_exec.info("Exec.Signal(core): task=%06x mask=%08x -> signals=0x%08X",
                      task_addr, signal_mask, self.signals)

    def _set_signal_core(self, ctx, new_signals, signal_mask):
        """
        Core SetSignal logic.
        Amiga semantics: old = signals; signals = (signals & ~mask) | (new & mask)
        Returns old_signals.
        """
        old_signals = self.signals
        self.signals = (self.signals & ~signal_mask) | (new_signals & signal_mask)

        log_exec.info(
            "Exec.SetSignal(core): new=%08x mask=%08x old=%08x -> now=%08x",
            new_signals, signal_mask, old_signals, self.signals
        )
        return old_signals

    def _wait_core(self, ctx, mask):
        """
        Core Wait logic; does not touch CPU registers.
        Blocks until (signals & mask) != 0.
        SDL events are pumped here on the CPU thread.
        """
        log_exec.info("Exec.Wait(core): waiting for mask 0x%08X", mask)
    
        import sdl2
        event = sdl2.SDL_Event()
    
        # Pump SDL events on this thread
        if self.intuition_lib is not None:
            
            # peform pending refresh -> sdl2.render
            self.intuition_lib.check_refresh(ctx)
            
            while True:
                # Only bother if there’s at least one SDL window
                if self.intuition_lib.sdl_window_id_2_sdl_window:
                    while sdl2.SDL_PollEvent(event):
                        had_sdl_event = True
        
                        # Turn SDL → pending Intuition events (thread-safe)
                        one = self.intuition_lib.ingest_sdl_event(ctx, event)
                        if one is not None:
                            self.intuition_lib.drain_pending_intui_events(ctx, one)
        
        
                # Check signals
                received = self.signals & mask
                if received:
                    break
    
        received = self.signals & mask
        self.signals &= ~mask
    
        log_exec.info("Exec.Wait(core): received signals 0x%08X", received)
        return received

