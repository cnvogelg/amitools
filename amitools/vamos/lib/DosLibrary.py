import time
import re
from contextlib import ExitStack

from amitools.vamos.machine import Code
from amitools.vamos.machine.regs import *
from amitools.vamos.libcore import LibImpl
from amitools.vamos.astructs import CSTR, LONG, UBYTE, APTR_VOID
from amitools.vamos.libstructs import (
    DosLibraryStruct,
    DosInfoStruct,
    RootNodeStruct,
    DateStampStruct,
    DateTimeStruct,
    LocalVarStruct,
    NodeStruct,
    SegmentStruct,
    FileHandleStruct,
    FileInfoBlockStruct,
    ExAllControlStruct,
    ExAllDataStruct,
    InfoDataStruct,
    DevProcStruct,
    AnchorPathStruct,
    RDArgsStruct,
    CLIStruct,
    DosPacketStruct,
    DosListDeviceStruct,
    DosListVolumeStruct,
    DosListAssignStruct,
    ProcessStruct,
    MessageStruct,
    MsgPortStruct,
    MsgPortFlags,
    ListStruct,
    TaskState,
    NodeType,
    TimeRequestStruct,
)
from amitools.vamos.libtypes import TagList, DosTag, DosPacket
from amitools.vamos.error import *
from amitools.vamos.log import log_dos
from amitools.vamos.handler import HandlerError, MODE_OLDFILE
from amitools.vamos.task import DosProcess
from amitools.vamos.schedule import SchedulerEvent
from .dos.Args import *
from .dos.Error import *
from .dos.AmiTime import *
from .dos import PathPart
from .dos.PatternMatch import Pattern, pattern_parse, pattern_match
from .dos.MatchFirstNext import MatchFirstNext
from .dos.CommandLine import CommandLine
from .dos.Process import Process
from .dos.DosList import DosList
from .dos.LockManager import LockManager
from .dos.Lock import fill_fib
from .dos.FileManager import FileManager
from .dos.DosFileOpener import DosFileOpener
from .dos import (
    Assign,
    Cli,
    Date,
    FileIO,
    Link,
    Notify,
    RecordLock,
    Segments,
    Stdio,
    Volume,
)
from .dos.CSource import *
from .dos.Item import *
from amitools.vamos.dos import run_command, run_sub_process

FORMAT_DOS = 0
FORMAT_INT = 1
FORMAT_USA = 2
FORMAT_CDN = 3
FORMAT_DEF = 4
DTF_SUBST = 1
DOS_MONTH_NAMES = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
SUBSTITUTED_DATES = ("Future", "Tomorrow", "Today", "Yesterday")


class DosLibrary(LibImpl):
    LV_VAR = 0  # an variable
    LV_ALIAS = 1  # an alias
    LVF_IGNORE = 0x80
    GVF_GLOBAL_ONLY = 0x100
    GVF_LOCAL_ONLY = 0x200
    GVF_BINARY_VAR = 0x400

    MAX_SHOW_DATA = 32

    def __init__(self):
        super().__init__()
        # these helpers keep state only in the Python process and may be
        # used before setup_lib() (e.g. by tests or a bare LibProxy)
        self.record_locks = RecordLock.RecordLockManager(self)
        self.handler_mgr = None

    def get_struct_def(self):
        return DosLibraryStruct

    def setup_lib(self, ctx, base_addr):
        log_dos.info("setup dos.library")
        # init own state
        self.alloc = ctx.alloc
        self.path_mgr = ctx.path_mgr
        self.io_err = 0
        self.mem_allocs = {}
        self.seg_lists = {}
        self.matches = {}
        self.rdargs = {}
        self.dos_objs = {}
        self.exall_scans = {}
        self.dos_entries = {}
        self.errstrings = {}
        self.resident = []
        self.local_vars = {}
        self.global_vars = {}
        self.record_locks = RecordLock.RecordLockManager(self)
        self.lib_struct = DosLibraryStruct(ctx.mem, base_addr)
        # setup RootNode
        self.root_struct = ctx.alloc.alloc_astruct(RootNodeStruct, label="RootNode")
        self.root_node = self.root_struct
        self.lib_struct.dl_Root.aptr = self.root_struct.addr
        # setup DosInfo
        self.dos_info = ctx.alloc.alloc_astruct(DosInfoStruct, label="DosInfo")
        self.dos_info_struct = self.dos_info
        self.root_node.rn_Info.aptr = self.dos_info.addr
        # file system handlers are built by the caller (main) and passed in
        # via the context; dos.library only consumes them
        self.handler_mgr = ctx.handler_mgr
        # setup dos list
        self.dos_list = DosList(
            self.path_mgr,
            self.path_mgr.assign_mgr,
            ctx.mem,
            ctx.alloc,
            handler_mgr=self.handler_mgr,
        )
        self.dos_list.build_list(ctx.path_mgr)
        self.update_dos_list_head()
        # create file manager
        self.file_mgr = FileManager(
            self.handler_mgr, ctx.exec_lib.port_mgr, ctx.alloc, ctx.mem
        )
        self.dos_list.add_host_devices()
        self.update_dos_list_head()
        # let the segment loader open files through DOS
        if ctx.seg_loader is not None:
            ctx.seg_loader.set_file_opener(DosFileOpener(self.file_mgr))
        # create lock manager
        self.lock_mgr = LockManager(
            ctx.path_mgr,
            self.dos_list,
            ctx.alloc,
            ctx.mem,
            handler_mgr=self.handler_mgr,
        )
        # the packet decoder resolves locks through the lock manager
        self.file_mgr.lock_mgr = self.lock_mgr
        # equip the DosList with all the locks
        self.dos_list.add_locks(self.lock_mgr)
        self._setup_timer_request(ctx)
        # processes made by CreateNewProc(), by their scheduler task
        self.child_procs = {}
        self.port_mgr = ctx.exec_lib.port_mgr
        if ctx.scheduler is not None:
            ctx.scheduler.set_event_callback(self._child_proc_event)

    # --- Timing ---

    def Delay(self, ctx):
        # DOS Delay waits d1 ticks (1/50s = 20ms per tick)
        ticks = ctx.cpu.r_reg(REG_D1)
        log_dos.info("Delay(%d)", ticks)
        if ticks > 0:
            time.sleep(ticks / 50.0)
        return 0

    def finish_lib(self, ctx):
        self._drop_all_exall_scans()
        self._finish_timer_request(ctx)
        # free the child processes that still run
        for child in self.child_procs.values():
            child.free()
        self.child_procs = {}
        # finish file manager
        self.file_mgr.finish()
        # free dos list
        self.dos_list.free_list()
        # free resident nodes
        for res in self.resident:
            self._free_mem(res)
        # free shell variables
        while len(self.local_vars) > 0:
            var = list(self.local_vars.values())[0]
            self.delete_var(ctx, var)
        # self.delete_var(ctx,var)
        # free RootNode
        self.root_struct.free()
        # free DosInfo
        self.dos_info.free()

    def _setup_timer_request(self, ctx):
        self.timer_device = 0
        self.timer_request = None
        self.timer_request_mem = None
        self.lib_struct.dl_TimeReq.aptr = 0
        with ExitStack() as rollback:
            device = ctx.exec_lib.lib_mgr.open_lib("timer.device", 0)
            if device == 0:
                return
            rollback.callback(ctx.exec_lib.lib_mgr.close_lib, device)
            # The typed allocator raises an internal error on exhaustion.
            # Allocate fallibly, then use a typed view of the owned memory.
            memory = ctx.alloc.alloc_memory(
                TimeRequestStruct.get_size(),
                label="DOS TimerRequest",
                except_on_failure=False,
            )
            if memory is None:
                return
            rollback.callback(ctx.alloc.free_memory, memory)
            request = TimeRequestStruct(ctx.mem, memory.addr)
            request.tr_node.io_Device.aptr = device
            self.timer_device = device
            self.timer_request = request
            self.timer_request_mem = memory
            self.lib_struct.dl_TimeReq.aptr = request.addr
            rollback.pop_all()

    def _finish_timer_request(self, ctx):
        memory = self.timer_request_mem
        device = self.timer_device
        self.timer_device = 0
        self.timer_request = None
        self.timer_request_mem = None
        self.lib_struct.dl_TimeReq.aptr = 0
        try:
            if memory is not None:
                ctx.alloc.free_memory(memory)
        finally:
            if device != 0:
                ctx.exec_lib.lib_mgr.close_lib(device)

    def update_dos_list_head(self):
        """Publish the current DOS list head through DOSBase."""
        head_addr = self.dos_list.get_head_addr()
        self.dos_info.di_DevInfo.aptr = head_addr
        return head_addr

    # helper

    def get_callee_pc(self, ctx):
        """a call stub log helper to extract the callee's pc"""
        sp = ctx.cpu.r_reg(REG_A7)
        return ctx.mem.r32(sp)

    # ----- IoErr -----

    def IoErr(self, ctx):
        if self.io_err in dos_error_strings:
            errstring = dos_error_strings[self.io_err]
        else:
            errstring = "%d" % self.io_err
        log_dos.info("IoErr: %d (%s)", self.io_err, errstring)
        return self.io_err

    def setioerr(self, ctx, err):
        self.io_err = err
        process = ctx.process
        if process is None:
            return
        amiga_process = getattr(process, "this_task", None)
        if amiga_process is None:
            amiga_process = getattr(process, "ami_proc", None)
        if amiga_process is not None:
            amiga_process.pr_Result2.val = err

    def SetIoErr(self, ctx):
        old_io_err = self.io_err
        self.setioerr(ctx, ctx.cpu.r_reg(REG_D1))
        log_dos.info("SetIoErr: IoErr=%d old IoErr=%d", self.io_err, old_io_err)
        return old_io_err

    def WaitPkt(self, ctx):
        proc_addr = ctx.exec_lib.exec_lib.this_task.aptr
        if proc_addr == 0:
            log_dos.warning("WaitPkt: ThisTask is NULL")
            return 0
        proc = ProcessStruct(ctx.mem, proc_addr)
        port_addr = proc.pr_MsgPort.addr
        log_dos.info("WaitPkt: proc=%06x port=%06x", proc_addr, port_addr)
        if not ctx.exec_lib.port_mgr.has_port(port_addr):
            log_dos.warning("WaitPkt: port %06x not registered", port_addr)
            return 0
        if not ctx.exec_lib.port_mgr.has_msg(port_addr):
            raise UnsupportedFeatureError(
                "WaitPkt on empty message queue called: Port (%06x)" % port_addr
            )
        msg_addr = ctx.exec_lib.port_mgr.get_msg(port_addr)
        self._unlink_msg(ctx, msg_addr)
        msg = MessageStruct(ctx.mem, msg_addr)
        return msg.mn_Node.ln_Name.aptr

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
            hdr = ctx.mem.r_cstr(hdr_ptr)
        else:
            hdr = ""
        if idx in dos_error_strings:
            err_str = dos_error_strings[idx]
        else:
            err_str = "%d ERROR" % self.io_err
        log_dos.info(
            "Fault: code=%d header='%s' err_str='%s'", self.io_err, hdr, err_str
        )
        # write to stdout
        if hdr_ptr != 0:
            txt = "%s: %s" % (hdr, err_str)
        else:
            txt = "%s" % err_str
        ctx.mem.w_cstr(buf_ptr, txt[: buf_len - 1])
        return DOSTRUE

    def PrintFault(self, ctx):
        self.io_err = ctx.cpu.r_reg(REG_D1)
        hdr_ptr = ctx.cpu.r_reg(REG_D2)
        if self.io_err >= 0x80000000:
            idx = self.io_err - 0x100000000
        else:
            idx = self.io_err
        # get header string
        if hdr_ptr != 0:
            hdr = ctx.mem.r_cstr(hdr_ptr)
        else:
            hdr = ""
        # get error string
        if idx in dos_error_strings:
            err_str = dos_error_strings[idx]
        else:
            err_str = "%d ERROR" % self.io_err
        log_dos.info(
            "PrintFault: code=%d header='%s' err_str='%s'", self.io_err, hdr, err_str
        )
        # write to stdout
        if hdr_ptr != 0:
            txt = "%s: %s\n" % (hdr, err_str)
        else:
            txt = "%s\n" % err_str
        fh = ctx.process.get_output()
        fh.write(txt.encode("latin-1"))
        return DOSTRUE

    # ----- current dir

    def get_current_dir(self, ctx):
        cur_dir = ctx.process.get_current_dir()
        return self.lock_mgr.get_by_b_addr(cur_dir >> 2)

    def get_home_dir(self, ctx):
        """Get the program's home directory lock (PROGDIR:)"""
        home_dir = ctx.process.get_home_dir()
        return self.lock_mgr.get_by_b_addr(home_dir >> 2)

    def get_cwd_path(self, ctx):
        """Amiga path of the current directory lock (or None)"""
        cur_dir = self.get_current_dir(ctx)
        return cur_dir.ami_path if cur_dir is not None else None

    # ----- dos API -----

    def DateStamp(self, ctx):
        ds_ptr = ctx.cpu.r_reg(REG_D1)
        ds = DateStampStruct(ctx.mem, ds_ptr)
        t = time.time()
        at = sys_to_ami_time(t)
        log_dos.info("DateStamp: ptr=%06x sys_time=%d time=%s", ds_ptr, t, at)
        ds.ds_Days.val = at.tday
        ds.ds_Minute.val = at.tmin
        ds.ds_Tick.val = at.tick
        return ds_ptr

    def DateToStr(self, ctx):
        dt_ptr = ctx.cpu.r_reg(REG_D1)
        dt = DateTimeStruct(ctx.mem, dt_ptr)
        ds_day = dt.dat_Stamp.ds_Days.val
        ds_min = dt.dat_Stamp.ds_Minute.val
        ds_tick = dt.dat_Stamp.ds_Tick.val
        date_format = dt.dat_Format.val
        flags = dt.dat_Flags.val
        str_day_ptr = dt.dat_StrDay.aptr
        str_date_ptr = dt.dat_StrDate.aptr
        str_time_ptr = dt.dat_StrTime.aptr
        at = AmiTime(ds_day, ds_min, ds_tick)
        st = at.to_sys_time()
        log_dos.info(
            "DateToStr: ptr=%06x format=%x flags=%x day_ptr=%06x date_ptr=%06x time_ptr=%06x %s => sys_time=%d",
            dt_ptr,
            format,
            flags,
            str_day_ptr,
            str_date_ptr,
            str_time_ptr,
            at,
            st,
        )
        t = time.gmtime(st)
        day_str = time.strftime("%A", t)
        year = t.tm_year % 100
        if date_format == FORMAT_INT:
            date_str = "%02d-%02d-%02d" % (year, t.tm_mon, t.tm_mday)
        elif date_format == FORMAT_USA:
            date_str = "%02d-%02d-%02d" % (t.tm_mon, t.tm_mday, year)
        elif date_format == FORMAT_CDN:
            date_str = "%02d-%02d-%02d" % (t.tm_mday, t.tm_mon, year)
        elif date_format == FORMAT_DEF:
            date_str = time.strftime("%x", t)
        else:
            date_str = "%02d-%s-%02d" % (
                t.tm_mday,
                DOS_MONTH_NAMES[t.tm_mon - 1],
                year,
            )
        if flags & DTF_SUBST:
            days_since = sys_to_ami_time(time.time()).tday - ds_day
            if days_since <= 7:
                if -1 <= days_since <= 1:
                    date_str = SUBSTITUTED_DATES[days_since + 2]
                elif days_since < -1:
                    date_str = "Future"
                else:
                    date_str = day_str
        time_str = time.strftime("%H:%M:%S", t)
        log_dos.info(
            "DateToStr: result day='%s' date='%s' time='%s'",
            day_str,
            date_str,
            time_str,
        )
        if str_day_ptr != 0:
            ctx.mem.w_cstr(str_day_ptr, day_str)
        if str_date_ptr != 0:
            ctx.mem.w_cstr(str_date_ptr, date_str)
        if str_time_ptr != 0:
            ctx.mem.w_cstr(str_time_ptr, time_str)
        return DOSTRUE

    def SetFileDate(self, ctx, name: CSTR, date):
        return FileIO.set_file_date(self, ctx, name.get_str(), date)

    def SetComment(self, ctx, name: CSTR, comment: CSTR):
        return FileIO.set_comment(self, ctx, name.get_str(), comment.get_str())

    def GetProgramName(self, ctx):
        buf_ptr = ctx.cpu.r_reg(REG_D1)
        max_len = ctx.cpu.r_reg(REG_D2)
        prog_name = ctx.process.get_program_name()
        n = len(prog_name)
        # return error if name is too long, but copy buffer size
        if n > max_len - 1:
            self.setioerr(ctx, ERROR_LINE_TOO_LONG)
            ret = DOSFALSE
            prog_name = prog_name[0:max_len]
        else:
            ret = DOSTRUE
        ctx.mem.w_cstr(buf_ptr, prog_name)
        log_dos.info("GetProgramName() -> '%s' (%d)", prog_name, max_len)
        return ret

    def GetProgramDir(self, ctx):
        prog_dir_addr = ctx.process.get_home_dir()
        prog_dir_lock = self.lock_mgr.get_by_b_addr(prog_dir_addr >> 2)
        log_dos.info("GetProgramDir() -> %s", prog_dir_lock)
        if prog_dir_lock:
            return prog_dir_lock.b_addr
        else:
            return 0

    def GetArgStr(self, ctx):
        arg_ptr = ctx.process.get_arg_str_ptr()
        log_dos.info("GetArgStr() -> %08x", arg_ptr)
        return arg_ptr

    # ----- Variables -----

    def find_var(self, ctx, name, flags):
        if (name.lower(), flags & 0xFF) in self.local_vars:
            return self.local_vars[(name.lower(), flags & 0xFF)]
        else:
            return None

    def create_var(self, ctx, name, flags):
        varlist = ctx.process.get_local_vars()
        varlist_struct = varlist
        node_addr = self._alloc_mem(
            "ShellVar(%s)" % name, LocalVarStruct.get_size() + len(name) + 1
        )
        name_addr = node_addr + LocalVarStruct.get_size()
        node = LocalVarStruct(ctx.mem, node_addr)
        ctx.mem.w_cstr(name_addr, name)
        node.lv_Node.ln_Name.aptr = name_addr
        node.lv_Node.ln_Type.val = flags & 0xFF
        node.lv_Value.aptr = 0
        head_addr = varlist_struct.mlh_Head.aptr
        head = NodeStruct(ctx.mem, head_addr)
        head.ln_Pred.aptr = node_addr
        varlist_struct.mlh_Head.aptr = node_addr
        node.lv_Node.ln_Succ.aptr = head_addr
        node.lv_Node.ln_Pred.aptr = varlist_struct.mlh_Head.addr
        self.local_vars[(name.lower(), flags & 0xFF)] = node
        return node

    def set_var(self, ctx, node, buff_ptr, size, value, flags):
        if node.lv_Value.aptr != 0:
            self._free_mem(node.lv_Value.aptr)
            node.lv_Value.aptr = 0
        buf_addr = self._alloc_mem("ShellVarBuffer", size)
        node.lv_Value.aptr = buf_addr
        node.lv_Len.val = size
        if flags & self.GVF_BINARY_VAR:
            ctx.mem.copy_block(buff_ptr, buf_addr, size)
        else:
            ctx.mem.w_cstr(buf_addr, value)

    def delete_var(self, ctx, node):
        buf_addr = node.lv_Value.aptr
        buf_len = node.lv_Len.val
        name_addr = node.lv_Node.ln_Name.aptr
        name = ctx.mem.r_cstr(name_addr)
        if buf_addr != 0:
            self._free_mem(buf_addr)
        node.lv_Value.aptr = 0
        succ = node.lv_Node.ln_Succ.aptr
        pred = node.lv_Node.ln_Pred.aptr
        NodeStruct(ctx.mem, pred).ln_Succ.aptr = succ
        NodeStruct(ctx.mem, succ).ln_Pred.aptr = pred
        self._free_mem(node.addr)
        for k in list(self.local_vars.keys()):
            if self.local_vars[k] == node:
                del self.local_vars[k]

    def GetVar(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        buff_ptr = ctx.cpu.r_reg(REG_D2)
        size = ctx.cpu.r_reg(REG_D3)
        flags = ctx.cpu.r_reg(REG_D4)
        if size == 0:
            self.setioerr(ctx, ERROR_BAD_NUMBER)
            return -1
        name = ctx.mem.r_cstr(name_ptr)
        if not flags & self.GVF_GLOBAL_ONLY:
            node = self.find_var(ctx, name, flags & 0xFF)
            if node != None:
                nodelen = node.lv_Len.val
                if flags & self.GVF_BINARY_VAR:
                    ctx.mem.copy_block(node.lv_Value.aptr, buff_ptr, min(nodelen, size))
                    log_dos.info(
                        'GetVar("%s", 0x%x) -> %0x06x',
                        name,
                        flags,
                        node.lv_Value.aptr,
                    )
                    self.setioerr(ctx, nodelen)
                    return min(nodelen, size)
                else:
                    value = ctx.mem.r_cstr(node.lv_Value.aptr)
                    ctx.mem.w_cstr(buff_ptr, value[: size - 1])
                    log_dos.info('GetVar("%s", 0x%x) -> %s', name, flags, value)
                    self.setioerr(ctx, len(value))
                    return min(nodelen - 1, size - 1)
        # no local variable. unless we were asked for local only, fall back
        # to the global ones, which is the order AmigaOS looks them up in
        if not flags & self.GVF_LOCAL_ONLY:
            value = self.global_vars.get((name.lower(), flags & 0xFF))
            if value is not None:
                if flags & self.GVF_BINARY_VAR:
                    ctx.mem.write_data(buff_ptr, value[:size])
                    log_dos.info('GetVar("%s", 0x%x) -> <global binary>', name, flags)
                    self.setioerr(ctx, len(value))
                    return min(len(value), size)
                ctx.mem.w_cstr(buff_ptr, value[: size - 1])
                log_dos.info('GetVar("%s", 0x%x) -> %s (global)', name, flags, value)
                self.setioerr(ctx, len(value))
                return min(len(value), size - 1)
        self.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
        return -1

    def FindVar(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        vtype = ctx.cpu.r_reg(REG_D2)
        name = ctx.mem.r_cstr(name_ptr)
        node = self.find_var(ctx, name, vtype)
        if node == None:
            self.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
            log_dos.info('FindVar("%s", 0x%x) -> NULL', name, vtype)
            return 0
        else:
            log_dos.info('FindVar("%s", 0x%x) -> %06lx', name, vtype, node.addr)
            return node.addr

    def SetVar(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        buff_ptr = ctx.cpu.r_reg(REG_D2)
        size = ctx.cpu.r_reg(REG_D3)
        flags = ctx.cpu.r_reg(REG_D4)
        name = ctx.mem.r_cstr(name_ptr)
        vtype = flags & 0xFF
        if buff_ptr == 0:
            if flags & self.GVF_GLOBAL_ONLY:
                self.global_vars.pop((name.lower(), vtype), None)
                return DOSTRUE
            node = self.find_var(ctx, name, vtype)
            if node != None:
                self.delete_var(ctx, node)
            return DOSTRUE
        else:
            if flags & self.GVF_BINARY_VAR:
                value = None
                log_dos.info('SetVar("%s") to %0x6x', name, buff_ptr)
            else:
                value = ctx.mem.r_cstr(buff_ptr)
                log_dos.info('SetVar("%s") to %s', name, value)
                size = len(value) + 1
            if flags & self.GVF_GLOBAL_ONLY:
                if flags & self.GVF_BINARY_VAR:
                    value = ctx.mem.read_data(buff_ptr, size)
                self.global_vars[(name.lower(), vtype)] = value
                return DOSTRUE
            node = self.find_var(ctx, name, flags)
            if node == None and buff_ptr != 0:
                node = self.create_var(ctx, name, flags)
            if node != None:
                self.set_var(ctx, node, buff_ptr, size, value, flags)
            return DOSTRUE
        return 0

    def DeleteVar(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        flags = ctx.cpu.r_reg(REG_D2)
        name = ctx.mem.r_cstr(name_ptr)
        if flags & self.GVF_GLOBAL_ONLY:
            found = self.global_vars.pop((name.lower(), flags & 0xFF), None)
            log_dos.info('DeleteVar("%s") global', name)
            return DOSTRUE if found is not None else DOSFALSE
        node = self.find_var(ctx, name, flags)
        log_dos.info('DeleteVar("%s")', name)
        if node != None:
            self.delete_var(ctx, node)
        return DOSTRUE

    # ----- Signals ----------------------

    def CheckSignal(self, ctx):
        sigmask = ctx.cpu.r_reg(REG_D1)
        # THOR: Fixme. We really need to get the signal
        # mask from the tty here.
        return 0

    # ----- Resident commands support ----

    def FindSegment(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        needle = ctx.mem.r_cstr(name_ptr)
        start = ctx.cpu.r_reg(REG_D2)
        system = ctx.cpu.r_reg(REG_D3)
        if start == 0:
            seg_addr = self.dos_info_struct.di_NetHand.aptr
        else:
            seg_addr = SegmentStruct(ctx.mem, start).seg_Next.aptr
        log_dos.info("FindSegment(%s)", needle)
        while seg_addr != 0:
            segment = SegmentStruct(ctx.mem, seg_addr)
            name_addr = seg_addr + SegmentStruct.sdef.seg_Name.offset
            name = ctx.mem.r_bstr(name_addr)
            seg_uc = segment.seg_UC.val
            if name.lower() == needle.lower():
                if (system and seg_uc < 0) or (not system and seg_uc > 0):
                    seg = segment.seg_Seg.aptr
                    log_dos.info("FindSegment(%s) -> %s", name, seg)
                    return seg_addr
            seg_addr = segment.seg_Next.aptr
        return 0

    def AddSegment(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        seglist = ctx.cpu.r_reg(REG_D2) << 2
        system = ctx.cpu.r_reg(REG_D3)
        name = ctx.mem.r_cstr(name_ptr)
        seg_addr = self._alloc_mem("Segment", SegmentStruct.get_size() + len(name) + 1)
        name_addr = seg_addr + SegmentStruct.sdef.seg_Name.offset
        segment = SegmentStruct(ctx.mem, seg_addr)
        head_addr = self.dos_info_struct.di_NetHand.aptr
        segment.seg_Next.aptr = head_addr
        segment.seg_UC.val = system
        segment.seg_Seg.aptr = seglist
        ctx.mem.w_bstr(name_addr, name)
        self.dos_info_struct.di_NetHand.aptr = seg_addr
        log_dos.info("AddSegment(%s,%06x) -> %06x", name, seglist, seg_addr)
        self.resident.append(seg_addr)
        # Adding a resident command to the registered seglists.
        b_addr = seglist >> 2
        if b_addr not in self.seg_lists:
            self.seg_lists[b_addr] = name
        return -1

    # ----- File Ops -----

    def Cli(self, ctx):
        return FileIO.cli(self, ctx)

    def ExtendedCli(self, ctx):
        return FileIO.extended_cli(self, ctx)

    def Input(self, ctx):
        return FileIO.input(self, ctx)

    def Output(self, ctx):
        return FileIO.output(self, ctx)

    def SelectInput(self, ctx, fh_b_addr):
        return FileIO.select_input(self, ctx, fh_b_addr)

    def SelectOutput(self, ctx, fh_b_addr):
        return FileIO.select_output(self, ctx, fh_b_addr)

    def SetMode(self, ctx, fh_b_addr, mode: LONG):
        return FileIO.set_mode(self, ctx, fh_b_addr, mode.val)

    def WaitForChar(self, ctx, fh_b_addr, timeout: LONG):
        return FileIO.wait_for_char(self, ctx, fh_b_addr, timeout.val)

    def Open(self, ctx, name_ptr, mode):
        return FileIO.open_file(self, ctx, name_ptr, mode)

    def Close(self, ctx, fh_b_addr):
        return FileIO.close_file(self, ctx, fh_b_addr)

    def Read(self, ctx, fh_b_addr, buf_ptr, size):
        return FileIO.read_file(self, ctx, fh_b_addr, buf_ptr, size)

    def Write(self, ctx, fh_b_addr, buf_ptr, size):
        return FileIO.write_file(self, ctx, fh_b_addr, buf_ptr, size)

    def FWrite(self, ctx, fh_b_addr, buf_ptr, size, number):
        return FileIO.fwrite(self, ctx, fh_b_addr, buf_ptr, size, number)

    def FRead(self, ctx, fh_b_addr, buf_ptr, size, number):
        return FileIO.fread(self, ctx, fh_b_addr, buf_ptr, size, number)

    def Seek(self, ctx, fh_b_addr, pos, mode):
        return FileIO.seek(self, ctx, fh_b_addr, pos, mode)

    def SetFileSize(self, ctx, fh_b_addr, pos, mode):
        return FileIO.set_file_size(self, ctx, fh_b_addr, pos, mode)

    def FGetC(self, ctx, fh_b_addr):
        return FileIO.fgetc(self, ctx, fh_b_addr)

    def FPutC(self, ctx, fh_b_addr, val):
        return FileIO.fputc(self, ctx, fh_b_addr, val)

    def FPuts(self, ctx, fh_b_addr, str_ptr):
        return FileIO.fputs(self, ctx, fh_b_addr, str_ptr)

    def UnGetC(self, ctx, fh_b_addr, val):
        return FileIO.ungetc(self, ctx, fh_b_addr, val)

    # ----- StdOut -----

    def PutStr(self, ctx, str_ptr):
        return Stdio.put_str(self, ctx, str_ptr)

    def Flush(self, ctx, fh_b_addr):
        return FileIO.flush_file(self, ctx, fh_b_addr)

    def SetVBuf(self, ctx, fh_b_addr, buf_ptr, buf_type, size):
        return FileIO.set_vbuf(self, ctx, fh_b_addr, buf_ptr, buf_type, size)

    def VPrintf(self, ctx, format: CSTR, argv_ptr):
        return FileIO.printf_to_handle(
            self, ctx, ctx.process.get_output(), format.get_str(), argv_ptr
        )

    def VFPrintf(self, ctx, fh_b_addr, format: CSTR, argv_ptr):
        return FileIO.vfprintf(self, ctx, fh_b_addr, format.get_str(), argv_ptr)

    def WriteChars(self, ctx, buf_ptr, size):
        return Stdio.write_chars(self, ctx, buf_ptr, size)

    def VFWritef(self, ctx, fh_b_addr, format: CSTR, args_ptr):
        return FileIO.vfwritef(self, ctx, fh_b_addr, format.get_str(), args_ptr)

    # ----- Stdin --------

    def FGets(self, ctx, fh_b_addr, buf_addr, buflen):
        return FileIO.fgets(self, ctx, fh_b_addr, buf_addr, buflen)

    # ----- File Ops -----

    def DeleteFile(self, ctx, name: CSTR):
        return FileIO.delete_file(self, ctx, name.get_str())

    def Rename(self, ctx, oldName: CSTR, newName: CSTR):
        return FileIO.rename(self, ctx, oldName.get_str(), newName.get_str())

    def SetProtection(self, ctx, name: CSTR, protect):
        return FileIO.set_protection(self, ctx, name.get_str(), protect)

    def IsInteractive(self, ctx, fh_b_addr):
        return FileIO.is_interactive(self, ctx, fh_b_addr)

    def IsFileSystem(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        name = ctx.mem.r_cstr(name_ptr)
        log_dos.info("IsFileSystem('%s'):", name)
        lock = self.get_current_dir(ctx)
        res = self.file_mgr.is_file_system(lock, name)
        log_dos.info("IsFileSystem('%s'): %s", name, res)
        if res:
            return DOSTRUE
        else:
            return DOSFALSE

    # ----- Locks -----

    def Lock(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        name = ctx.mem.r_cstr(name_ptr)
        mode = ctx.cpu.r_reg(REG_D2)

        if mode == 0xFFFFFFFF:
            lock_exclusive = True
        elif mode == 0xFFFFFFFE:
            lock_exclusive = False
        else:
            raise UnsupportedFeatureError("Lock: mode=%x" % mode)

        cur_dir = self.get_current_dir(ctx)
        home_dir = self.get_home_dir(ctx)
        lock = self.lock_mgr.create_lock(
            cur_dir, name, lock_exclusive, home_dir=home_dir
        )
        log_dos.info(
            "Lock: (curdir=%s, homedir=%s) '%s' exc=%s -> %s",
            cur_dir,
            home_dir,
            name,
            lock_exclusive,
            lock,
        )
        if lock == None:
            self.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
            return 0
        else:
            return lock.b_addr

    def UnLock(self, ctx):
        lock_b_addr = ctx.cpu.r_reg(REG_D1)
        if lock_b_addr == 0:
            log_dos.info("UnLock: NULL")
        else:
            lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
            log_dos.info("UnLock: %s", lock)
            self.lock_mgr.release_lock(lock)

    def DupLock(self, ctx):
        lock_b_addr = ctx.cpu.r_reg(REG_D1)
        lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
        dup_lock = self.lock_mgr.dup_lock(lock)
        log_dos.info("DupLock: %s -> %s", lock, dup_lock)
        if dup_lock is None:
            self.setioerr(ctx, ERROR_INVALID_LOCK)
            return 0
        self.setioerr(ctx, NO_ERROR)
        return dup_lock.b_addr

    def SameLock(self, ctx):
        lock1_b_addr = ctx.cpu.r_reg(REG_D1)
        lock2_b_addr = ctx.cpu.r_reg(REG_D2)
        lock1 = self.lock_mgr.get_by_b_addr(lock1_b_addr)
        lock2 = self.lock_mgr.get_by_b_addr(lock2_b_addr)
        if lock1 is None or lock2 is None:
            return DOSFALSE
        if lock1 is lock2:
            return DOSTRUE
        # two locks on the same handler are compared by the handler; locks
        # from different handlers are never the same object
        if (
            lock1.handler is not None
            and lock1.handler is lock2.handler
            and lock1.handler_lock is not None
            and lock2.handler_lock is not None
        ):
            same = lock1.handler.same_lock(lock1.handler_lock, lock2.handler_lock)
            return DOSTRUE if same else DOSFALSE
        if lock1.handler is None and lock2.handler is None:
            return DOSTRUE if lock1.key == lock2.key else DOSFALSE
        return DOSFALSE

    def OpenFromLock(self, ctx):
        lock_b_addr = ctx.cpu.r_reg(REG_D1)
        lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
        if lock is None:
            self.setioerr(ctx, ERROR_INVALID_LOCK)
            return 0
        try:
            fh = self.file_mgr.open_from_lock(lock, MODE_OLDFILE)
        except HandlerError as e:
            self.setioerr(ctx, e.code)
            return 0
        # the handle absorbs the lock
        self.lock_mgr.release_lock(lock)
        log_dos.info("OpenFromLock: %s -> %s", lock, fh)
        self.setioerr(ctx, NO_ERROR)
        return fh.b_addr

    def DupLockFromFH(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        fh = self.file_mgr.get_by_b_addr(fh_b_addr)
        if fh is None or fh.handler is None or fh.handler_file is None:
            self.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
            return 0
        try:
            handler_lock = fh.handler.copy_dir_fh(fh.handler_file)
        except HandlerError as e:
            self.setioerr(ctx, e.code)
            return 0
        lock = self.lock_mgr.register_handler_lock(
            fh.handler, handler_lock, fh.ami_path, name=fh.name
        )
        log_dos.info("DupLockFromFH: %s -> %s", fh, lock)
        self.setioerr(ctx, NO_ERROR)
        return lock.b_addr

    def ParentOfFH(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        fh = self.file_mgr.get_by_b_addr(fh_b_addr)
        if fh is None or fh.handler is None or fh.handler_file is None:
            self.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
            return 0
        try:
            handler_lock = fh.handler.parent_fh(fh.handler_file)
        except HandlerError as e:
            self.setioerr(ctx, e.code)
            return 0
        ami_parent_path = self.path_mgr.ami_abs_parent_path(fh.ami_path)
        name = self.path_mgr.ami_name_of_path(None, ami_parent_path)
        lock = self.lock_mgr.register_handler_lock(
            fh.handler, handler_lock, ami_parent_path, name=name
        )
        log_dos.info("ParentOfFH: %s -> %s", fh, lock)
        self.setioerr(ctx, NO_ERROR)
        return lock.b_addr

    def Examine(self, ctx):
        lock_b_addr = ctx.cpu.r_reg(REG_D1)
        fib_ptr = ctx.cpu.r_reg(REG_D2)

        lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
        fib = FileInfoBlockStruct(ctx.mem, fib_ptr)
        err = lock.examine_lock(fib)
        name_addr = fib.fib_FileName.addr
        name = ctx.mem.r_cstr(name_addr)
        log_dos.info("Examine: %s fib=%06x(%s) -> %s", lock, fib_ptr, name, err)
        self.setioerr(ctx, err)
        if err == NO_ERROR:
            return DOSTRUE
        else:
            return DOSFALSE

    def ExamineFH(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        fib_ptr = ctx.cpu.r_reg(REG_D2)

        fh = self.file_mgr.get_by_b_addr(fh_b_addr, False)
        fib = FileInfoBlockStruct(ctx.mem, fib_ptr)
        # handler-backed: ACTION_EXAMINE_FH examines the object the handle
        # points at directly
        if fh.handler is not None and fh.handler_file is not None:
            try:
                info = fh.handler.examine_fh(fh.handler_file)
            except HandlerError as e:
                self.setioerr(ctx, e.code)
                return DOSFALSE
            fill_fib(fib, info, name=fh.name)
            log_dos.info("ExamineFH: %s fib=%06x -> ok", fh, fib_ptr)
            self.setioerr(ctx, 0)
            return DOSTRUE
        # handler-less fallback: examine via a temporary lock
        lock = self.lock_mgr.create_lock(self.get_current_dir(ctx), fh.ami_path, False)
        log_dos.info(
            "Lock: (%s) '%s' exc=%s -> %s",
            self.get_current_dir(ctx),
            fh.ami_path,
            False,
            lock,
        )
        if lock == None:
            self.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
            return DOSFALSE

        err = lock.examine_lock(fib)
        name_addr = fib.fib_FileName.addr
        name = ctx.mem.r_cstr(name_addr)
        log_dos.info("ExamineFH: %s fib=%06x(%s) -> %s", fh, fib_ptr, name, err)
        self.setioerr(ctx, err)

        log_dos.info("UnLock: %s", lock)
        self.lock_mgr.release_lock(lock)
        if err == NO_ERROR:
            return DOSTRUE
        else:
            return DOSFALSE

    def Info(self, ctx):
        lock_b_addr = ctx.cpu.r_reg(REG_D1)
        info_ptr = ctx.cpu.r_reg(REG_D2)
        lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
        info = InfoDataStruct(ctx.mem, info_ptr)
        if lock is None:
            self.setioerr(ctx, ERROR_INVALID_LOCK)
            return DOSFALSE
        vol = lock.find_volume_node(self.dos_list)
        if vol:
            if lock.handler is None:
                self.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
                return DOSFALSE
            try:
                if lock.handler_lock is not None:
                    disk = lock.handler.info(lock.handler_lock)
                elif self.handler_mgr is not None:
                    # a lock without a handler lock: a lock-less volume query
                    # (ACTION_DISK_INFO) resolved through the handler manager
                    volume_name = self.lock_mgr.volume_name_of_lock(lock)
                    disk = self.handler_mgr.disk_info(volume_name)
                else:
                    disk = lock.handler.disk_info(None)
            except HandlerError as e:
                self.setioerr(ctx, e.code)
                return DOSFALSE
            disk_state = disk.disk_state
            block_size = disk.bytes_per_block
            total = disk.num_blocks
            used = disk.num_blocks_used
            info.id_NumSoftErrors.val = 0
            info.id_UnitNumber.val = 0  # not that we really care...
            info.id_DiskState.val = disk_state
            # InfoData has signed 32-bit block counts. Preserve capacity
            # on large host filesystems by increasing the reporting unit.
            while total > 0x7FFFFFFF:
                total = (total + 1) // 2
                used = (used + 1) // 2
                block_size *= 2
            info.id_NumBlocks.val = total
            info.id_NumBlocksUsed.val = used
            info.id_BytesPerBlock.val = block_size
            info.id_DiskType.val = 0x444F5303  # international FFS
            info.id_VolumeNode.aptr = vol
            info.id_InUse.val = 0
            self.setioerr(ctx, 0)
            log_dos.info("Info: %s info=%06x -> true", lock, info_ptr)
            return DOSTRUE
        else:
            log_dos.info("Info: %s info=%06x -> false", lock, info_ptr)
            return DOSFALSE

    def ExNext(self, ctx):
        lock_b_addr = ctx.cpu.r_reg(REG_D1)
        fib_ptr = ctx.cpu.r_reg(REG_D2)
        lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
        fib = FileInfoBlockStruct(ctx.mem, fib_ptr)
        err = lock.examine_next(fib)
        name_addr = fib.fib_FileName.addr
        name = ctx.mem.r_cstr(name_addr)
        log_dos.info("ExNext: %s fib=%06x (%s) -> %s", lock, fib_ptr, name, err)
        self.setioerr(ctx, err)
        if err == NO_ERROR:
            self.setioerr(ctx, 0)
            return DOSTRUE
        else:
            self.setioerr(ctx, err)
            return DOSFALSE

    # bytes of struct ExAllData used by each ED_* type: ED_NAME .. ED_OWNER
    ex_all_data_sizes = (0, 8, 12, 16, 20, 32, 36, 40)

    @staticmethod
    def _free_scan_lock(scan):
        """release the handler lock of an ExAll scan (ACTION_FREE_LOCK)"""
        if scan.handler is not None and scan.handler_lock is not None:
            scan.handler.free_lock(scan.handler_lock)

    def _drop_exall_scan(self, control_ptr):
        """drop a control's scan state and release its cloned handler lock"""
        state = self.exall_scans.pop(control_ptr, None)
        if state is not None:
            self._free_scan_lock(state[1])
        return state

    def _drop_all_exall_scans(self):
        for state in self.exall_scans.values():
            self._free_scan_lock(state[1])
        self.exall_scans.clear()

    def ExAll(self, ctx, lock_b_addr, buffer, size, data_type, control_ptr):
        """Fill a bounded entry chain using a cursor private to this control."""
        control = ExAllControlStruct(ctx.mem, control_ptr)
        control.eac_Entries.val = 0
        if data_type < 1 or data_type >= len(self.ex_all_data_sizes):
            self._drop_exall_scan(control_ptr)
            self.setioerr(ctx, ERROR_BAD_NUMBER)
            return DOSFALSE
        if size < 0 or size > 0x7FFFFFFF:
            self._drop_exall_scan(control_ptr)
            self.setioerr(ctx, ERROR_NO_FREE_STORE)
            return DOSFALSE
        lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
        if lock is None:
            self._drop_exall_scan(control_ptr)
            self.setioerr(ctx, ERROR_INVALID_LOCK)
            return DOSFALSE
        last_key = control.eac_LastKey.val
        if last_key == 0:
            # A cloned lock owns its ExNext cache independently of the
            # caller's lock. clone_for_scan also checks that the lock is a
            # directory.
            self._drop_exall_scan(control_ptr)
            try:
                scan = lock.clone_for_scan()
            except HandlerError as e:
                self.setioerr(ctx, e.code)
                return DOSFALSE
            self.exall_scans[control_ptr] = (lock, scan)
        else:
            state = self.exall_scans.get(control_ptr)
            if state is None or state[0] is not lock:
                self._drop_exall_scan(control_ptr)
                self.setioerr(ctx, ERROR_INVALID_LOCK)
                return DOSFALSE
            scan = state[1]

        fib_size = FileInfoBlockStruct.get_size()
        scratch = self.alloc.alloc_memory(
            fib_size + 4, label="ExAll_FIB", except_on_failure=False
        )
        if scratch is None:
            self.exall_scans.pop(control_ptr, None)
            self.setioerr(ctx, ERROR_NO_FREE_STORE)
            return DOSFALSE
        keep_scan = False
        try:
            fib = FileInfoBlockStruct(ctx.mem, scratch.addr)
            if last_key == 0:
                err = scan.examine_lock(fib)
            else:
                fib.fib_DiskKey.val = last_key
                err = NO_ERROR
            if err == NO_ERROR:
                err = self._exall_fill(
                    ctx,
                    scan,
                    fib,
                    buffer,
                    size,
                    data_type,
                    control,
                    scratch.addr + fib_size,
                )
            control.eac_LastKey.val = fib.fib_DiskKey.val
            keep_scan = err == NO_ERROR
        finally:
            self.alloc.free_memory(scratch)
            if not keep_scan:
                self._drop_exall_scan(control_ptr)
        log_dos.info(
            "ExAll: %s buf=%06x size=%d type=%d -> entries=%d err=%d",
            lock,
            buffer,
            size,
            data_type,
            control.eac_Entries.val,
            err,
        )
        self.setioerr(ctx, err)
        return DOSTRUE if err == NO_ERROR else DOSFALSE

    def _exall_fill(self, ctx, scan, fib, buffer, size, data_type, control, type_ptr):
        match_ptr = control.eac_MatchString.aptr
        match_pat = None
        if match_ptr:
            match_pat = Pattern(None, ctx.mem.r_cstr(match_ptr), True, True)
        hook_ptr = control.eac_MatchFunc.aptr
        entry_size = self.ex_all_data_sizes[data_type]
        prev = None
        pos = buffer
        end = buffer + size
        while True:
            key_before = fib.fib_DiskKey.val
            # The Examine helper leaves fib_Size unchanged for directories.
            fib.fib_Size.val = 0
            err = scan.examine_next(fib)
            if err != NO_ERROR:
                return err
            name = ctx.mem.r_cstr(fib.fib_FileName.addr)
            if match_pat is not None and not pattern_match(match_pat, name):
                continue
            comment = ""
            if data_type >= 6:
                comment = ctx.mem.r_cstr(fib.fib_Comment.addr)
            need = entry_size + len(name) + 1
            if comment:
                need += len(comment) + 1
            need = (need + 3) & ~3
            if pos + need > end:
                fib.fib_DiskKey.val = key_before
                if control.eac_Entries.val == 0:
                    return ERROR_NO_FREE_STORE
                return NO_ERROR
            ead = ExAllDataStruct(ctx.mem, pos)
            str_addr = pos + entry_size
            ead.ed_Next.aptr = 0
            ead.ed_Name.aptr = str_addr
            ctx.mem.w_cstr(str_addr, name)
            str_addr += len(name) + 1
            if data_type >= 2:
                ead.ed_Type.val = fib.fib_DirEntryType.val
            if data_type >= 3:
                ead.ed_Size.val = fib.fib_Size.val
            if data_type >= 4:
                ead.ed_Prot.val = fib.fib_Protection.val
            if data_type >= 5:
                ead.ed_Days.val = fib.fib_Date.ds_Days.val
                ead.ed_Mins.val = fib.fib_Date.ds_Minute.val
                ead.ed_Ticks.val = fib.fib_Date.ds_Tick.val
            if data_type >= 6:
                ead.ed_Comment.aptr = str_addr if comment else 0
                if comment:
                    ctx.mem.w_cstr(str_addr, comment)
            if data_type >= 7:
                ead.ed_OwnerUID.val = fib.fib_OwnerUID.val
                ead.ed_OwnerGID.val = fib.fib_OwnerGID.val
            if hook_ptr:
                # h_Entry follows the Hook's two-pointer MinNode header.
                entry = ctx.mem.r32(hook_ptr + 8)
                ctx.mem.w32(type_ptr, data_type)
                code = Code(
                    entry,
                    set_regs={REG_A0: hook_ptr, REG_A1: pos, REG_A2: type_ptr},
                    get_regs=[REG_D0],
                )
                result = ctx.runner(code, name="ExAllMatch")
                if result.regs[REG_D0] == 0:
                    continue
            if prev is not None:
                prev.ed_Next.aptr = pos
            prev = ead
            pos += need
            control.eac_Entries.val += 1

    def ExAllEnd(self, ctx, lock_b_addr, buffer, size, data_type, control_ptr):
        self._drop_exall_scan(control_ptr)
        control = ExAllControlStruct(ctx.mem, control_ptr)
        control.eac_Entries.val = 0
        control.eac_LastKey.val = 0

    def ParentDir(self, ctx):
        lock_b_addr = ctx.cpu.r_reg(REG_D1)
        lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
        parent_lock = self.lock_mgr.create_parent_lock(lock)
        log_dos.info("ParentDir: %s -> %s", lock, parent_lock)
        if parent_lock != None:
            return parent_lock.b_addr
        else:
            return 0

    def CurrentDir(self, ctx):
        lock_b_addr = ctx.cpu.r_reg(REG_D1)
        # CurrentDir exchanges a BPTR. The old lock may already have been
        # released (e.g. FreeDeviceProc followed by restoring the old cwd).
        proc = ctx.process.get_ami_process()
        old = proc.current_dir.bptr
        proc.current_dir.bptr = lock_b_addr
        return old

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
            self.setioerr(ctx, ERROR_LINE_TOO_LONG)
            return DOSFALSE
        else:
            ctx.mem.w_cstr(buf, name)
            return DOSTRUE

    def NameFromFH(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        buf = ctx.cpu.r_reg(REG_D2)
        buf_len = ctx.cpu.r_reg(REG_D3)
        fh = self.file_mgr.get_by_b_addr(fh_b_addr)
        if fh is None:
            log_dos.warning("NameFromFH: invalid fh=%x", fh_b_addr)
            self.setioerr(ctx, ERROR_INVALID_LOCK)
            return DOSFALSE
        name = fh.ami_path
        log_dos.info("NameFromFH(%x,%d): %s -> %s", buf, buf_len, fh, name)
        if len(name) >= buf_len:
            self.setioerr(ctx, ERROR_LINE_TOO_LONG)
            return DOSFALSE
        else:
            ctx.mem.w_cstr(buf, name)
            return DOSTRUE

    def CreateDir(self, ctx, name: CSTR):
        return FileIO.create_dir(self, ctx, name.get_str())

    # ----- DevProc -----

    def _handler_port(self, name):
        """the packet port of the handler serving ``name`` (0 if none)"""
        if self.handler_mgr is None:
            return 0
        get_dispatcher = getattr(self.handler_mgr, "get_dispatcher", None)
        if get_dispatcher is None:
            return 0
        dispatcher = get_dispatcher(name)
        return dispatcher.port if dispatcher is not None else 0

    # dvp_Flags (see dos/dosextens.h)
    DVPF_UNLOCK = 1
    DVPF_ASSIGN = 2

    def _port_of_lock(self, lock, name):
        """the packet port of the handler behind ``lock`` (fallback ``name``)"""
        if lock is not None and lock.handler is not None:
            dispatcher = getattr(lock.handler, "dispatcher", None)
            if dispatcher is not None:
                return dispatcher.port
        return self._handler_port(name)

    def _new_devproc(self, ctx, name, port, lock, flags, devnode=0):
        """allocate a DevProc for a handler/lock/device node"""
        addr = self._alloc_mem("DevProc:%s" % name, DevProcStruct.get_size())
        devproc = DevProcStruct(ctx.mem, addr)
        devproc.dvp_Port.aptr = port
        devproc.dvp_Lock.aptr = (lock.b_addr << 2) if lock is not None else 0
        # a lock only needs unlocking if the DevProc owns it
        devproc.dvp_Flags.val = flags if lock is not None else flags & ~self.DVPF_UNLOCK
        devproc.dvp_DevNode.aptr = devnode
        return addr

    def GetDeviceProc(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        last_devproc = ctx.cpu.r_reg(REG_D2)
        name = ctx.mem.r_cstr(name_ptr)
        uname = name.upper()

        # "*" enumerates every entry of the DOS device list, returning the
        # next device on each call (AmigaDOS listing extension)
        if uname == "*":
            return self._enumerate_devproc(ctx, last_devproc)

        # a repeated call only continues a multi-directory assign
        if last_devproc != 0:
            if self._advance_assign_devproc(ctx, last_devproc):
                return last_devproc
            # AmigaDOS frees the DevProc and returns NULL at the end
            self._release_devproc_lock(DevProcStruct(ctx.mem, last_devproc))
            self._free_mem(last_devproc)
            self.setioerr(ctx, ERROR_NO_MORE_ENTRIES)
            return 0

        # initial named lookup
        abs_name = ctx.path_mgr.ami_abs_path(self.get_current_dir(ctx), name)
        volume = ctx.path_mgr.ami_volume_of_path(abs_name)
        entry = self.dos_list.get_entry_by_name(volume) if volume else None

        if (
            entry is not None
            and entry.struct_def is DosListAssignStruct
            and entry.locks
        ):
            # an assign: hand out its primary directory lock. A
            # multi-directory assign asks the caller to loop (DVPF_ASSIGN)
            flags = self.DVPF_ASSIGN if len(entry.locks) > 1 else 0
            lock = entry.locks[0]
            port = self._port_of_lock(lock, volume)
            addr = self._new_devproc(ctx, name, port, lock, flags, entry.mem.addr)
        elif entry is not None and entry.locks:
            # a volume: use its DOS list root lock
            lock = entry.locks[0]
            port = self._port_of_lock(lock, volume)
            addr = self._new_devproc(ctx, name, port, lock, 0, entry.mem.addr)
        else:
            # a device (NIL:, CONSOLE:, ...) or an unknown volume: the DevProc
            # owns a temporary root lock that FreeDeviceProc releases
            vol_name = entry.name if entry is not None else volume
            lock = (
                self.lock_mgr.create_lock(None, vol_name + ":", False)
                if vol_name
                else None
            )
            flags = self.DVPF_UNLOCK if lock is not None else 0
            port = self._port_of_lock(lock, vol_name or name)
            devnode = entry.mem.addr if entry is not None else 0
            addr = self._new_devproc(ctx, name, port, lock, flags, devnode)

        log_dos.info(
            "GetDeviceProc: name='%s' devproc=%06x -> volume=%s devproc=%06x",
            name,
            last_devproc,
            volume,
            addr,
        )
        self.setioerr(ctx, NO_ERROR)
        return addr

    def _enumerate_devproc(self, ctx, last_devproc):
        """one device entry of a ``GetDeviceProc("*")`` enumeration

        Like AmigaDOS the DevProc handed in is reused in place; it is only
        freed once the device list is exhausted.
        """
        flags = self.dos_list.LDF_DEVICES
        prev = None
        if last_devproc == 0:
            entry = self.dos_list.get_first_entry(flags)
        else:
            prev = DevProcStruct(ctx.mem, last_devproc)
            node = prev.dvp_DevNode.aptr
            cur = self.dos_list.get_entry_by_b_addr(node >> 2) if node else None
            entry = self.dos_list.get_next_entry(cur, flags)
        if entry is None:
            if prev is not None:
                self._release_devproc_lock(prev)
                self._free_mem(last_devproc)
            self.setioerr(ctx, ERROR_NO_MORE_ENTRIES)
            return 0
        if prev is not None:
            self._release_devproc_lock(prev)
        # each step hands out a temporary root lock owned by the DevProc
        lock = self.lock_mgr.create_lock(None, entry.name + ":", False)
        dev_flags = self.DVPF_UNLOCK if lock is not None else 0
        port = self._port_of_lock(lock, entry.name)
        if prev is not None:
            prev.dvp_Port.aptr = port
            prev.dvp_Lock.aptr = (lock.b_addr << 2) if lock is not None else 0
            prev.dvp_Flags.val = dev_flags
            prev.dvp_DevNode.aptr = entry.mem.addr
            addr = last_devproc
        else:
            addr = self._new_devproc(
                ctx, entry.name, port, lock, dev_flags, entry.mem.addr
            )
        log_dos.info(
            "GetDeviceProc('*'): devproc=%06x -> device=%s", last_devproc, entry.name
        )
        self.setioerr(ctx, NO_ERROR)
        return addr

    def _advance_assign_devproc(self, ctx, addr):
        """advance an in-place multi-directory assign DevProc

        Returns True if the DevProc now points at the next directory, False
        when the assign has no further directory.
        """
        devproc = DevProcStruct(ctx.mem, addr)
        if not (devproc.dvp_Flags.val & self.DVPF_ASSIGN):
            return False
        entry = self.dos_list.get_entry_by_b_addr(devproc.dvp_DevNode.aptr >> 2)
        if entry is None:
            return False
        locks = entry.locks
        cur = devproc.dvp_Lock.aptr
        index = None
        for i, lock in enumerate(locks):
            if (lock.b_addr << 2) == cur:
                index = i
                break
        if index is None or index + 1 >= len(locks):
            return False
        lock = locks[index + 1]
        devproc.dvp_Lock.aptr = lock.b_addr << 2
        devproc.dvp_Port.aptr = self._port_of_lock(lock, entry.name)
        return True

    def _release_devproc_lock(self, devproc):
        """release the temporary lock a DevProc owns (DVPF_UNLOCK)"""
        if (devproc.dvp_Flags.val & self.DVPF_UNLOCK) and devproc.dvp_Lock.aptr != 0:
            lock = self.lock_mgr.get_by_b_addr(devproc.dvp_Lock.aptr >> 2)
            self.lock_mgr.release_lock(lock)
        devproc.dvp_Lock.aptr = 0
        devproc.dvp_Flags.val &= ~self.DVPF_UNLOCK

    def FreeDeviceProc(self, ctx):
        addr = ctx.cpu.r_reg(REG_D1)
        if addr == 0:
            return
        devproc = DevProcStruct(ctx.mem, addr)
        self._release_devproc_lock(devproc)
        self._free_mem(addr)
        log_dos.info("FreeDeviceProc: devproc=%06x", addr)

    # ----- Matcher -----

    def MatchFirst(self, ctx):
        pat_ptr = ctx.cpu.r_reg(REG_D1)
        pat = ctx.mem.r_cstr(pat_ptr)
        anchor_ptr = ctx.cpu.r_reg(REG_D2)
        anchor = AnchorPathStruct(ctx.mem, anchor_ptr)

        # create MatchFirstNext instance
        mfn = MatchFirstNext(
            ctx.path_mgr, self.lock_mgr, self.get_current_dir(ctx), pat, anchor
        )
        log_dos.info(
            "MatchFirst: pat='%s' anchor=%06x strlen=%d flags=%02x-> ok=%s",
            pat,
            anchor_ptr,
            mfn.str_len,
            mfn.flags,
            mfn.ok,
        )
        if not mfn.ok:
            self.matches[anchor_ptr] = mfn
            self.setioerr(ctx, ERROR_BAD_TEMPLATE)
            return self.io_err
        log_dos.debug("MatchFirst: %s", mfn.matcher)

        # try first match
        err = mfn.first(ctx)
        self.setioerr(ctx, err)
        if self.io_err == NO_ERROR:
            log_dos.info(
                "MatchFirst: found name='%s' path='%s' -> parent lock %s, io_err=%d",
                mfn.name,
                mfn.path,
                mfn.dir_lock,
                self.io_err,
            )
            self.matches[anchor_ptr] = mfn
        # no entry found or error
        elif self.io_err == ERROR_OBJECT_NOT_FOUND:
            log_dos.info("MatchFirst: none found")
            self.matches[anchor_ptr] = mfn
        else:
            # Dos also creates a matcher on failure...
            self.matches[anchor_ptr] = mfn
            log_dos.info("MatchFirst: error: %d", self.io_err)
        return self.io_err

    def MatchNext(self, ctx):
        anchor_ptr = ctx.cpu.r_reg(REG_D1)
        log_dos.info("MatchNext: anchor=%06x", anchor_ptr)
        # retrieve match
        if anchor_ptr not in self.matches:
            raise VamosInternalError(
                "MatchNext: No matcher found for %06x" % anchor_ptr
            )
        mfn = self.matches[anchor_ptr]
        # has matches?
        if mfn != None:
            self.setioerr(ctx, mfn.next(ctx))
            if self.io_err == NO_ERROR:
                log_dos.info(
                    "MatchNext: found name='%s' path=%s -> parent lock %s, io_err=%d",
                    mfn.name,
                    mfn.path,
                    mfn.dir_lock,
                    self.io_err,
                )
            elif self.io_err == ERROR_NO_MORE_ENTRIES:
                log_dos.info("MatchNext: no more entries!")
            else:
                log_dos.info("MatchNext: error: %d", self.io_err)
            return self.io_err

    def MatchEnd(self, ctx):
        anchor_ptr = ctx.cpu.r_reg(REG_D1)
        log_dos.info("MatchEnd: anchor=%06x ", anchor_ptr)
        # retrieve match
        if anchor_ptr not in self.matches:
            raise VamosInternalError("MatchEnd: No matcher found for %06x" % anchor_ptr)
        mfn = self.matches[anchor_ptr]
        del self.matches[anchor_ptr]
        if mfn != None:
            mfn.end(ctx)

    # ----- Pattern Parsing and Matching -----

    def parsePattern(self, ctx, ignore_case=False):
        src_ptr = ctx.cpu.r_reg(REG_D1)
        dst_ptr = ctx.cpu.r_reg(REG_D2)
        dst_len = ctx.cpu.r_reg(REG_D3)
        src = ctx.mem.r_cstr(src_ptr)
        pat = pattern_parse(src, ignore_case=ignore_case)
        log_dos.info(
            "ParsePattern: src=%s ignore_case=%s -> pat=%s", src, ignore_case, pat
        )
        if pat == None:
            self.setioerr(ctx, ERROR_BAD_TEMPLATE)
            return -1
        else:
            self.setioerr(ctx, NO_ERROR)
            pat_str = pat.pat_str
            if len(pat_str) >= dst_len:
                return -1
            else:
                ctx.mem.w_cstr(dst_ptr, pat_str)
                if pat.has_wildcard:
                    return 1
                else:
                    return 0

    def ParsePattern(self, ctx):
        return self.parsePattern(ctx, False)

    def ParsePatternNoCase(self, ctx):
        return self.parsePattern(ctx, True)

    def matchPattern(self, ctx, ignore_case=False):
        pat_ptr = ctx.cpu.r_reg(REG_D1)
        txt_ptr = ctx.cpu.r_reg(REG_D2)
        pat = ctx.mem.r_cstr(pat_ptr)
        txt = ctx.mem.r_cstr(txt_ptr)
        pattern = Pattern(None, pat, ignore_case, True)
        match = pattern_match(pattern, txt)
        log_dos.info(
            "MatchPattern: pat=%s txt=%s ignore_case=%s -> match=%s",
            pat,
            txt,
            ignore_case,
            match,
        )
        if match:
            return -1
        else:
            return 0

    def MatchPattern(self, ctx):
        return self.matchPattern(ctx)

    def MatchPatternNoCase(self, ctx):
        return self.matchPattern(ctx, ignore_case=True)

    # ----- Args -----

    def FindArg(self, ctx):
        template_ptr = ctx.cpu.r_reg(REG_D1)
        keyword_ptr = ctx.cpu.r_reg(REG_D2)
        template = ctx.mem.r_cstr(template_ptr)
        keyword = ctx.mem.r_cstr(keyword_ptr)
        # parse template
        tal = TemplateArgList.parse_string(template)
        if tal is None:
            # template parse error
            log_dos.warning("FindArgs: invalid template=%s", template)
            return -1
        # find keyword
        arg = tal.find_arg(keyword)
        if arg is None:
            pos = -1
        else:
            pos = arg.pos
        log_dos.info(
            "FindArgs: template=%s keyword=%s -> %s,%d", tal, keyword, arg, pos
        )
        return pos

    def ReadArgs(self, ctx):
        template_ptr = ctx.cpu.r_reg(REG_D1)
        template = ctx.mem.r_cstr(template_ptr)
        array_ptr = ctx.cpu.r_reg(REG_D2)
        rdargs_ptr = ctx.cpu.r_reg(REG_D3)

        # 1. Check Template
        log_dos.info(
            "ReadArgs: template='%s' array_ptr=%08x rdargs_ptr=%08x",
            template,
            array_ptr,
            rdargs_ptr,
        )
        tal = TemplateArgList.parse_string(template)
        log_dos.info("ReadArgs: tal=%s", tal)
        if tal is None:
            log_dos.warning("ReadArgs: bad template '%s'", template)
            self.setioerr(ctx, ERROR_BAD_TEMPLATE)
            return 0

        # 2. setup CSource for input
        # use submitted csrc?
        csrc_buf_ptr = 0
        rdargs = None
        if rdargs_ptr != 0:
            rdargs = RDArgsStruct(ctx.mem, rdargs_ptr)
            csrc_buf_ptr = rdargs.RDA_Source.CS_Buffer.aptr
        if csrc_buf_ptr != 0:
            # take given csrc and setup buffer
            input_fh = None
            csrc = CSource()
            csrc.read_s(ctx.alloc, rdargs_ptr)
        else:
            # setup file based csrc and read first line
            input_fh = ctx.process.get_input()
            csrc = FileLineCSource(input_fh)
            csrc.append_line()
        log_dos.info("ReadArgs: input=%s csrc=%s", input_fh, csrc)

        # 3. was help requested with '?'
        if rdargs is None:
            flags = 0
            ext_help = None
        else:
            flags = rdargs.RDA_Flags.val
            ext_help_ptr = rdargs.RDA_ExtHelp.aptr
            ext_help = ctx.mem.r_cstr(ext_help_ptr) if ext_help_ptr else None
        log_dos.info("ReadArgs: flags=%s ext_help=%s", flags, ext_help)
        RDAF_NOPROMPT = 4
        # prompting is allowed?
        if flags & RDAF_NOPROMPT == 0:
            ah = ArgsHelp(csrc)
            # user entered '?'
            if ah.want_help():
                ctx.process.get_output().write(template.encode("latin1") + b": ")
                csrc.append_line()
                msg = ext_help if ext_help else template
                # ext help is shown on second '?'
                while ah.want_help():
                    ctx.process.get_output().write(template.encode("latin1") + b": ")
                    csrc.append_line()
            csrc.rewind(ah.get_num_bytes())

        # 4. parse csrc with given template
        log_dos.info("ReadArgs: parse input: %s @%d", repr(csrc.buf), csrc.pos)
        p = ArgsParser(tal)
        error = p.parse(csrc)
        result_list = p.get_result_list()
        log_dos.info(
            "ReadArgs: parse error=%d list=%s", error, result_list.get_results()
        )

        # 5. always sync back csrc position
        if input_fh is None:
            csrc.update_s(ctx.alloc, rdargs_ptr)

        # parse failed
        if error != 0:
            rdargs_ptr = 0
        # parse ok
        else:
            # 6. calc and allocate extra memory
            total_bytes, num_longs = result_list.calc_extra_result_size()
            log_dos.info(
                "ReadArgs: extra memory: total_bytes=%d num_longs=%d",
                total_bytes,
                num_longs,
            )
            if total_bytes > 0:
                extra_ptr = self._alloc_mem(
                    "ReadArgs(@%06x)" % self.get_callee_pc(ctx), total_bytes
                )
                if extra_ptr == 0:
                    log_dos.warning("ReadArgs: no memory for extra")
                    self.setioerr(ctx, ERROR_NO_FREE_STORE)
                    return 0
            else:
                extra_ptr = 0

            # 7. write array and extra memory from result list
            result_list.generate_result(ctx.mem, array_ptr, extra_ptr, num_longs)

            # 8. alloc custom rdargs if none is given
            if rdargs_ptr == 0:
                rdargs = ctx.alloc.alloc_astruct(RDArgsStruct, label="RDArgs")
                rdargs_ptr = rdargs.addr
                own = True
            else:
                own = False
            # own house keeping
            self.rdargs[rdargs_ptr] = (rdargs, own)

            # 9. store extra buffer
            rdargs.RDA_Buffer.aptr = extra_ptr
            rdargs.RDA_BufSiz.val = total_bytes

        # done
        self.setioerr(ctx, error)
        return rdargs_ptr

    def FreeArgs(self, ctx):
        rdargs_ptr = ctx.cpu.r_reg(REG_D1)
        log_dos.info("FreeArgs: %06x", rdargs_ptr)
        # find rdargs
        if rdargs_ptr not in self.rdargs:
            raise VamosInternalError("Can't find RDArgs: %06x" % rdargs_ptr)
        rdargs, own = self.rdargs[rdargs_ptr]
        del self.rdargs[rdargs_ptr]
        # clean up rdargs
        addr = rdargs.RDA_Buffer.aptr
        if addr != 0:
            self._free_mem(addr)
        # free our memory
        if own:
            rdargs.free()

    def ReadItem(self, ctx):
        buff_ptr = ctx.cpu.r_reg(REG_D1)
        maxchars = ctx.cpu.r_reg(REG_D2)
        csrc_ptr = ctx.cpu.r_reg(REG_D3)
        log_dos.info(
            "ReadItem: buff_ptr=%06x maxchars=%d csource_ptr=%06x",
            buff_ptr,
            maxchars,
            csrc_ptr,
        )
        if csrc_ptr:
            csrc = CSource()
            csrc.read_s(ctx.alloc, csrc_ptr)
            input_fh = None
        else:
            input_fh = ctx.process.get_input()
            csrc = FileCSource(input_fh)
        # no pointer
        if buff_ptr == 0:
            return 0  # ITEM_NOTHING
        # Well Known Bug: buff[0] = 0, even if maxchars == 0
        ctx.mem.w8(buff_ptr, 0)
        if maxchars <= 0:
            return 0
        # reset IOErr if not BNULL nor NIL:
        if input_fh is not None and not input_fh.is_nil:
            self.setioerr(ctx, 0)
        # get item
        parser = ItemParser(csrc)
        res, data = parser.read_item(maxchars)
        log_dos.info("ReadItem: res=%d data=%s", res, data)
        # Write back the updated csource ptr if we have one
        if csrc_ptr:
            csrc.update_s(ctx.alloc, csrc_ptr)
        # write string
        if data is not None:
            ctx.mem.w_cstr(buff_ptr, data)
        return res

    # ----- System/Execute -----

    def SystemTagList(self, ctx, cmd: CSTR, tag_list: TagList):
        cmd = cmd.get_str()
        return self._system_tag_list(ctx, cmd, tag_list)

    def _system_tag_list(self, ctx, cmd, tag_list):
        log_dos.info("SystemTagList: cmd=%s tags=%s ctx=%s", cmd, tag_list, ctx)
        # cmd is at this point a full string of commands to execute.
        # If we're running from the Amiga shell, forward this to the shell
        # anyhow.
        if ctx.process.is_native_shell():
            cli_addr = ctx.process.get_cli_struct()
            cli = CLIStruct(ctx.mem, cli_addr)
            new_input = self.file_mgr.open(None, "NIL:", "r")
            if new_input == None:
                log_dos.warning(
                    "SystemTagList: can't create new input file handle for SystemTagList('%s')",
                    cmd,
                )
                return 0xFFFFFFFF
            # Push-back the commands into the input buffer.
            if cmd:
                new_input.setbuf(cmd)
            new_stdin = self.file_mgr.open(None, "*", "rw")
            outtag = (
                tag_list.find_tag(DosTag.SYS_Output) if tag_list is not None else None
            )
            # print "setting new input to %s" % new_input
            # and install this as current input. The shell will read from that
            # instead until it hits the EOF
            input_fhsi = cli.cli_StandardInput.aptr
            input_fhci = cli.cli_CurrentInput.aptr
            if outtag:
                data = outtag.get_data()
                if data != 0:
                    output_fhci = cli.cli_StandardOutput.aptr
                    cli.cli_StandardOutput.aptr = data << 2
            else:
                output_fhci = None
            cli.cli_CurrentInput.aptr = new_input.mem.addr
            cli.cli_StandardInput.aptr = new_stdin.mem.addr
            cli.cli_Background.val = DOSTRUE_S
            # Create the Packet for the background process.
            packet = ctx.process.run_system()
            stack_size = cli.cli_DefaultStack.val << 2
            current_dir = ctx.process.get_current_dir()
            cur_lock = self.lock_mgr.get_by_b_addr(current_dir >> 2)
            dup_lock = self.lock_mgr.dup_lock(self.get_current_dir(ctx))
            cur_module = cli.cli_Module.aptr
            cur_out = ctx.process.this_task.pr_COS.aptr
            cur_setname = ctx.mem.r_bstr(cli.cli_SetName.aptr)
            cli.cli_Module.aptr = 0
            ctx.process.set_current_dir(dup_lock.mem.addr)
            self.cur_dir_lock = dup_lock

            # run command
            reg_d1 = packet >> 2
            code_start = ctx.process.shell_start
            log_dos.info("(Shell)SystemTagList: pc=%06x", code_start)
            ret_code = run_command(ctx.process, code_start, 0, 0, stack_size, reg_d1)
            log_dos.info(
                "(Shell)SystemTagList returned: cmd='%s' tags=%s: ret_code=%d",
                cmd,
                tag_list,
                ret_code,
            )

            # shutdown
            cli.cli_CurrentInput.aptr = input_fhci
            cli.cli_StandardInput.aptr = input_fhsi
            cli.cli_Background.val = DOSFALSE
            cli.cli_Module.aptr = cur_module
            if output_fhci != None:
                cli.cli_StandardOutput.aptr = output_fhci
            # Channels are closed by the dying shell
            ctx.mem.w_bstr(cli.cli_SetName.aptr, cur_setname)
            ctx.process.this_task.pr_CIS.aptr = input_fhci
            ctx.process.this_task.pr_COS.aptr = cur_out
            # infile = self.file_mgr.get_by_b_addr(input_fhci >> 2,False)
            # infile.setbuf("")
            ctx.process.set_current_dir(current_dir)
            self.cur_dir_lock = self.lock_mgr.get_by_b_addr(current_dir >> 2)
            self.setioerr(ctx, ret_code)
            return 0
        else:
            # parse "command line"
            cl = CommandLine()
            res = cl.parse_line(cmd)
            if res != cl.LINE_OK:
                log_dos.info("SystemTagList: error parsing command: '%s' -> %d", res)
                return 10  # RETURN_ERROR
            # TODO: redirs
            binary = cl.get_cmd()
            arg_str = cl.get_arg_str()
            log_dos.info("SystemTagList: bin='%s' arg_str='%s'", binary, arg_str[:-1])
            # fetch current dir for current process
            cur_proc = ctx.process
            cwd_lock = cur_proc.cwd_lock
            cwd = cur_proc.cwd
            # create a process and run it...
            proc = Process(ctx, binary, arg_str, cwd=cwd, cwd_lock=cwd_lock)
            if not proc.ok:
                log_dos.warning(
                    "SystemTagList: can't create process for '%s' args=%s",
                    binary,
                    arg_str,
                )
                return DOSTRUE
            return run_sub_process(ctx.scheduler, ctx.runner, proc)

    def _load_seg_list(self, ctx, name, lock):
        """load a seglist by Amiga path and register it for UnLoadSeg"""
        b_addr = ctx.seg_loader.load_ami_seglist(name, lock)
        if b_addr == 0:
            log_dos.warning("LoadSeg: '%s' -> not found!", name)
            return 0
        # overlay seglists are returned as negative BPTR
        info = ctx.seg_loader.get_info(b_addr)
        if info.has_overlay():
            b_addr = -b_addr
        log_dos.info("LoadSeg: '%s' -> %06x", name, b_addr)
        self.seg_lists[b_addr] = name
        return b_addr

    def _unload_seg_list(self, ctx, b_addr):
        """unload a seglist booked by LoadSeg/NewLoadSeg"""
        if b_addr >= 0x80000000:
            b_addr -= 0x100000000
        if b_addr != 0:
            if b_addr not in self.seg_lists:
                raise VamosInternalError(
                    "Trying to unload unknown LoadSeg seg_list: b_addr=%06x" % b_addr
                )
            else:
                del self.seg_lists[b_addr]
                ctx.seg_loader.unload_seglist(abs(b_addr))
                log_dos.info("UnLoadSeg: %06x", b_addr)
        else:
            log_dos.info("UnLoadSeg:  NULL")

    def LoadSeg(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        name = ctx.mem.r_cstr(name_ptr)
        lock = self.get_current_dir(ctx)
        return self._load_seg_list(ctx, name, lock)

    def UnLoadSeg(self, ctx):
        b_addr = ctx.cpu.r_reg(REG_D1)
        self._unload_seg_list(ctx, b_addr)

    def InternalLoadSeg(self, ctx):
        fh_baddr = ctx.cpu.r_reg(REG_D0)
        table_ptr = ctx.cpu.r_reg(REG_A0)
        func_ptr = ctx.cpu.r_reg(REG_A1)
        stack_ptr = ctx.cpu.r_reg(REG_A2)
        # FIXME: For now, just fail
        log_dos.warning(
            "InternalLoadSeg: fh=%06x table=%06x funcptr=%06x stack_ptr=%06x -> not implemented!",
            fh_baddr,
            table_ptr,
            func_ptr,
            stack_ptr,
        )
        self.setioerr(ctx, ERROR_OBJECT_WRONG_TYPE)
        return 0

    def RunCommand(self, ctx):
        b_addr = ctx.cpu.r_reg(REG_D1)
        if b_addr >= 0x80000000:
            b_addr -= 0x100000000
        if not b_addr in self.seg_lists:
            raise VamosInternalError(
                "Trying to run unknown LoadSeg seg_list: b_addr=%06x" % b_addr
            )
        else:
            name = self.seg_lists[b_addr]
        stack = ctx.cpu.r_reg(REG_D2)
        args = ctx.cpu.r_reg(REG_D3)
        length = ctx.cpu.r_reg(REG_D4)
        fh = ctx.process.get_input()
        cmdline = ctx.mem.r_cstr(args)
        # push command line into input buffer
        input_fh = ctx.process.get_input()
        input_fh.setbuf(cmdline)
        log_dos.info(
            "RunCommand: seglist=%06x(%s) stack=%d args=%s",
            b_addr,
            name,
            stack,
            cmdline,
        )
        # round up the stack
        stack = (stack + 3) & -4
        prog_start = (abs(b_addr) << 2) + 4
        ret_code = run_command(ctx.process, prog_start, args, length, stack)
        # clear input
        input_fh.setbuf("")
        return ret_code

    # ----- Path Helper -----

    def FilePart(self, ctx):
        addr = ctx.cpu.r_reg(REG_D1)
        path = ctx.mem.r_cstr(addr)
        pos = PathPart.file_part(path)
        if pos < len(path):
            log_dos.info("FilePart: path='%s' -> result='%s'", path, path[pos:])
        else:
            log_dos.info("FilePart: path='%s' -> pos=NULL", path)
        return addr + pos

    def PathPart(self, ctx):
        addr = ctx.cpu.r_reg(REG_D1)
        path = ctx.mem.r_cstr(addr)
        pos = PathPart.path_part(path)
        if pos < len(path):
            log_dos.info("PathPart: path='%s' -> result='%s'", path, path[:pos])
        else:
            log_dos.info("PathPart: path='%s' -> pos=NULL", path)
        return addr + pos

    def AddPart(self, ctx):
        dn_addr = ctx.cpu.r_reg(REG_D1)
        fn_addr = ctx.cpu.r_reg(REG_D2)
        size = ctx.cpu.r_reg(REG_D3)
        dn = ctx.mem.r_cstr(dn_addr)
        fn = ctx.mem.r_cstr(fn_addr)
        np = PathPart.add_part(dn, fn, size)
        log_dos.info("AddPart: dn='%s' fn='%s' size=%d -> np='%s'", dn, fn, size, np)
        if np != None:
            ctx.mem.w_cstr(dn_addr, np)
            return DOSTRUE
        else:
            return DOSFALSE

    def SplitName(
        self,
        ctx,
        name: CSTR,
        separator: UBYTE,
        buf: APTR_VOID,
        oldpos: LONG,
        size: LONG,
    ):
        name_str = name.str if name is not None else ""
        pos, part = PathPart.split_name(
            name_str, int(separator), int(oldpos), int(size)
        )
        ctx.mem.w_cstr(buf.aptr, part)
        log_dos.info(
            "SplitName: name='%s' sep=%d oldpos=%d size=%d -> pos=%d part='%s'",
            name_str,
            int(separator),
            int(oldpos),
            int(size),
            pos,
            part,
        )
        return pos

    # ----- DosObjects -----

    def AllocDosObject(self, ctx):
        obj_type = ctx.cpu.r_reg(REG_D1)
        tags_ptr = ctx.cpu.r_reg(REG_D2)
        if obj_type == 0:  # DOS_FILEHANDLE
            name = "DOS_FILEHANDLE"
            struct_def = FileHandleStruct
        elif obj_type == 1:  # DOS_EXALLCONTROL
            name = "DOS_EXALLCONTROL"
            struct_def = ExAllControlStruct
        elif obj_type == 2:  # DOS_FIB
            name = "DOS_FIB"
            struct_def = FileInfoBlockStruct
        elif obj_type == 3:  # DOS_STDPKT
            name = "DOS_STDPKT"
            struct_def = DosPacketStruct
        elif obj_type == 4:  # DOS_CLI
            name = "DOS_CLI"
            struct_def = CLIStruct
        elif obj_type == 5:  # DOS_RDARGS
            name = "DOS_RDARGS"
            struct_def = RDArgsStruct
        else:
            log_dos.error("AllocDosObject: invalid type=%d", obj_type)
            return 0
        if struct_def is None:
            log_dos.warning("AllocDosObject: unsupported type=%d/%s", obj_type, name)
            return 0
        # allocate struct
        dos_obj = ctx.alloc.alloc_astruct(struct_def, label=name)
        log_dos.info(
            "AllocDosObject: type=%d/%s tags_ptr=%08x -> dos_obj=%s",
            obj_type,
            name,
            tags_ptr,
            dos_obj,
        )
        # store struct
        ptr = dos_obj.addr
        self.dos_objs[ptr] = (dos_obj, obj_type)
        # pre fill struct
        if obj_type == 0:
            dos_obj.fh_Pos.val = 0xFFFFFFFF
            dos_obj.fh_End.val = 0xFFFFFFFF
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
                log_dos.warning(
                    "FreeDosObject: type mismatch %d != %d", obj_type, entry[1]
                )
            # Freeing a control also releases an unfinished scan.
            if entry[1] == 1:
                self._drop_exall_scan(ptr)
            # free struct
            ctx.alloc.free_struct(entry[0])
        else:
            log_dos.error(
                "FreeDosObject: type=%d ptr=%08x -> NOT FOUND!", obj_type, ptr
            )

    # ----- Cli support ---

    def CliInit(self, ctx, dp: DosPacket):
        # Init style shells are not needed anymore
        log_dos.error("CliInit: not supported/needed!")
        return 0

    def CliInitNewcli(self, ctx, dp: DosPacket):
        # NewCLI style shells are not supported
        log_dos.error("CliInitNewcli: not supported/needed!")
        return 0

    def CliInitRun(self, ctx, dp: DosPacket):
        # check dos packet
        type = dp.type.val
        res1 = dp.res1.val
        res2 = dp.res2.val
        log_dos.info(
            "CliInitRun pkt@%08x type=%d res1=%d res2=%d", dp.addr, type, res1, res2
        )
        # run style
        if type != 0 and res1 == 0 and res2 == 0:
            # setup CLI with legacy CliInit
            return 0x80000008  # valid, and a async Run call.
        else:
            log_dos.warning(
                "CliInitRun: unsupported mode: type=%d res1=%d res2=%d",
                type,
                res1,
                res2,
            )
            return 0

    # ----- DosList -------------

    def LockDosList(self, ctx):
        flags = ctx.cpu.r_reg(REG_D1)
        node = self.dos_list.lock_dos_list(flags)
        return node

    def UnLockDosList(self, ctx):
        flags = ctx.cpu.r_reg(REG_D1)
        self.dos_list.unlock_dos_list(flags)

    def NextDosEntry(self, ctx):
        flags = ctx.cpu.r_reg(REG_D2)
        node = ctx.cpu.r_reg(REG_D1)
        return self.dos_list.next_dos_entry(flags, node)

    def FindDosEntry(self, ctx):
        dlist = ctx.cpu.r_reg(REG_D1)
        name_ptr = ctx.cpu.r_reg(REG_D2)
        flags = ctx.cpu.r_reg(REG_D3)
        if name_ptr == 0:
            log_dos.info(
                "FindDosEntry(dlist=0x%x, name=NULL, flags=0x%x) -> 0",
                dlist,
                flags,
            )
            return 0
        try:
            name = ctx.mem.r_cstr(name_ptr)
        except Exception:
            log_dos.info("FindDosEntry: failed to read CSTR at 0x%x", name_ptr)
            return 0
        if name and name.endswith(":"):
            name = name[:-1]
        entry = self.dos_list.get_entry_by_name(name, flags)
        if entry is None:
            log_dos.info("FindDosEntry('%s', flags=0x%x) -> 0 (not found)", name, flags)
            return 0
        entry_type = entry.struct.dol_Type.val
        type_matches = False
        if entry_type == 0 and (flags & 4):
            type_matches = True
        elif entry_type == 2 and (flags & 8):
            type_matches = True
        elif entry_type == 1 and (flags & 16):
            type_matches = True
        if not type_matches:
            log_dos.info(
                "FindDosEntry('%s', flags=0x%x) -> 0 (type %d doesn't match)",
                name,
                flags,
                entry_type,
            )
            return 0
        log_dos.info(
            "FindDosEntry('%s', flags=0x%x) -> 0x%x",
            name,
            flags,
            entry.mem.addr,
        )
        return entry.mem.addr

    def AttemptLockDosList(self, ctx):
        flags = ctx.cpu.r_reg(REG_D1)
        log_dos.info("AttemptLockDosList(flags=0x%x)", flags)
        return self.dos_list.lock_dos_list(flags)

    def Inhibit(self, ctx, name: CSTR, onoff):
        dev_name = name.str if name else ""
        if dev_name.endswith(":"):
            dev_name = dev_name[:-1]
        entry = self.dos_list.get_entry_by_name(dev_name)
        if (
            entry is None
            or entry.struct.dol_Type.val != 0
            or not entry.exclusive
            or entry.struct.dol_Task.aptr != 0
        ):
            self.setioerr(ctx, ERROR_DEVICE_NOT_MOUNTED)
            log_dos.info("Inhibit('%s', %d) -> false", dev_name, onoff)
            return DOSFALSE
        entry.inhibited = bool(onoff)
        self.setioerr(ctx, NO_ERROR)
        log_dos.info("Inhibit('%s', %d) -> true", dev_name, onoff)
        return DOSTRUE

    def MakeDosEntry(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        entry_type = ctx.cpu.r_reg(REG_D2)
        try:
            name = ctx.mem.r_cstr(name_ptr) if name_ptr else ""
        except Exception:
            name = ""
        if not name:
            name = f"vol_{entry_type:x}"
        struct_defs = {
            0: DosListDeviceStruct,
            1: DosListAssignStruct,
            2: DosListVolumeStruct,
        }
        struct_def = struct_defs.get(entry_type)
        if struct_def is None:
            self.setioerr(ctx, ERROR_OBJECT_WRONG_TYPE)
            return 0
        entry = ctx.alloc.alloc_astruct(struct_def, label=f"DosList({name})")
        entry.dol_Next.aptr = 0
        entry.dol_Type.val = entry_type
        entry.dol_Task.aptr = 0
        entry.dol_Lock.aptr = 0
        if struct_def is DosListDeviceStruct:
            entry.dol_Handler.aptr = 0
            entry.dol_StackSize.val = 0
            entry.dol_Priority.val = 0
            entry.dol_Startup.val = 0
            entry.dol_SegList.aptr = 0
            entry.dol_GlobVec.aptr = 0
        elif struct_def is DosListVolumeStruct:
            entry.dol_LockList.aptr = 0
            entry.dol_DiskType.val = 0
        else:
            entry.dol_List.aptr = 0
        name_mem = ctx.alloc.alloc_bstr(name, label="DosListName")
        entry.dol_Name.aptr = name_mem.addr
        self.dos_entries[entry.addr] = {
            "mem": entry,
            "name": name_mem,
            "name_text": name,
            "dos_list_entry": None,
        }
        log_dos.info(
            "MakeDosEntry('%s', type=%d) -> 0x%x", name, entry_type, entry.addr
        )
        return entry.addr

    def AddDosEntry(self, ctx):
        dlist_ptr = ctx.cpu.r_reg(REG_D1)
        record = self.dos_entries.get(dlist_ptr)
        ok = record is not None and record["dos_list_entry"] is None
        if ok:
            try:
                record["dos_list_entry"] = self.dos_list.add_existing_entry(
                    record["name_text"], record["mem"], record["name"]
                )
            except ValueError:
                ok = False
            else:
                self.update_dos_list_head()
        log_dos.info("AddDosEntry(0x%x) -> %s", dlist_ptr, ok)
        return DOSTRUE if ok else DOSFALSE

    def RemDosEntry(self, ctx):
        dlist_ptr = ctx.cpu.r_reg(REG_D1)
        record = self.dos_entries.get(dlist_ptr)
        entry = record["dos_list_entry"] if record is not None else None
        ok = entry is not None and self.dos_list.remove_entry(entry)
        if ok:
            record["dos_list_entry"] = None
            self.update_dos_list_head()
        log_dos.info("RemDosEntry(0x%x) -> %s", dlist_ptr, ok)
        return DOSTRUE if ok else DOSFALSE

    def FreeDosEntry(self, ctx):
        dlist_ptr = ctx.cpu.r_reg(REG_D1)
        entry = self.dos_entries.pop(dlist_ptr, None)
        if entry:
            linked_entry = entry["dos_list_entry"]
            if linked_entry is not None:
                self.dos_list.remove_entry(linked_entry)
                self.update_dos_list_head()
            ctx.alloc.free_bstr(entry["name"])
            ctx.alloc.free_struct(entry["mem"])
        log_dos.info("FreeDosEntry(0x%x)", dlist_ptr)
        return 0

    def CreateNewProc(self, ctx, tags: TagList):
        if tags is None:
            log_dos.warning("CreateNewProc: NULL tags")
            return 0

        tag_list = tags.to_list(map_enum=DosTag, do_map=True)
        log_dos.info("CreateNewProc: tags=%s", tag_list)

        entry_pc = tags.get_tag_data(DosTag.NP_Entry, 0)
        seglist_bptr = tags.get_tag_data(DosTag.NP_SegList, 0)
        stack_size = tags.get_tag_data(DosTag.NP_StackSize, 4096)
        name_ptr = tags.get_tag_data(DosTag.NP_Name, 0)
        priority = tags.get_tag_data(DosTag.NP_Priority, 0)
        current_dir = tags.get_tag_data(DosTag.NP_CurrentDir, 0)
        home_dir = tags.get_tag_data(DosTag.NP_HomeDir, 0)
        input_fh = tags.get_tag_data(DosTag.NP_Input, 0)
        output_fh = tags.get_tag_data(DosTag.NP_Output, 0)

        name = ctx.mem.r_cstr(name_ptr) if name_ptr != 0 else "child_process"
        if entry_pc == 0 and seglist_bptr == 0:
            log_dos.warning("CreateNewProc: no NP_Entry or NP_SegList")
            return 0
        if entry_pc == 0 and seglist_bptr != 0:
            seg_addr = seglist_bptr << 2
            entry_pc = seg_addr + 4

        log_dos.info(
            "CreateNewProc: name=%s entry=%06x stack=%d pri=%d",
            name,
            entry_pc,
            stack_size,
            priority,
        )

        # the child is a process of its own: the scheduler runs it beside
        # its parent, and it is freed once its task ends (_child_proc_event)
        child = self.create_child_process(
            ctx,
            name,
            stack_size=stack_size,
            start_pc=entry_pc,
            start_regs={REG_D0: 0, REG_A0: 0},
        )
        proc = child.proc
        task = proc.task
        stack = child.get_stack()
        task.node.pri.val = priority
        task.sp_reg.aptr = stack.get_initial_sp()
        task.sp_lower.aptr = stack.get_lower()
        task.sp_upper.aptr = stack.get_upper()
        proc.stack_size.val = stack.get_size()
        proc.stack_base.bptr = stack.get_lower() >> 2
        proc.seg_list.bptr = seglist_bptr
        proc.glob_vec.aptr = 0xFFFFFFFF
        proc.current_dir.bptr = current_dir
        proc.home_dir.bptr = home_dir
        proc.window_ptr.aptr = 0xFFFFFFFF

        if input_fh == 0 or output_fh == 0:
            parent_proc = ctx.exec_lib.exec_lib.this_task.aptr
            if parent_proc != 0:
                parent = ProcessStruct(ctx.mem, parent_proc)
                if input_fh == 0:
                    input_fh = parent.cis.bptr
                if output_fh == 0:
                    output_fh = parent.cos.bptr
        proc.cis.bptr = input_fh
        proc.cos.bptr = output_fh

        # the process port is signalled with SIGB_DOS. it is no public port:
        # FindPort() does not find it, a child that wants one adds its own
        port = proc.msg_port
        port.new(flags=MsgPortFlags.PA_SIGNAL, sig_bit=8, sig_task=task)
        port_addr = port.addr
        if not ctx.exec_lib.port_mgr.has_port(port_addr):
            ctx.exec_lib.port_mgr.register_port(port_addr)

        sched_task = child.get_sched_task()
        self.child_procs[sched_task] = child
        ctx.scheduler.add_task(sched_task)
        # add_task() marks the task TS_ADDED. a new process is ready on the Amiga
        task.state.val = TaskState.TS_READY

        log_dos.info(
            "CreateNewProc: created process %06x entry=%06x port=%06x",
            proc.addr,
            entry_pc,
            port_addr,
        )
        return proc.addr

    def AssignLock(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        lockbaddr = ctx.cpu.r_reg(REG_D2)
        name = ctx.mem.r_cstr(name_ptr)
        if lockbaddr == 0:
            log_dos.info("AssignLock (%s -> null)", name)
            if self.dos_list.remove_assign(name):
                self.update_dos_list_head()
            return -1
        else:
            lock = self.lock_mgr.get_by_b_addr(lockbaddr)
            log_dos.info("AssignLock (%s -> %s)", name, lock)
            if self.dos_list.create_assign(name, lock) != None:
                self.update_dos_list_head()
                return -1
            return 0

    # ----- misc --------

    def StrToLong(self, ctx):
        str_addr = ctx.cpu.r_reg(REG_D1)
        val_addr = ctx.cpu.r_reg(REG_D2)
        string = ctx.mem.r_cstr(str_addr)
        match = re.search(r"(\+|\-|)[0-9]*", string)
        if len(match.group(0)) > 0:
            ctx.mem.w32(val_addr, int(match.group(0)))
            return len(match.group(0))
        else:
            return 0

    def SetCurrentDirName(self, ctx):
        str_addr = ctx.cpu.r_reg(REG_D1)
        string = ctx.mem.r_cstr(str_addr)[:79]
        cli_addr = self.Cli(ctx)
        cli = CLIStruct(ctx.mem, cli_addr)
        setaddr = cli.cli_SetName.aptr
        ctx.mem.w_bstr(setaddr, string)
        return DOSTRUE

    def SetPrompt(self, ctx):
        str_addr = ctx.cpu.r_reg(REG_D1)
        string = ctx.mem.r_cstr(str_addr)[:59]
        cli_addr = self.Cli(ctx)
        cli = CLIStruct(ctx.mem, cli_addr)
        setaddr = cli.cli_Prompt.aptr
        ctx.mem.w_bstr(setaddr, string)
        return DOSTRUE

    def DosGetString(self, ctx):
        errno = ctx.cpu.r_reg(REG_D1)
        if errno >= 0x80000000:
            errno = errno - 0x100000000
        if errno in dos_error_strings:
            if errno in self.errstrings:
                return self.errstrings[errno]
            self.errstrings[errno] = self._alloc_mem(
                "Error %d" % errno, len(dos_error_strings[errno]) + 1
            )
            ctx.mem.w_cstr(self.errstrings[errno], dos_error_strings[errno])
            return self.errstrings[errno]
        else:
            return 0

    # As we only have one file system (though with multiple assigns)
    # it does not really matter what we do here...
    def GetFileSysTask(self, ctx):
        return ctx.process.this_task.pr_FileSystemTask.aptr

    def SetFileSysTask(self, ctx):
        port = ctx.cpu.r_reg(REG_D1)
        ctx.process.this_task.pr_FileSystemTask.aptr = port

    # ----- DosPackets -----

    def ReplyPkt(self, ctx, dp: DosPacket, res1, res2):
        log_dos.info("ReplyPkt(%s, %d, %d)", dp, res1, res2)
        if res1 > 0x7FFFFFFF:
            res1 -= 0x100000000
        if res2 > 0x7FFFFFFF:
            res2 -= 0x100000000
        dp.res1.val = res1
        dp.res2.val = res2
        if dp.link.aptr == 0 or dp.port.aptr == 0:
            return 0
        reply_port = dp.port.aptr
        proc_addr = ctx.exec_lib.exec_lib.this_task.aptr
        if proc_addr != 0:
            proc = ProcessStruct(ctx.mem, proc_addr)
            dp.port.aptr = proc.msg_port.addr
        msg = MessageStruct(ctx.mem, dp.link.aptr)
        msg.node.type.val = NodeType.NT_REPLYMSG
        msg.node.succ.aptr = 0
        msg.node.pred.aptr = 0
        try:
            ctx.exec_lib.port_mgr.put_msg(reply_port, dp.link.aptr)
        except Exception:
            ctx.proxies.get_exec_lib_proxy().PutMsg(reply_port, dp.link.aptr)
        log_dos.info(
            "ReplyPkt: pkt=%06x res1=%d res2=%d -> port=%06x",
            dp.addr,
            res1,
            res2,
            reply_port,
        )
        return 0

    def _proc_reply_port(self, ctx):
        """the current process's message port (DoPkt's reply port)"""
        proc_addr = ctx.exec_lib.exec_lib.this_task.aptr
        if proc_addr == 0:
            return 0
        return ProcessStruct(ctx.mem, proc_addr).pr_MsgPort.addr

    def _send_pkt(self, ctx, dp_addr, port_addr, reply_addr):
        """fill ``dp_Port``/``dp_Link`` and put the packet on the handler port"""
        dp = DosPacketStruct(ctx.mem, dp_addr)
        msg_addr = dp.link.aptr
        if msg_addr == 0:
            # a StandardPacket: the message immediately precedes the packet
            msg_addr = dp_addr - MessageStruct.get_size()
        dp.port.aptr = reply_addr
        dp.link.aptr = msg_addr
        # vamos locates the packet through the message's ln_Name
        MessageStruct(ctx.mem, msg_addr).node.name.aptr = dp_addr
        log_dos.info(
            "SendPkt: pkt=%06x port=%06x reply=%06x msg=%06x",
            dp_addr,
            port_addr,
            reply_addr,
            msg_addr,
        )
        ctx.exec_lib.port_mgr.put_msg(port_addr, msg_addr)
        return msg_addr

    def SendPkt(self, ctx):
        dp_addr = ctx.cpu.r_reg(REG_D1)
        port_addr = ctx.cpu.r_reg(REG_D2)
        reply_addr = ctx.cpu.r_reg(REG_D3)
        self._send_pkt(ctx, dp_addr, port_addr, reply_addr)
        return 0

    def DoPkt(self, ctx):
        port_addr = ctx.cpu.r_reg(REG_D1)
        action = ctx.cpu.r_reg(REG_D2)
        args = (
            ctx.cpu.rs_reg(REG_D3),
            ctx.cpu.rs_reg(REG_D4),
            ctx.cpu.rs_reg(REG_D5),
            ctx.cpu.rs_reg(REG_D6),
            ctx.cpu.rs_reg(REG_D7),
        )
        # one block holds the StandardPacket: message followed by packet
        mem = ctx.alloc.alloc_memory(
            MessageStruct.get_size() + DosPacketStruct.get_size(), label="DoPkt"
        )
        try:
            msg_addr = mem.addr
            pkt_addr = msg_addr + MessageStruct.get_size()
            MessageStruct(ctx.mem, msg_addr).node.name.aptr = pkt_addr
            pkt = DosPacketStruct(ctx.mem, pkt_addr)
            pkt.link.aptr = msg_addr
            pkt.type.val = action
            pkt.arg1.val = args[0]
            pkt.arg2.val = args[1]
            pkt.arg3.val = args[2]
            pkt.arg4.val = args[3]
            pkt.arg5.val = args[4]
            reply_port = self._proc_reply_port(ctx)
            self._send_pkt(ctx, pkt_addr, port_addr, reply_port)
            # the handler replies synchronously while put_msg runs
            reply = self.WaitPkt(ctx)
            res1 = pkt.res1.val
            res2 = pkt.res2.val
            log_dos.info(
                "DoPkt: port=%06x action=%d args=%s -> res1=%d res2=%d (reply=%06x)",
                port_addr,
                action,
                args,
                res1,
                res2,
                reply,
            )
            self.setioerr(ctx, res2)
            return res1
        finally:
            ctx.alloc.free_memory(mem)

    def AbortPkt(self, ctx):
        port_addr = ctx.cpu.r_reg(REG_D1)
        pkt_addr = ctx.cpu.r_reg(REG_D2)
        log_dos.info("AbortPkt: port=%06x pkt=%06x -> DOSFALSE", port_addr, pkt_addr)
        return DOSFALSE

    # ----- Helpers -----

    # ----- Process/CLI (RKRM AmigaDOS 3: process properties) -----

    def _bool_result(self, ctx, ok, err):
        self.setioerr(ctx, 0 if ok else err)
        return DOSTRUE if ok else DOSFALSE

    def CreateProc(self, ctx, name: CSTR, pri: LONG, segList: LONG, stackSize: LONG):
        return Cli.create_proc(
            self, ctx, name.get_str(), pri.val, segList.val, stackSize.val
        )

    def Exit(self, ctx, returnCode: LONG):
        return Cli.exit_process(self, ctx, returnCode.val)

    def DeviceProc(self, ctx, name: CSTR):
        dev_name = name.get_str()
        if not dev_name:
            self.setioerr(ctx, ERROR_REQUIRED_ARG_MISSING)
            return 0
        abs_name = self.path_mgr.ami_abs_path(self.get_current_dir(ctx), dev_name)
        volume = str(self.path_mgr.ami_volume_of_path(abs_name) or dev_name)
        volume = volume.rstrip(":")
        dispatcher = (
            self.handler_mgr.get_dispatcher(volume)
            if self.handler_mgr is not None
            else None
        )
        if dispatcher is None:
            log_dos.warning("DeviceProc('%s'): no handler", dev_name)
            self.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
            return 0
        log_dos.info("DeviceProc('%s') -> port %06x", dev_name, dispatcher.port)
        return dispatcher.port

    def Execute(self, ctx, string: CSTR, file: LONG, file2: LONG):
        cmd = string.get_str()
        return Cli.execute(
            self,
            ctx,
            cmd,
            file.val,
            file2.val,
            lambda call_ctx, call_cmd: self._system_tag_list(call_ctx, call_cmd, None),
        )

    def GetConsoleTask(self, ctx):
        return Cli.get_console_task(ctx)

    def SetConsoleTask(self, ctx, task: LONG):
        return Cli.set_console_task(ctx, task.val)

    def SetArgStr(self, ctx, string: CSTR):
        return Cli.set_arg_str(ctx, string.aptr)

    def FindCliProc(self, ctx, num: LONG):
        return Cli.find_cli_proc(ctx, num.val)

    def MaxCli(self, ctx):
        return Cli.max_cli(ctx)

    def GetCurrentDirName(self, ctx, buf: LONG, length: LONG):
        ok, err = Cli.get_current_dir_name(ctx, buf.val, length.val)
        self.setioerr(ctx, err)
        return ok

    def SetProgramName(self, ctx, name: CSTR):
        ok, err = Cli.set_program_name(ctx, name.get_str())
        self.setioerr(ctx, err)
        return ok

    def GetPrompt(self, ctx, buf: LONG, length: LONG):
        ok, err = Cli.get_prompt(ctx, buf.val, length.val)
        self.setioerr(ctx, err)
        return ok

    def SetProgramDir(self, ctx, lock: LONG):
        return Cli.set_program_dir(ctx, lock.val)

    def GetCurrentDir(self, ctx):
        return Cli.get_current_dir(ctx)

    # ----- Record locks (RKRM AmigaDOS 3: record locking) -----

    def LockRecord(
        self,
        ctx,
        fh: LONG,
        offset: LONG,
        length: LONG,
        mode: LONG,
        timeout: LONG,
    ):
        ok, err = self.record_locks.lock_record(
            ctx, fh.val, offset.val, length.val, mode.val, timeout.val
        )
        return self._bool_result(ctx, ok, err)

    def LockRecords(self, ctx, recArray: LONG, timeout: LONG):
        ok, err = self.record_locks.lock_records(ctx, recArray.val, timeout.val)
        return self._bool_result(ctx, ok, err)

    def UnLockRecord(self, ctx, fh: LONG, offset: LONG, length: LONG):
        ok, err = self.record_locks.unlock_record(fh.val, offset.val, length.val)
        return self._bool_result(ctx, ok, err)

    def UnLockRecords(self, ctx, recArray: LONG):
        ok, err = self.record_locks.unlock_records(ctx, recArray.val)
        return self._bool_result(ctx, ok, err)

    # ----- Links (RKRM AmigaDOS 3: links and soft links) -----

    def ReadLink(
        self,
        ctx,
        port: LONG,
        lock: LONG,
        path: CSTR,
        buffer: LONG,
        size: LONG,
    ):
        ok, err = Link.read_link(
            self,
            ctx,
            port.val,
            lock.val,
            path.get_str(),
            buffer.val,
            size.val,
        )
        self.setioerr(ctx, err)
        return ok

    def MakeLink(self, ctx, name: CSTR, dest: LONG, soft: LONG):
        ok, err = Link.make_link(self, ctx, name.get_str(), dest.val, soft.val)
        return self._bool_result(ctx, ok, err)

    # ----- Assist tags -----

    # ACTION_CHANGE_MODE object type (dos/dos.h)
    CHANGE_LOCK = 0
    CHANGE_FH = 1

    def ChangeMode(self, ctx, type: LONG, fh: LONG, newmode: LONG):
        if type.val == self.CHANGE_LOCK:
            try:
                obj = self.lock_mgr.get_by_b_addr(fh.val) if fh.val else None
            except Exception:
                obj = None
            if obj is None or obj.handler is None or obj.handler_lock is None:
                self.setioerr(ctx, ERROR_INVALID_LOCK)
                return DOSFALSE
            handler, handler_obj = obj.handler, obj.handler_lock
        elif type.val == self.CHANGE_FH:
            try:
                file_handle = (
                    self.file_mgr.get_by_b_addr(fh.val, False) if fh.val else None
                )
            except Exception:
                file_handle = None
            if (
                file_handle is None
                or file_handle.handler is None
                or file_handle.handler_file is None
            ):
                self.setioerr(ctx, ERROR_INVALID_LOCK)
                return DOSFALSE
            handler, handler_obj = file_handle.handler, file_handle.handler_file
        else:
            self.setioerr(ctx, ERROR_BAD_NUMBER)
            return DOSFALSE
        try:
            handler.change_mode(handler_obj, newmode.val)
        except HandlerError as e:
            self.setioerr(ctx, e.code)
            return DOSFALSE
        log_dos.info("ChangeMode(type=%d, mode=%d): ok", type.val, newmode.val)
        return self._bool_result(ctx, True, 0)

    def SetOwner(self, ctx, name: CSTR, owner_info: LONG):
        if self.handler_mgr is None:
            self.setioerr(ctx, ERROR_NOT_IMPLEMENTED)
            return DOSFALSE
        try:
            self.handler_mgr.set_owner(
                name.get_str(), owner_info.val, cwd=self.get_cwd_path(ctx)
            )
        except HandlerError as e:
            self.setioerr(ctx, e.code)
            return DOSFALSE
        return self._bool_result(ctx, True, 0)

    # ----- Stdio -----

    def ErrorOutput(self, ctx):
        return Stdio.error_output(ctx)

    def SelectError(self, ctx, fh: LONG):
        return Stdio.select_error(ctx, fh.val)

    def PutErrStr(self, ctx, string: CSTR):
        return Stdio.put_err_str(self, ctx, string.aptr)

    def ErrorReport(self, ctx, code: LONG, type: LONG, arg1: LONG, device: LONG):
        ok, err = Stdio.error_report(
            self, ctx, code.val, type.val, arg1.val, device.val
        )
        return self._bool_result(ctx, ok, err)

    # ----- Assigns (RKRM AmigaDOS 3: creating and updating assigns) -----

    def AssignLate(self, ctx, name: CSTR, path: CSTR):
        ok, err = Assign.assign_path(self, ctx, name.get_str(), path.get_str())
        return self._bool_result(ctx, ok, err)

    def AssignPath(self, ctx, name: CSTR, path: CSTR):
        ok, err = Assign.assign_path(self, ctx, name.get_str(), path.get_str())
        return self._bool_result(ctx, ok, err)

    def AssignAdd(self, ctx, name: CSTR, lock: LONG):
        ok, err = Assign.assign_add(self, name.get_str(), lock.val)
        return self._bool_result(ctx, ok, err)

    def RemAssignList(self, ctx, name: CSTR, lock: LONG):
        ok, err = Assign.rem_assign_list(self, name.get_str(), lock.val)
        return self._bool_result(ctx, ok, err)

    # ----- Volumes (RKRM AmigaDOS 3: Format/Relabel/AddBuffers) -----

    def Format(
        self,
        ctx,
        filesystem: CSTR,
        volumename: CSTR,
        dostype: LONG,
    ):
        ok, err = Volume.format_volume(
            self,
            ctx,
            filesystem.get_str(),
            volumename.get_str(),
            dostype.val,
        )
        return self._bool_result(ctx, ok, err)

    def Relabel(self, ctx, drive: CSTR, newname: CSTR):
        ok, err = Volume.relabel(self, ctx, drive.get_str(), newname.get_str())
        return self._bool_result(ctx, ok, err)

    def AddBuffers(self, ctx, name: CSTR, number: LONG):
        ok, err = Volume.add_buffers(self, ctx, name.get_str(), number.val)
        return self._bool_result(ctx, ok, err)

    # ----- Dates -----

    def CompareDates(self, ctx, date1: LONG, date2: LONG):
        result = Date.compare_dates(date1.val, date2.val, ctx.mem)
        log_dos.info("CompareDates(%06x, %06x) -> %d", date1.val, date2.val, result)
        return result

    def StrToDate(self, ctx, datetime: LONG):
        dt = DateTimeStruct(ctx.mem, datetime.val)
        return Date.str_to_date(ctx, dt)

    # ----- Segments (RKRM AmigaDOS 3: LoadSeg and resident segments) -----

    def InternalUnLoadSeg(self, ctx, seglist: LONG, freefunc: LONG):
        Segments.internal_unload_seg(self, ctx, seglist.val, freefunc.val)

    def NewLoadSeg(self, ctx, file: CSTR, tags: TagList):
        return Segments.new_load_seg(self, ctx, file.get_str(), tags)

    def RemSegment(self, ctx, seg: LONG):
        ok, err = Segments.rem_segment(self, ctx, seg.val)
        return self._bool_result(ctx, ok, err)

    # ----- Notify -----

    def StartNotify(self, ctx, notify: LONG):
        ok, err = Notify.start_notify(self, ctx, notify.val)
        return self._bool_result(ctx, ok, err)

    def EndNotify(self, ctx, notify: LONG):
        ok, err = Notify.end_notify(self, ctx, notify.val)
        return self._bool_result(ctx, ok, err)

    # ----- Misc -----

    def SameDevice(self, ctx, lock1: LONG, lock2: LONG):
        try:
            l1 = self.lock_mgr.get_by_b_addr(lock1.val) if lock1.val else None
            l2 = self.lock_mgr.get_by_b_addr(lock2.val) if lock2.val else None
        except Exception:
            self.setioerr(ctx, ERROR_INVALID_LOCK)
            return DOSFALSE
        name1 = self.lock_mgr.volume_name_of_lock(l1)
        name2 = self.lock_mgr.volume_name_of_lock(l2)
        same = name1.lower() == name2.lower()
        log_dos.info("SameDevice(%s, %s) -> %s", name1, name2, same)
        return DOSTRUE if same else DOSFALSE

    def VolumeRequestHook(self, ctx, vol: LONG):
        log_dos.warning("VolumeRequestHook(%s): not implemented", vol.val)
        return 0

    def DoShellMethodTagList(self, ctx, method: LONG, tags: TagList):
        log_dos.warning(
            "DoShellMethodTagList(method=%d, tags=%s): not implemented",
            method.val,
            tags,
        )
        return 0

    def ScanStackToken(self, ctx, seg: LONG, defaultstack: LONG):
        log_dos.info(
            "ScanStackToken(%s, %d): returning the default",
            seg.val,
            defaultstack.val,
        )
        return defaultstack.val

    def create_child_process(self, ctx, name, **kw_args):
        """the process CreateNewProc() makes: a DosProcess by default.

        an embedder may return a subclass that serves the DOS calls of a
        process vamos did not load as a program.
        """
        return DosProcess(ctx.machine, ctx.alloc, name, **kw_args)

    def _child_proc_event(self, event):
        """free a process made by CreateNewProc() once its task has ended"""
        if event.type != SchedulerEvent.Type.REMOVE_TASK:
            return
        child = self.child_procs.pop(event.task, None)
        if child is None:
            return
        port_addr = child.proc.msg_port.addr
        if self.port_mgr.has_port(port_addr):
            self.port_mgr.unregister_port(port_addr)
        log_dos.info("CreateNewProc: process %06x ended", child.proc.addr)
        child.free()

    def _unlink_msg(self, ctx, msg_addr):
        try:
            ln_succ = ctx.mem.r32(msg_addr + 0)
            ln_pred = ctx.mem.r32(msg_addr + 4)
            if ln_succ != 0 and ln_pred != 0:
                ctx.mem.w32(ln_pred + 0, ln_succ)
                ctx.mem.w32(ln_succ + 4, ln_pred)
        except Exception:
            pass

    def _alloc_mem(self, name, size):
        mem = self.alloc.alloc_memory(size, label=name)
        self.mem_allocs[mem.addr] = mem
        return mem.addr

    def _free_mem(self, addr):
        if addr in self.mem_allocs:
            mem = self.mem_allocs[addr]
            self.alloc.free_memory(mem)
            del self.mem_allocs[addr]
        else:
            raise VamosInternalError("Invalid DOS free mem: %06x" % addr)
