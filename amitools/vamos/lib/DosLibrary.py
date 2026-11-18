import time
from contextlib import ExitStack

from amitools.vamos.machine.regs import *
from amitools.vamos.libcore import LibImpl
from amitools.vamos.astructs import CSTR, LONG, UBYTE, APTR_VOID
from amitools.vamos.libstructs import (
    DosLibraryStruct,
    DosInfoStruct,
    RootNodeStruct,
    DateTimeStruct,
    ProcessStruct,
    MessageStruct,
    MsgPortStruct,
    ListStruct,
    TimeRequestStruct,
)
from amitools.vamos.libtypes import TagList, DosPacket
from amitools.vamos.error import *
from amitools.vamos.log import log_dos
from amitools.vamos.handler import HandlerError
from amitools.vamos.task import DosProcess
from amitools.vamos.schedule import SchedulerEvent
from .dos.Args import *
from .dos.Error import *
from .dos import PathPart
from .dos.DosList import DosList
from .dos.LockManager import LockManager
from .dos.FileManager import FileManager
from .dos.DosFileOpener import DosFileOpener
from .dos import (
    Args,
    Assign,
    Cli,
    Date,
    DeviceProc as DeviceProcMod,
    DosList as DosListMod,
    DosPacket as DosPacketMod,
    FileIO,
    Link,
    Lock,
    MatchFirstNext,
    Notify,
    PatternMatch,
    RecordLock,
    Segments,
    Stdio,
    Var,
    Volume,
)
from .dos.CSource import *
from .dos.Item import *


class DosLibrary(LibImpl):
    LV_VAR = 0  # an variable
    LV_ALIAS = 1  # an alias
    LVF_IGNORE = 0x80

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
        Lock.drop_all_exall_scans(self)
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
            Var.delete_var_node(self, ctx, var)
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
        return Stdio.io_err(self, ctx)

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

    def SetIoErr(self, ctx, err):
        return Stdio.set_io_err(self, ctx, err)

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

    def Fault(self, ctx, errcode, hdr_ptr, buf_ptr, buf_len):
        return Stdio.fault(self, ctx, errcode, hdr_ptr, buf_ptr, buf_len)

    def PrintFault(self, ctx, errcode, hdr_ptr):
        return Stdio.print_fault(self, ctx, errcode, hdr_ptr)

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

    def DateStamp(self, ctx, ds_ptr):
        return Date.date_stamp(self, ctx, ds_ptr)

    def DateToStr(self, ctx, dt_ptr):
        return Date.date_to_str(self, ctx, dt_ptr)

    def SetFileDate(self, ctx, name: CSTR, date):
        return FileIO.set_file_date(self, ctx, name.get_str(), date)

    def SetComment(self, ctx, name: CSTR, comment: CSTR):
        return FileIO.set_comment(self, ctx, name.get_str(), comment.get_str())

    def GetProgramName(self, ctx, buf_ptr, max_len):
        return Cli.get_program_name(self, ctx, buf_ptr, max_len)

    def GetProgramDir(self, ctx):
        return Cli.get_program_dir(self, ctx)

    def GetArgStr(self, ctx):
        return Cli.get_arg_str(self, ctx)

    # ----- Variables -----

    def GetVar(self, ctx, name_ptr, buff_ptr, size, flags):
        return Var.get_var(self, ctx, name_ptr, buff_ptr, size, flags)

    def FindVar(self, ctx, name_ptr, vtype):
        return Var.find_var(self, ctx, name_ptr, vtype)

    def SetVar(self, ctx, name_ptr, buff_ptr, size, flags):
        return Var.set_var(self, ctx, name_ptr, buff_ptr, size, flags)

    def DeleteVar(self, ctx, name_ptr, flags):
        return Var.delete_var(self, ctx, name_ptr, flags)

    # ----- Signals ----------------------

    def CheckSignal(self, ctx, sigmask):
        return Segments.check_signal(self, ctx, sigmask)

    # ----- Resident commands support ----

    def FindSegment(self, ctx, name_ptr, start, system):
        return Segments.find_segment(self, ctx, name_ptr, start, system)

    def AddSegment(self, ctx, name_ptr, seglist, system):
        return Segments.add_segment(self, ctx, name_ptr, seglist, system)

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

    def IsFileSystem(self, ctx, name_ptr):
        return DosListMod.is_file_system(self, ctx, name_ptr)

    # ----- Locks -----

    def Lock(self, ctx, name: CSTR, mode):
        return Lock.lock(self, ctx, name.get_str(), mode)

    def UnLock(self, ctx, lock_b_addr):
        return Lock.unlock(self, ctx, lock_b_addr)

    def DupLock(self, ctx, lock_b_addr):
        return Lock.dup_lock(self, ctx, lock_b_addr)

    def SameLock(self, ctx, lock1_b_addr, lock2_b_addr):
        return Lock.same_lock(self, ctx, lock1_b_addr, lock2_b_addr)

    def OpenFromLock(self, ctx, lock_b_addr):
        return Lock.open_from_lock(self, ctx, lock_b_addr)

    def DupLockFromFH(self, ctx, fh_b_addr):
        return Lock.dup_lock_from_fh(self, ctx, fh_b_addr)

    def ParentOfFH(self, ctx, fh_b_addr):
        return Lock.parent_of_fh(self, ctx, fh_b_addr)

    def Examine(self, ctx, lock_b_addr, fib_ptr):
        return Lock.examine(self, ctx, lock_b_addr, fib_ptr)

    def ExamineFH(self, ctx, fh_b_addr, fib_ptr):
        return Lock.examine_fh(self, ctx, fh_b_addr, fib_ptr)

    def Info(self, ctx, lock_b_addr, info_ptr):
        return Lock.info(self, ctx, lock_b_addr, info_ptr)

    def ExNext(self, ctx, lock_b_addr, fib_ptr):
        return Lock.exnext(self, ctx, lock_b_addr, fib_ptr)

    def ExAll(self, ctx, lock_b_addr, buffer, size, data_type, control_ptr):
        return Lock.exall(self, ctx, lock_b_addr, buffer, size, data_type, control_ptr)

    def ExAllEnd(self, ctx, lock_b_addr, buffer, size, data_type, control_ptr):
        return Lock.exall_end(
            self, ctx, lock_b_addr, buffer, size, data_type, control_ptr
        )

    def ParentDir(self, ctx, lock_b_addr):
        return Lock.parent_dir(self, ctx, lock_b_addr)

    def CurrentDir(self, ctx, lock_b_addr):
        return Lock.current_dir(self, ctx, lock_b_addr)

    def NameFromLock(self, ctx, lock_b_addr, buf, buf_len):
        return Lock.name_from_lock(self, ctx, lock_b_addr, buf, buf_len)

    def NameFromFH(self, ctx, fh_b_addr, buf, buf_len):
        return Lock.name_from_fh(self, ctx, fh_b_addr, buf, buf_len)

    def CreateDir(self, ctx, name: CSTR):
        return FileIO.create_dir(self, ctx, name.get_str())

    # ----- DevProc -----

    # dvp_Flags (see dos/dosextens.h)
    DVPF_UNLOCK = 1
    DVPF_ASSIGN = 2

    def GetDeviceProc(self, ctx, name_ptr, last_devproc):
        return DeviceProcMod.get_device_proc(self, ctx, name_ptr, last_devproc)

    def FreeDeviceProc(self, ctx, addr):
        return DeviceProcMod.free_device_proc(self, ctx, addr)

    # ----- Matcher -----

    def MatchFirst(self, ctx, pat_ptr, anchor_ptr):
        return MatchFirstNext.match_first(self, ctx, pat_ptr, anchor_ptr)

    def MatchNext(self, ctx, anchor_ptr):
        return MatchFirstNext.match_next(self, ctx, anchor_ptr)

    def MatchEnd(self, ctx, anchor_ptr):
        return MatchFirstNext.match_end(self, ctx, anchor_ptr)

    # ----- Pattern Parsing and Matching -----

    def ParsePattern(self, ctx, src_ptr, dst_ptr, dst_len):
        return PatternMatch.parse_pattern(self, ctx, src_ptr, dst_ptr, dst_len)

    def ParsePatternNoCase(self, ctx, src_ptr, dst_ptr, dst_len):
        return PatternMatch.parse_pattern(self, ctx, src_ptr, dst_ptr, dst_len, True)

    def MatchPattern(self, ctx, pat_ptr, txt_ptr):
        return PatternMatch.match_pattern(self, ctx, pat_ptr, txt_ptr)

    def MatchPatternNoCase(self, ctx, pat_ptr, txt_ptr):
        return PatternMatch.match_pattern(self, ctx, pat_ptr, txt_ptr, ignore_case=True)

    # ----- Args -----

    def FindArg(self, ctx, template_ptr, keyword_ptr):
        return Args.find_arg(self, ctx, template_ptr, keyword_ptr)

    def ReadArgs(self, ctx, template_ptr, array_ptr, rdargs_ptr):
        return Args.read_args(self, ctx, template_ptr, array_ptr, rdargs_ptr)

    def FreeArgs(self, ctx, rdargs_ptr):
        return Args.free_args(self, ctx, rdargs_ptr)

    def ReadItem(self, ctx, buff_ptr, maxchars, csrc_ptr):
        return Args.read_item(self, ctx, buff_ptr, maxchars, csrc_ptr)

    # ----- System/Execute -----

    def SystemTagList(self, ctx, cmd: CSTR, tag_list: TagList):
        cmd = cmd.get_str()
        return self._system_tag_list(ctx, cmd, tag_list)

    def _system_tag_list(self, ctx, cmd, tag_list):
        return Cli.system_tag_list(self, ctx, cmd, tag_list)

    def _load_seg_list(self, ctx, name, lock):
        return Cli.load_seg_list(self, ctx, name, lock)

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

    def LoadSeg(self, ctx, name_ptr):
        return Segments.load_seg(self, ctx, name_ptr)

    def UnLoadSeg(self, ctx, b_addr):
        return Segments.unload_seg(self, ctx, b_addr)

    def InternalLoadSeg(self, ctx, fh_baddr, table_ptr, func_ptr, stack_ptr):
        return Segments.internal_load_seg(
            self, ctx, fh_baddr, table_ptr, func_ptr, stack_ptr
        )

    def RunCommand(self, ctx, b_addr, stack, args, length):
        return Cli.run_command(self, ctx, b_addr, stack, args, length)

    # ----- Path Helper -----

    def FilePart(self, ctx, addr):
        return PathPart.file_part(self, ctx, addr)

    def PathPart(self, ctx, addr):
        return PathPart.path_part(self, ctx, addr)

    def AddPart(self, ctx, dn_addr, fn_addr, size):
        return PathPart.add_part(self, ctx, dn_addr, fn_addr, size)

    def SplitName(
        self,
        ctx,
        name: CSTR,
        separator: UBYTE,
        buf: APTR_VOID,
        oldpos: LONG,
        size: LONG,
    ):
        return PathPart.split_name(
            self, ctx, name.str, int(separator), buf.aptr, int(oldpos), int(size)
        )

    # ----- DosObjects -----

    def AllocDosObject(self, ctx, obj_type, tags_ptr):
        return DosListMod.alloc_dos_object(self, ctx, obj_type, tags_ptr)

    def FreeDosObject(self, ctx, obj_type, ptr):
        return DosListMod.free_dos_object(self, ctx, obj_type, ptr)

    # ----- Cli support ---

    def CliInit(self, ctx, dp: DosPacket):
        return Cli.cli_init(self, ctx, dp)

    def CliInitNewcli(self, ctx, dp: DosPacket):
        return Cli.cli_init_newcli(self, ctx, dp)

    def CliInitRun(self, ctx, dp: DosPacket):
        return Cli.cli_init_run(self, ctx, dp)

    # ----- DosList -------------

    def LockDosList(self, ctx, flags):
        return DosListMod.lock_dos_list(self, ctx, flags)

    def UnLockDosList(self, ctx, flags):
        return DosListMod.unlock_dos_list(self, ctx, flags)

    def NextDosEntry(self, ctx, node, flags):
        return DosListMod.next_dos_entry(self, ctx, node, flags)

    def FindDosEntry(self, ctx, dlist, name_ptr, flags):
        return DosListMod.find_dos_entry(self, ctx, dlist, name_ptr, flags)

    def AttemptLockDosList(self, ctx, flags):
        return DosListMod.attempt_lock_dos_list(self, ctx, flags)

    def Inhibit(self, ctx, name: CSTR, onoff):
        return DosListMod.inhibit(self, ctx, name.get_str(), onoff)

    def MakeDosEntry(self, ctx, name_ptr, entry_type):
        return DosListMod.make_dos_entry(self, ctx, name_ptr, entry_type)

    def AddDosEntry(self, ctx, dlist_ptr):
        return DosListMod.add_dos_entry(self, ctx, dlist_ptr)

    def RemDosEntry(self, ctx, dlist_ptr):
        return DosListMod.rem_dos_entry(self, ctx, dlist_ptr)

    def FreeDosEntry(self, ctx, dlist_ptr):
        return DosListMod.free_dos_entry(self, ctx, dlist_ptr)

    def CreateNewProc(self, ctx, tags: TagList):
        return Cli.create_new_proc(self, ctx, tags)

    def AssignLock(self, ctx, name: CSTR, lock: LONG):
        return Assign.assign_lock(self, ctx, name.get_str(), lock.val)

    # ----- misc --------

    def StrToLong(self, ctx, str_addr, val_addr):
        return Args.str_to_long(self, ctx, str_addr, val_addr)

    def SetCurrentDirName(self, ctx, str_addr):
        return Cli.set_current_dir_name(self, ctx, str_addr)

    def SetPrompt(self, ctx, str_addr):
        return Cli.set_prompt(self, ctx, str_addr)

    def DosGetString(self, ctx, errno):
        return Date.dos_get_string(self, ctx, errno)

    # As we only have one file system (though with multiple assigns)
    # it does not really matter what we do here...
    def GetFileSysTask(self, ctx):
        return Cli.get_file_sys_task(self, ctx)

    def SetFileSysTask(self, ctx, port):
        return Cli.set_file_sys_task(self, ctx, port)

    # ----- DosPackets -----

    def ReplyPkt(self, ctx, dp: DosPacket, res1, res2):
        return DosPacketMod.reply_pkt(self, ctx, dp, res1, res2)

    def SendPkt(self, ctx, dp_addr, port_addr, reply_addr):
        return DosPacketMod.send_pkt(self, ctx, dp_addr, port_addr, reply_addr)

    def DoPkt(self, ctx, port_addr, action, arg1, arg2, arg3, arg4, arg5):
        return DosPacketMod.do_pkt(
            self, ctx, port_addr, action, arg1, arg2, arg3, arg4, arg5
        )

    def AbortPkt(self, ctx, port_addr, pkt_addr):
        return DosPacketMod.abort_pkt(self, ctx, port_addr, pkt_addr)

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
        return DeviceProcMod.device_proc(self, ctx, name.get_str())

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
        return Lock.same_device(self, ctx, lock1.val, lock2.val)

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
