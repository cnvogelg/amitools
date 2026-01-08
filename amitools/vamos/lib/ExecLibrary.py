from enum import IntEnum
from amitools.vamos.machine.regs import *
from amitools.vamos.libnative import MakeFuncs, InitStruct, MakeLib, LibFuncs, InitRes
from amitools.vamos.libcore import LibImpl
from amitools.vamos.astructs import AccessStruct, BYTE, CSTR
from amitools.vamos.libstructs import (
    ExecLibraryStruct,
    StackSwapStruct,
    IORequestStruct,
    NodeType,
    SignalSemaphoreStruct,
)
from amitools.vamos.libtypes import ExecLibrary as ExecLibraryType, MsgPort, Message
from amitools.vamos.libtypes import Task, List, Node
from amitools.vamos.log import log_exec
from amitools.vamos.error import VamosInternalError, UnsupportedFeatureError
from amitools.vamos.lib.lexec.signalfunc import SignalFunc
from amitools.vamos.lib.lexec.taskfunc import TaskFunc
from amitools.vamos.lib.lexec.msgfunc import MessageFunc
from .lexec.PortManager import PortManager
from .lexec.SemaphoreManager import SemaphoreManager
from .lexec.Pool import Pool
from .lexec.RawDoFmt import raw_do_fmt
from .lexec import Alloc


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
        self.exec_lib.lib_list.new(NodeType.NT_LIBRARY)
        self.exec_lib.device_list.new(NodeType.NT_DEVICE)
        self.exec_lib.task_ready.new(NodeType.NT_TASK)
        self.exec_lib.task_wait.new(NodeType.NT_TASK)
        self.exec_lib.port_list.new(NodeType.NT_MSGPORT)
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
        self.signal_func = SignalFunc(ctx, self.exec_lib)
        self.task_func = TaskFunc(ctx, self.exec_lib)
        self.msg_func = MessageFunc(
            ctx, self.exec_lib, self.signal_func, self.task_func, self.port_mgr
        )

    # helper

    def get_callee_pc(self, ctx):
        """a call stub log helper to extract the callee's pc"""
        sp = ctx.cpu.r_reg(REG_A7)
        return ctx.mem.r32(sp)

    # ----- Signals -----

    def AllocSignal(self, ctx, signal_num: BYTE):
        return self.signal_func.alloc_signal(signal_num.val)

    def FreeSignal(self, ctx, signal_num: BYTE):
        return self.signal_func.free_signal(signal_num.val)

    def SetSignal(self, ctx, new_signals, signal_mask):
        return self.signal_func.set_signal(new_signals, signal_mask)

    def Signal(self, ctx, task, signals):
        self.signal_func.signal(task, signals)

    def Wait(self, ctx, signal_set):
        return self.signal_func.wait(signal_set)

    def Disable(self, ctx):
        # map disable to forbid for now
        # (since we do not deal with irqs right now)
        log_exec.info("Disable -> Forbid")
        self.signal_func.forbid()

    def Enable(self, ctx):
        # map enable to permit for now
        # (since we do not deal with irqs right now)
        log_exec.info("Enable -> Permit")
        self.signal_func.permit()

    def Forbid(self, ctx):
        self.signal_func.forbid()

    def Permit(self, ctx):
        self.signal_func.permit()

    # ----- Tasks -----

    def FindTask(self, ctx, task_name: CSTR) -> Task:
        return self.task_func.find_task(task_name.str)

    def StackSwap(self, ctx):
        stsw_ptr = ctx.cpu.r_reg(REG_A0)
        stsw = AccessStruct(ctx.mem, StackSwapStruct, struct_addr=stsw_ptr)
        # get new stack values
        new_lower = stsw.r_s("stk_Lower")
        new_upper = stsw.r_s("stk_Upper")
        new_pointer = stsw.r_s("stk_Pointer")
        # retrieve current (old) stack
        stack = ctx.task.get_stack()
        old_lower = stack.get_lower()
        old_upper = stack.get_upper()
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
        # only owerwrite stack object but keep mem allocated (if any)
        stack.lower = new_lower
        stack.upper = new_upper
        stack.initial_sp = new_pointer
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
        ml = MakeLib(ctx.machine.get_mem(), ctx.alloc, ctx.runner)
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
        ir = InitRes(ctx.machine.get_mem(), ctx.alloc, ctx.runner)
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
        lf = LibFuncs(ctx.machine.get_mem(), ctx.alloc, ctx.runner)
        lf.add_library(lib_addr, exec_lib=self.exec_lib)

    def SumLibrary(self, ctx):
        lib_addr = ctx.cpu.r_reg(REG_A1)
        lf = LibFuncs(ctx.machine.get_mem(), ctx.alloc, ctx.runner)
        lib_sum = lf.sum_library(lib_addr)
        log_exec.info("SumLibrary: lib=%06x -> sum=%08x", lib_addr, lib_sum)

    def SetFunction(self, ctx):
        lib_addr = ctx.cpu.r_reg(REG_A1)
        lvo = ctx.cpu.rs_reg(REG_A0)
        new_func = ctx.cpu.r_reg(REG_D0)
        lf = LibFuncs(ctx.machine.get_mem(), ctx.alloc, ctx.runner)
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
        lf = LibFuncs(ctx.machine.get_mem(), ctx.alloc, ctx.runner)
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

    # ----- Pools -----

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

    def SuperState(self, ctx):
        # not complete with stack change and all but at least allows
        # to run privileged instructions
        ctx.cpu.w_sr(ctx.cpu.r_sr() | 0x2000)
        #ctx.cpu.w_msp(ctx.cpu.r_usp()-0x400)

    def UserState(self, ctx):
        # not complete with stack change and all but at least allows
        # to return to user state
        ctx.cpu.w_sr(ctx.cpu.r_sr() & 0x7FF)
        #ctx.cpu.w_msp(ctx.cpu.r_usp()-0x400)

    # ----- Memory Handling -----

    def AllocAbs(self, ctx):
        size = ctx.cpu.r_reg(REG_D0)
        location = ctx.cpu.r_reg(REG_A1)
        # label alloc
        pc = self.get_callee_pc(ctx)
        name = "AllocAbs(%06x)" % pc
        mb = self.alloc.alloc_abs_memory(location, size, label=name)
        log_exec.info("AllocAbs: %s -> 0x%06x %d bytes" % (mb, mb.addr, size))
        return mb.addr

    def AllocMem(self, ctx):
        size = ctx.cpu.r_reg(REG_D0)
        flags = ctx.cpu.r_reg(REG_D1)
        # label alloc
        pc = self.get_callee_pc(ctx)
        name = "AllocMem(%06x)" % pc
        mb = self.alloc.alloc_memory(size, label=name, except_on_failure=False)
        if mb is None:
            log_exec.info("AllocMem FAILED: %s size=%d flags=%08x", name, size, flags)
            return 0
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
            pass
             #raise VamosInternalError(
             #   "FreeMem: Unknown memory to free: ptr=%06x size=%06x" % (addr, size)
            #)

    def AllocVec(self, ctx):
        size = ctx.cpu.r_reg(REG_D0)
        flags = ctx.cpu.r_reg(REG_D1)
        name = "AllocVec(@%06x)" % self.get_callee_pc(ctx)
        mb = self.alloc.alloc_memory(size, label=name, except_on_failure=False)
        if mb is None:
            log_exec.info("AllocVec FAILED: %s size=%d flags=%08x", name, size, flags)
            return 0
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

    def PutMsg(self, ctx, port: MsgPort, msg: Message):
        return self.msg_func.put_msg(port, msg)

    def GetMsg(self, ctx, port: MsgPort) -> Message:
        return self.msg_func.get_msg(port)

    def CreateMsgPort(self, ctx) -> MsgPort:
        return self.msg_func.create_msg_port()

    def DeleteMsgPort(self, ctx, msg_port: MsgPort):
        return self.msg_func.delete_msg_port(msg_port)

    def WaitPort(self, ctx, msg_port: MsgPort) -> Message:
        return self.msg_func.wait_port(msg_port)

    def AddPort(self, ctx, msg_port: MsgPort):
        return self.msg_func.add_port(msg_port)

    def RemPort(self, ctx, msg_port: MsgPort):
        return self.msg_func.rem_port(msg_port)

    def FindPort(self, ctx, name: CSTR) -> MsgPort:
        return self.msg_func.find_port(name)

    def ReplyMsg(self, ctx, msg: Message):
        return self.msg_func.reply_msg(msg)

    # ----- IOReq/Devices -----

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

    # ----- Nodes/Lists -----

    def AddTail(self, ctx, list: List, node: Node):
        log_exec.info("AddTail(%s, %s)", list, node)
        list.add_tail(node)
        log_exec.debug("-> %s", list)

    def AddHead(self, ctx, list: List, node: Node):
        log_exec.info("AddHead(%s, %s)", list, node)
        list.add_head(node)
        log_exec.debug("-> %s", list)

    def RemHead(self, ctx, list: List) -> Node:
        node = list.rem_head()
        log_exec.info("RemHead(%s) -> %s", list, node)
        return node

    def RemTail(self, ctx, list: List) -> Node:
        node = list.rem_tail()
        log_exec.info("RemTail(%s) -> %s", list, node)
        return node

    def FindName(self, ctx, list: List, name: CSTR) -> Node:
        node = list.find_name(name.str)
        log_exec.info("FindName(%s, %s) -> %s", list, name, node)
        return node

    def Insert(self, ctx, list: List, node: Node, list_node: Node):
        list.insert(node, list_node)
        log_exec.info("Insert(%s, %s, %s)", list, node, list_node)

    def Enqueue(self, ctx, list: List, node: Node):
        list.enqueue(node)
        log_exec.info("Enqueue(%s, %s)", list, node)

    def Remove(self, ctx, node: Node):
        log_exec.info("Remove(%s)", node)
        ok = node.remove()
        if not ok:
            log_exec.warning("Remove(%s) not in a list?", node)

    # ----- Memory Ops -----

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

    # ----- Misc -----

    def Alert(self, ctx, code):
        log_exec.error("ALERT: code=%08x", code)
