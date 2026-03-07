from enum import IntEnum
from amitools.vamos.machine.regs import *
from amitools.vamos.libnative import MakeFuncs, InitStruct, MakeLib, LibFuncs, InitRes
from amitools.vamos.libcore import LibImpl
from amitools.vamos.astructs import AccessStruct, BYTE, CSTR
from amitools.vamos.libstructs import (
    ExecLibraryStruct,
    StackSwapStruct,
    IORequestStruct,
    MessageStruct,
    MsgPortStruct,
    ListStruct,
    NodeStruct,
    NodeType,
    SignalSemaphoreStruct,
)
from amitools.vamos.libstructs.exec_ import TaskStruct
from amitools.vamos.libtypes import ExecLibrary as ExecLibraryType
from amitools.vamos.libtypes import Task, List
from amitools.vamos.log import log_exec
from amitools.vamos.error import VamosInternalError, UnsupportedFeatureError
from amitools.vamos.lib.lexec.signalfunc import SignalFunc
from amitools.vamos.lib.lexec.taskfunc import TaskFunc
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
        self.exec_lib.lib_list.new_list(NodeType.NT_LIBRARY)
        self.exec_lib.device_list.new_list(NodeType.NT_DEVICE)
        self.exec_lib.task_ready.new_list(NodeType.NT_TASK)
        self.exec_lib.task_wait.new_list(NodeType.NT_TASK)
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

    # helper

    def get_callee_pc(self, ctx):
        """a call stub log helper to extract the callee's pc"""
        sp = ctx.cpu.r_reg(REG_A7)
        return ctx.mem.r32(sp)

    # ----- System -----

    def AllocSignal(self, ctx, signal_num: BYTE):
        return self.signal_func.alloc_signal(signal_num.val)

    def FreeSignal(self, ctx, signal_num: BYTE):
        return self.signal_func.free_signal(signal_num.val)

    def SetSignal(self, ctx, new_signals, signal_mask):
        return self.signal_func.set_signal(new_signals, signal_mask)

    def Signal(self, ctx, task, signals):
        self.signal_func.signal(task, signals)

    def Wait(self, ctx, signal_set):
        # Check if we're in fallback mode (no scheduler task)
        sched_task = self.signal_func.get_my_sched_task()
        if sched_task is None:
            # Fallback mode - check if any signals are already set
            from .lexec.signalfunc import SignalFunc
            got = SignalFunc._fallback_signals & signal_set
            if got != 0:
                # Clear the received signals and return them
                SignalFunc._fallback_signals &= ~got
                log_exec.info("Wait(%08x): fallback immediate -> %08x", signal_set, got)
                return got
            else:
                # No signals pending - block
                sp = ctx.cpu.r_reg(REG_A7)
                ExecLibrary._wait_blocked_sp = sp
                ExecLibrary._wait_blocked_mask = signal_set
                ExecLibrary._wait_blocked_ret = ctx.mem.r32(sp)
                log_exec.info("Wait(%08x): fallback blocking (sp=%08x)", signal_set, sp)
                raise UnsupportedFeatureError(
                    "Wait on signal set %08x with no signals pending" % signal_set
                )
        # Normal path with scheduler
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
            raise VamosInternalError(
                "FreeMem: Unknown memory to free: ptr=%06x size=%06x" % (addr, size)
            )

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

    def PutMsg(self, ctx):
        port_addr = ctx.cpu.r_reg(REG_A0)
        msg_addr = ctx.cpu.r_reg(REG_A1)
        log_exec.info("PutMsg: port=%06x msg=%06x" % (port_addr, msg_addr))
        has_port = self.port_mgr.has_port(port_addr)
        if not has_port:
            raise VamosInternalError(
                "PutMsg: on invalid Port (%06x) called!" % port_addr
            )
        self.port_mgr.put_msg(port_addr, msg_addr)

    def GetMsg(self, ctx):
        port_addr = ctx.cpu.r_reg(REG_A0)
        log_exec.info("GetMsg: port=%06x" % (port_addr))
        has_port = self.port_mgr.has_port(port_addr)
        if not has_port:
            raise VamosInternalError(
                "GetMsg: on invalid Port (%06x) called!" % port_addr
            )
        msg_addr = self.port_mgr.get_msg(port_addr)
        if msg_addr is not None:
            # Also remove from m68k memory list (REMOVE operation)
            # to keep Python queue and m68k list in sync.
            try:
                ln_succ = ctx.mem.r32(msg_addr + 0)
                ln_pred = ctx.mem.r32(msg_addr + 4)
                if ln_succ != 0 and ln_pred != 0:
                    ctx.mem.w32(ln_pred + 0, ln_succ)  # pred.ln_Succ = succ
                    ctx.mem.w32(ln_succ + 4, ln_pred)  # succ.ln_Pred = pred
            except Exception:
                pass
            log_exec.info("GetMsg: got message %06x" % (msg_addr))
            return msg_addr
        else:
            log_exec.info("GetMsg: no message available!")
            return 0

    def ReplyMsg(self, ctx):
        msg_addr = ctx.cpu.r_reg(REG_A1)
        log_exec.info("ReplyMsg: msg=%06x" % (msg_addr))
        if msg_addr == 0:
            return 0
        msg = AccessStruct(ctx.mem, MessageStruct, msg_addr)
        reply_port = msg.r_s("mn_ReplyPort")
        if reply_port == 0:
            return 0
        if not self.port_mgr.has_port(reply_port):
            log_exec.warning("ReplyMsg: invalid reply port %06x", reply_port)
            return 0
        msg.w_s("mn_Node.ln_Type", NodeType.NT_REPLYMSG)
        self.port_mgr.put_msg(reply_port, msg_addr)
        return 0

    def CreateMsgPort(self, ctx):
        port = self.port_mgr.create_port("exec_port", None)
        log_exec.info("CreateMsgPort: -> port=%06x" % (port))
        return port

    def AddPort(self, ctx):
        """Add a port to the public port list."""
        port_addr = ctx.cpu.r_reg(REG_A1)
        if port_addr == 0:
            log_exec.warning("AddPort: NULL port")
            return 0
        # Register the port with port manager if not already registered
        if not self.port_mgr.has_port(port_addr):
            self.port_mgr.register_port(port_addr)
        # Read port name for debugging
        try:
            mp = AccessStruct(ctx.mem, MsgPortStruct, port_addr)
            name_addr = mp.r_s("mp_Node.ln_Name")
            port_name = ctx.mem.r_cstr(name_addr) if name_addr else "unnamed"
        except:
            port_name = "?"
        log_exec.info("AddPort: port=%06x name=%s" % (port_addr, port_name))
        return 0

    def RemPort(self, ctx):
        """Remove a port from the public port list."""
        port_addr = ctx.cpu.r_reg(REG_A1)
        if port_addr == 0:
            log_exec.warning("RemPort: NULL port")
            return 0
        # Unregister the port if it was registered
        if self.port_mgr.has_port(port_addr):
            self.port_mgr.unregister_port(port_addr)
        log_exec.info("RemPort: port=%06x" % port_addr)
        return 0

    def FindPort(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_A1)
        if name_ptr == 0:
            log_exec.info("FindPort(NULL) -> 0")
            return 0
        try:
            name = ctx.mem.r_cstr(name_ptr)
        except Exception:
            name = "<invalid>"

        # First, check if this port exists in the public port list (via AddPort)
        # Look it up by searching registered ports for matching name
        port_addr = self._find_port_by_name(ctx, name)
        if port_addr:
            log_exec.info("FindPort('%s') -> %06x" % (name, port_addr))
            return port_addr

        log_exec.info("FindPort('%s') -> 0 (not found)" % name)
        return 0

    def _find_port_by_name(self, ctx, name):
        """Look up a port by name in registered ports."""
        from amitools.vamos.libstructs.exec_ import MsgPortStruct, NodeStruct
        # Search all registered ports for one with matching ln_Name
        for addr in self.port_mgr.ports:
            try:
                mp = AccessStruct(ctx.mem, MsgPortStruct, addr)
                name_addr = mp.r_s("mp_Node.ln_Name")
                if name_addr != 0:
                    port_name = ctx.mem.r_cstr(name_addr)
                    if port_name == name:
                        return addr
            except Exception:
                pass
        return 0

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
        # Initialize the IORequest structure
        ctx.mem.w_block(mb.addr, b"\x00" * size)
        io = AccessStruct(ctx.mem, IORequestStruct, mb.addr)
        io.w_s("io_Message.mn_ReplyPort", port)
        io.w_s("io_Message.mn_Length", size)
        io.w_s("io_Flags", 0)
        io.w_s("io_Error", 0)
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

    def _dispatch_begin_io(self, ctx, io_addr):
        """Helper to call BeginIO on the target device and mark the request done."""
        io = AccessStruct(ctx.mem, IORequestStruct, io_addr)
        dev_addr = io.r_s("io_Device")
        vlib = self.lib_mgr.get_vlib_by_addr(dev_addr)
        if vlib is None:
            log_exec.warning(
                "DoIO: missing device for io=0x%06x dev=0x%06x", io_addr, dev_addr
            )
            return -1
        impl = vlib.get_impl()
        # ensure regs point at the IORequest
        ctx.cpu.w_reg(REG_A1, io_addr)
        if hasattr(impl, "BeginIO"):
            # Set IOF_QUICK before BeginIO.  Devices that hold requests
            # (e.g. TD_ADDCHANGEINT) clear this flag to indicate the IO
            # is NOT completed yet and should not be replied.
            flags = io.r_s("io_Flags") | 1  # IOF_QUICK
            io.w_s("io_Flags", flags)
            impl.BeginIO(ctx)
            # Re-read flags - device may have cleared IOF_QUICK
            flags = io.r_s("io_Flags")
            if flags & 1:
                io.w_s("io_Message.mn_Node.ln_Type", NodeType.NT_REPLYMSG)
            return io.r_s("io_Error")
        log_exec.warning("DoIO: device impl missing BeginIO for dev=0x%06x", dev_addr)
        return -1

    def DoIO(self, ctx):
        io_addr = ctx.cpu.r_reg(REG_A1)
        res = self._dispatch_begin_io(ctx, io_addr)
        log_exec.info("DoIO(io=0x%06x) -> %d", io_addr, res)
        return res

    def SendIO(self, ctx):
        io_addr = ctx.cpu.r_reg(REG_A1)
        res = self._dispatch_begin_io(ctx, io_addr)
        log_exec.info("SendIO(io=0x%06x) -> %d", io_addr, res)
        # SendIO is asynchronous - the caller expects a reply message when IO
        # completes.  We complete synchronously in _dispatch_begin_io, so we
        # simulate async completion by queuing the IORequest as a reply.
        # If the device cleared IOF_QUICK (e.g. TD_ADDCHANGEINT which holds
        # the request), we do NOT queue a reply - the IO is pending.
        io = AccessStruct(ctx.mem, IORequestStruct, io_addr)
        if not (io.r_s("io_Flags") & 1):
            log_exec.info("SendIO: IO held (IOF_QUICK cleared), no reply queued")
            return res
        reply_port = io.r_s("io_Message.mn_ReplyPort")
        if reply_port != 0:
            # Auto-register ports that handlers created internally (e.g.
            # PFS3's timer reply port) so we can queue messages to them.
            if not self.port_mgr.has_port(reply_port):
                self.port_mgr.register_port(reply_port)
                log_exec.info(
                    "SendIO: auto-registered reply_port=0x%06x", reply_port
                )
            self.port_mgr.put_msg(reply_port, io_addr)
            # Also add to the m68k memory list (ADDTAIL) so the handler
            # can find the message via raw list access or WaitIO/Remove.
            # Without this, only the Python queue has the message, and
            # handlers that check the m68k list directly would see an
            # empty list and skip processing.
            try:
                lst_off = MsgPortStruct.sdef.find_field_def_by_name("mp_MsgList").offset
                list_addr = reply_port + lst_off
                # lh_Tail is at offset 4 within ListStruct
                lh_tail_field = list_addr + 4
                # lh_TailPred is at offset 8 within ListStruct
                old_tailpred = ctx.mem.r32(list_addr + 8)
                # ADDTAIL: insert message node at end of list
                ctx.mem.w32(io_addr + 0, lh_tail_field)  # ln_Succ -> &lh_Tail
                ctx.mem.w32(io_addr + 4, old_tailpred)   # ln_Pred -> old last
                ctx.mem.w32(old_tailpred + 0, io_addr)   # old_last.ln_Succ -> new
                ctx.mem.w32(list_addr + 8, io_addr)      # lh_TailPred -> new
            except Exception:
                pass  # Port memory not accessible - Python queue is enough
            # Signal the task like real AmigaOS ReplyMsg() does.
            # Without this, handlers that call Wait() for IO completion
            # (e.g. BFFS) never see the IO completion signal and take
            # wrong code paths.
            try:
                sigbit = ctx.mem.r8(
                    reply_port
                    + MsgPortStruct.sdef.find_field_def_by_name(
                        "mp_SigBit"
                    ).offset
                )
                if 0 <= sigbit < 32:
                    sig_task_off = MsgPortStruct.sdef.find_field_def_by_name(
                        "mp_SigTask"
                    ).offset
                    sig_task = ctx.mem.r32(reply_port + sig_task_off)
                    if sig_task != 0:
                        self.signal_func.signal(sig_task, 1 << sigbit)
            except Exception:
                pass
            log_exec.info("SendIO: queued reply to port 0x%06x", reply_port)
        return res

    def CheckIO(self, ctx):
        io_addr = ctx.cpu.r_reg(REG_A1)
        io = AccessStruct(ctx.mem, IORequestStruct, io_addr)
        log_exec.info("CheckIO(io=0x%06x)", io_addr)
        # Return io_addr if complete (IOF_QUICK set), 0 if still pending
        return io_addr if (io.r_s("io_Flags") & 1) else 0

    def WaitIO(self, ctx):
        io_addr = ctx.cpu.r_reg(REG_A1)
        io = AccessStruct(ctx.mem, IORequestStruct, io_addr)
        log_exec.info("WaitIO(io=0x%06x)", io_addr)
        # Remove IORequest from its reply port's message list and Python
        # queue (like real WaitIO does after IO completes).
        reply_port = io.r_s("io_Message.mn_ReplyPort")
        if reply_port != 0 and self.port_mgr.has_port(reply_port):
            # Remove from Python queue if present
            port = self.port_mgr.ports[reply_port]
            if port.queue is not None and io_addr in port.queue:
                port.queue.remove(io_addr)
            # Remove from m68k memory list (REMOVE operation)
            try:
                ln_succ = ctx.mem.r32(io_addr + 0)
                ln_pred = ctx.mem.r32(io_addr + 4)
                if ln_succ != 0 and ln_pred != 0:
                    ctx.mem.w32(ln_pred + 0, ln_succ)
                    ctx.mem.w32(ln_succ + 4, ln_pred)
            except Exception:
                pass
        return io.r_s("io_Error")

    # Class variables for tracking blocked WaitPort/Wait state (used by amifuse)
    _waitport_blocked_sp = None
    _waitport_blocked_port = None
    _waitport_blocked_ret = None
    _wait_blocked_sp = None
    _wait_blocked_ret = None
    _wait_blocked_mask = None

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
            # Set blocking state before raising exception (for amifuse resume support)
            sp = ctx.cpu.r_reg(REG_A7)
            ExecLibrary._waitport_blocked_sp = sp
            ExecLibrary._waitport_blocked_port = port_addr
            # Return address is at top of stack
            ExecLibrary._waitport_blocked_ret = ctx.mem.r32(sp)
            raise UnsupportedFeatureError(
                "WaitPort on empty message queue called: Port (%06x)" % port_addr
            )
        msg_addr = self.port_mgr.peek_msg(port_addr)
        log_exec.info("WaitPort: peek message %06x" % (msg_addr))
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
