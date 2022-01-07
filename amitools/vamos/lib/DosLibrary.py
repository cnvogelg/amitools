import time
import ctypes
import re
import os

from amitools.vamos.machine.regs import *
from amitools.vamos.libcore import LibImpl
from amitools.vamos.astructs import AccessStruct
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
    InfoDataStruct,
    DevProcStruct,
    AnchorPathStruct,
    RDArgsStruct,
    CLIStruct,
    DosPacketStruct,
    PathStruct,
)
from amitools.vamos.error import *
from amitools.vamos.log import log_dos
from .dos.Args import *
from .dos.Error import *
from .dos.AmiTime import *
from .util.TagList import *
from .dos import Printf, PathPart
from .dos.DosTags import DosTags
from .dos.PatternMatch import Pattern, pattern_parse, pattern_match
from .dos.MatchFirstNext import MatchFirstNext
from .dos.CommandLine import CommandLine
from .dos.Process import Process
from .dos.DosList import DosList
from .dos.LockManager import LockManager
from .dos.FileManager import FileManager
from .dos.CSource import *
from .dos.Item import *
from amitools.vamos.dos import run_command, run_sub_process


class DosLibrary(LibImpl):
    DOSFALSE = 0
    DOSTRUE = 0xFFFFFFFF
    DOSTRUE_S = -1

    LV_VAR = 0  # an variable
    LV_ALIAS = 1  # an alias
    LVF_IGNORE = 0x80
    GVF_GLOBAL_ONLY = 0x100
    GVF_LOCAL_ONLY = 0x200
    GVF_BINARY_VAR = 0x400

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
        self.errstrings = {}
        self.path = []
        self.resident = []
        self.local_vars = {}
        self.access = AccessStruct(ctx.mem, self.get_struct_def(), base_addr)
        # setup RootNode
        self.root_struct = ctx.alloc.alloc_struct(RootNodeStruct, label="RootNode")
        self.access.w_s("dl_Root", self.root_struct.addr)
        # setup DosInfo
        self.dos_info = ctx.alloc.alloc_struct(DosInfoStruct, label="DosInfo")
        self.root_struct.access.w_s("rn_Info", self.dos_info.addr)
        # setup dos list
        self.dos_list = DosList(
            self.path_mgr, self.path_mgr.assign_mgr, ctx.mem, ctx.alloc
        )
        baddr = self.dos_list.build_list(ctx.path_mgr)
        # create lock manager
        self.lock_mgr = LockManager(ctx.path_mgr, self.dos_list, ctx.alloc, ctx.mem)
        # equip the DosList with all the locks
        self.dos_list.add_locks(self.lock_mgr)
        # create file manager
        self.file_mgr = FileManager(
            ctx.path_mgr, ctx.exec_lib.port_mgr, ctx.alloc, ctx.mem
        )

    def finish_lib(self, ctx):
        # finish file manager
        self.file_mgr.finish()
        # free dos list
        self.dos_list.free_list()
        # free path
        for path, lock in self.path:
            ctx.alloc.free_struct(path)
            self.lock_mgr.release_lock(lock)
        # free resident nodes
        for res in self.resident:
            self._free_mem(res)
        # free shell variables
        while len(self.local_vars) > 0:
            var = list(self.local_vars.values())[0]
            self.delete_var(ctx, var)
        # self.delete_var(ctx,var)
        # free RootNode
        ctx.alloc.free_struct(self.root_struct)
        # free DosInfo
        ctx.alloc.free_struct(self.dos_info)

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
        log_dos.info("IoErr: %d (%s)" % (self.io_err, errstring))
        return self.io_err

    def setioerr(self, ctx, err):
        self.io_err = err
        ctx.process.this_task.access.w_s("pr_Result2", err)

    def SetIoErr(self, ctx):
        old_io_err = self.io_err
        self.setioerr(ctx, ctx.cpu.r_reg(REG_D1))
        log_dos.info("SetIoErr: IoErr=%d old IoErr=%d", self.io_err, old_io_err)
        return old_io_err

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
        return self.DOSTRUE

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
        return self.DOSTRUE

    # ----- current dir

    def get_current_dir(self, ctx):
        cur_dir = ctx.process.get_current_dir()
        return self.lock_mgr.get_by_b_addr(cur_dir >> 2)

    # ----- dos API -----

    def DateStamp(self, ctx):
        ds_ptr = ctx.cpu.r_reg(REG_D1)
        ds = AccessStruct(ctx.mem, DateStampStruct, struct_addr=ds_ptr)
        t = time.time()
        at = sys_to_ami_time(t)
        log_dos.info("DateStamp: ptr=%06x sys_time=%d time=%s", ds_ptr, t, at)
        ds.w_s("ds_Days", at.tday)
        ds.w_s("ds_Minute", at.tmin)
        ds.w_s("ds_Tick", at.tick)
        return ds_ptr

    def DateToStr(self, ctx):
        dt_ptr = ctx.cpu.r_reg(REG_D1)
        dt = AccessStruct(ctx.mem, DateTimeStruct, struct_addr=dt_ptr)
        ds_day = dt.r_s("dat_Stamp.ds_Days")
        ds_min = dt.r_s("dat_Stamp.ds_Minute")
        ds_tick = dt.r_s("dat_Stamp.ds_Tick")
        format = dt.r_s("dat_Format")
        flags = dt.r_s("dat_Flags")
        str_day_ptr = dt.r_s("dat_StrDay")
        str_date_ptr = dt.r_s("dat_StrDate")
        str_time_ptr = dt.r_s("dat_StrTime")
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
        date_str = time.strftime("%d-%m-%y", t)
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
        return self.DOSTRUE

    def SetFileDate(self, ctx):
        ds_ptr = ctx.cpu.r_reg(REG_D2)
        ds = AccessStruct(ctx.mem, DateStampStruct, struct_addr=ds_ptr)
        name_ptr = ctx.cpu.r_reg(REG_D1)
        name = ctx.mem.r_cstr(name_ptr)
        ticks = ds.r_s("ds_Tick")
        minutes = ds.r_s("ds_Minute")
        days = ds.r_s("ds_Days")
        seconds = ami_to_sys_time(AmiTime(days, minutes, ticks))
        log_dos.info("SetFileDate: file=%s date=%d" % (name, seconds))
        sys_path = self.path_mgr.ami_to_sys_path(
            self.get_current_dir(ctx), name, searchMulti=True
        )
        if sys_path == None:
            log_dos.info("file not found: '%s' -> '%s'" % (name, sys_path))
            self.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
            return self.DOSFALSE
        else:
            os.utime(sys_path, (seconds, seconds))
            return self.DOSTRUE

    def SetComment(self, ctx):
        # the typical unixoid file system does not implement this
        log_dos.warning("SetComment: not implemented")
        return self.DOSTRUE

    def GetProgramName(self, ctx):
        buf_ptr = ctx.cpu.r_reg(REG_D1)
        max_len = ctx.cpu.r_reg(REG_D2)
        prog_name = ctx.process.get_program_name()
        n = len(prog_name)
        # return error if name is too long, but copy buffer size
        if n > max_len - 1:
            self.setioerr(ctx, ERROR_LINE_TOO_LONG)
            ret = self.DOSFALSE
            prog_name = prog_name[0:max_len]
        else:
            ret = self.DOSTRUE
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
        node_addr = self._alloc_mem(
            "ShellVar(%s)" % name, LocalVarStruct.get_size() + len(name) + 1
        )
        name_addr = node_addr + LocalVarStruct.get_size()
        node = ctx.alloc.map_struct(
            node_addr, LocalVarStruct, label="ShellVar(%s) % name"
        )
        ctx.mem.w_cstr(name_addr, name)
        node.access.w_s("lv_Node.ln_Name", name_addr)
        node.access.w_s("lv_Node.ln_Type", flags & 0xFF)
        node.access.w_s("lv_Value", 0)
        head_addr = varlist.access.r_s("mlh_Head")
        head = AccessStruct(ctx.mem, NodeStruct, head_addr)
        head.w_s("ln_Pred", node_addr)
        varlist.access.w_s("mlh_Head", node_addr)
        node.access.w_s("lv_Node.ln_Succ", head_addr)
        node.access.w_s("lv_Node.ln_Pred", varlist.access.s_get_addr("mlh_Head"))
        self.local_vars[(name.lower(), flags & 0xFF)] = node.access
        return node.access

    def set_var(self, ctx, node, buff_ptr, size, value, flags):
        if node.r_s("lv_Value") != 0:
            self._free_mem(node.r_s("lv_Value"))
            node.w_s("lv_Value", 0)
        buf_addr = self._alloc_mem("ShellVarBuffer", size)
        node.w_s("lv_Value", buf_addr)
        node.w_s("lv_Len", size)
        if flags & self.GVF_BINARY_VAR:
            ctx.mem.copy_block(buff_ptr, buf_addr, size)
        else:
            ctx.mem.w_cstr(buf_addr, value)

    def delete_var(self, ctx, node):
        buf_addr = node.r_s("lv_Value")
        buf_len = node.r_s("lv_Len")
        name_addr = node.r_s("lv_Node.ln_Name")
        name = ctx.mem.r_cstr(name_addr)
        if buf_addr != 0:
            self._free_mem(buf_addr)
        node.w_s("lv_Value", 0)
        succ = node.r_s("lv_Node.ln_Succ")
        pred = node.r_s("lv_Node.ln_Pred")
        AccessStruct(ctx.mem, NodeStruct, pred).w_s("ln_Succ", succ)
        AccessStruct(ctx.mem, NodeStruct, succ).w_s("ln_Pred", pred)
        self._free_mem(node.struct._addr)
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
            return self.DOSFALSE
        name = ctx.mem.r_cstr(name_ptr)
        if not flags & self.GVF_GLOBAL_ONLY:
            node = self.find_var(ctx, name, flags & 0xFF)
            if node != None:
                nodelen = node.r_s("lv_Len")
                if flags & self.GVF_BINARY_VAR:
                    ctx.mem.copy_block(
                        node.r_s("lv_Value"), buff_ptr, min(nodelen, size)
                    )
                    log_dos.info(
                        'GetVar("%s", 0x%x) -> %0x06x'
                        % (name, flags, node.r_s("lv_Value"))
                    )
                    self.setioerr(ctx, nodelen)
                    return min(nodelen, size)
                else:
                    value = ctx.mem.r_cstr(node.r_s("lv_Value"))
                    ctx.mem.w_cstr(buff_ptr, value[: size - 1])
                    log_dos.info('GetVar("%s", 0x%x) -> %s' % (name, flags, value))
                    self.setioerr(ctx, len(value))
                    return min(nodelen - 1, size - 1)
        return self.DOSFALSE

    def FindVar(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        vtype = ctx.cpu.r_reg(REG_D2)
        name = ctx.mem.r_cstr(name_ptr)
        node = self.find_var(ctx, name, vtype)
        if node == None:
            self.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
            log_dos.info('FindVar("%s", 0x%x) -> NULL' % (name, vtype))
            return 0
        else:
            log_dos.info(
                'FindVar("%s", 0x%x) -> %06lx' % (name, vtype, node.struct_addr)
            )
            return node.struct_addr

    def SetVar(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        buff_ptr = ctx.cpu.r_reg(REG_D2)
        size = ctx.cpu.r_reg(REG_D3)
        flags = ctx.cpu.r_reg(REG_D4)
        name = ctx.mem.r_cstr(name_ptr)
        vtype = flags & 0xFF
        if buff_ptr == 0:
            if not flags & self.GVF_GLOBAL_ONLY:
                node = self.find_var(ctx, name, vtype)
                if node != None:
                    self.delete_var(ctx, node)
                return self.DOSTRUE
        else:
            if flags & self.GVF_BINARY_VAR:
                value = None
                log_dos.info('SetVar("%s") to %0x6x' % (name, buff_ptr))
            else:
                value = ctx.mem.r_cstr(buff_ptr)
                log_dos.info('SetVar("%s") to %s' % (name, value))
                size = len(value) + 1
            if not flags & self.GVF_GLOBAL_ONLY:
                node = self.find_var(ctx, name, flags)
                if node == None and buff_ptr != 0:
                    node = self.create_var(ctx, name, flags)
                if node != None:
                    self.set_var(ctx, node, buff_ptr, size, value, flags)
                return self.DOSTRUE
        return 0

    def DeleteVar(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        flags = ctx.cpu.r_reg(REG_D4)
        name = ctx.mem.r_cstr(name_ptr)
        if not flags & self.GVF_GLOBAL_ONLY:
            node = self.find_var(ctx, name, flags)
            log_dos.info('DeleteVar("%s")' % name)
            if node != None:
                self.delete_var(ctx, node)
            return self.DOSTRUE

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
            seg_addr = self.dos_info.access.r_s("di_NetHand")
        else:
            seg_addr = AccessStruct(ctx.mem, SegmentStruct, start).r_s("seg_Next")
        log_dos.info("FindSegment(%s)" % needle)
        while seg_addr != 0:
            segment = AccessStruct(ctx.mem, SegmentStruct, seg_addr)
            name_addr = seg_addr + SegmentStruct.sdef.seg_Name.offset
            name = ctx.mem.r_bstr(name_addr)
            if name.lower() == needle.lower():
                if (system and segment.r_s("seg_UC") < 0) or (
                    not system and segment.r_s("seg_UC") > 0
                ):
                    seg = segment.r_s("seg_Seg")
                    log_dos.info("FindSegment(%s) -> %s" % (name, seg))
                    return seg_addr
            seg_addr = segment.r_s("seg_Next")
        return 0

    def AddSegment(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        seglist = ctx.cpu.r_reg(REG_D2) << 2
        system = ctx.cpu.r_reg(REG_D3)
        name = ctx.mem.r_cstr(name_ptr)
        seg_addr = self._alloc_mem("Segment", SegmentStruct.get_size() + len(name) + 1)
        name_addr = seg_addr + SegmentStruct.sdef.seg_Name.offset
        segment = ctx.alloc.map_struct(seg_addr, SegmentStruct, label="Segment")
        head_addr = self.dos_info.access.r_s("di_NetHand")
        segment.access.w_s("seg_Next", head_addr)
        segment.access.w_s("seg_UC", system)
        segment.access.w_s("seg_Seg", seglist)
        ctx.mem.w_bstr(name_addr, name)
        self.dos_info.access.w_s("di_NetHand", seg_addr)
        log_dos.info("AddSegment(%s,%06x) -> %06x" % (name, seglist, seg_addr))
        self.resident.append(seg_addr)
        # Adding a resident command to the registered seglists.
        b_addr = seglist >> 2
        if b_addr not in self.seg_lists:
            self.seg_lists[b_addr] = name
        return -1

    # ----- File Ops -----

    def Cli(self, ctx):
        cli_addr = ctx.process.get_cli_struct()
        log_dos.info("Cli() -> %06x" % cli_addr)
        return cli_addr

    def Input(self, ctx):
        inp_bptr = ctx.process.this_task.access.r_s("pr_CIS") >> 2
        log_dos.info("Input() -> b%06x" % inp_bptr)
        return inp_bptr

    def Output(self, ctx):
        out_bptr = ctx.process.this_task.access.r_s("pr_COS") >> 2
        log_dos.info("Output() -> b%06x" % out_bptr)
        return out_bptr

    def SelectInput(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        fh = self.file_mgr.get_by_b_addr(fh_b_addr)
        log_dos.info("SelectInput(fh=%s)" % fh)
        cur_in = self.Input(ctx)
        ctx.process.set_input(fh)
        return cur_in

    def SelectOutput(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        fh = self.file_mgr.get_by_b_addr(fh_b_addr)
        log_dos.info("SelectOutput(fh=%s)" % fh)
        cur_out = self.Output(ctx)
        ctx.process.set_output(fh)
        return cur_out

    def Open(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        name = ctx.mem.r_cstr(name_ptr)
        mode = ctx.cpu.r_reg(REG_D2)

        # decode mode
        if mode == 1006:
            mode_name = "new"
            f_mode = "wb+"
        elif mode == 1005:
            mode_name = "old"
            f_mode = "rb+"
        elif mode == 1004:
            mode_name = "r/w"
            f_mode = "rwb+"
        else:
            mode_name = "?"
            log_dos.warning("open: invalid mode=%d!", mode)
            f_mode = "wb+"

        fh = self.file_mgr.open(self.get_current_dir(ctx), name, f_mode)
        log_dos.info(
            "Open: name='%s' (%s/%d/%s) -> %s" % (name, mode_name, mode, f_mode, fh)
        )

        if fh == None:
            self.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
            return 0
        else:
            return fh.b_addr

    def Close(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        if fh_b_addr != 0:
            fh = self.file_mgr.get_by_b_addr(fh_b_addr)
            self.file_mgr.close(fh)
            log_dos.info("Close: %s" % fh)
            self.setioerr(ctx, 0)
        return self.DOSTRUE

    def Read(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        buf_ptr = ctx.cpu.r_reg(REG_D2)
        size = ctx.cpu.r_reg(REG_D3)

        fh = self.file_mgr.get_by_b_addr(fh_b_addr, False)
        data = fh.read(size)
        ctx.mem.w_block(buf_ptr, data)
        got = len(data)
        log_dos.info("Read(%s, %06x, %d) -> %d" % (fh, buf_ptr, size, got))
        return got

    def Write(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        buf_ptr = ctx.cpu.r_reg(REG_D2)
        size = ctx.cpu.r_reg(REG_D3)

        fh = self.file_mgr.get_by_b_addr(fh_b_addr, True)
        data = ctx.mem.r_block(buf_ptr, size)
        fh.write(data)
        got = len(data)
        log_dos.info("Write(%s, %06x, %d) -> %d" % (fh, buf_ptr, size, got))
        return size

    def FWrite(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        buf_ptr = ctx.cpu.r_reg(REG_D2)
        size = ctx.cpu.r_reg(REG_D3)
        number = ctx.cpu.r_reg(REG_D4)
        # Actually, this is buffered I/O, not unbuffered IO. For the
        # time being, keep it unbuffered.
        fh = self.file_mgr.get_by_b_addr(fh_b_addr, True)
        data = ctx.mem.r_block(buf_ptr, size * number)
        fh.write(data)
        got = len(data) // size
        log_dos.info(
            "FWrite(%s, %06x, %d, %d) -> %d" % (fh, buf_ptr, size, number, got)
        )
        return got

    def FRead(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        buf_ptr = ctx.cpu.r_reg(REG_D2)
        size = ctx.cpu.r_reg(REG_D3)
        number = ctx.cpu.r_reg(REG_D4)
        # Again, this is actually buffered I/O and I should really
        # go through all the buffer logic. However, for the time
        # being, keep it unbuffered.
        fh = self.file_mgr.get_by_b_addr(fh_b_addr, True)
        data = fh.read(size * number)
        if data == -1:
            got = 0  # simple error handling
        else:
            got = len(data) // size
            ctx.mem.w_block(buf_ptr, data)
        log_dos.info("FRead(%s, %06x, %d, %d) -> %d" % (fh, buf_ptr, size, number, got))
        return got

    def Seek(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        pos = ctx.cpu.r_reg(REG_D2)
        mode = ctx.cpu.r_reg(REG_D3)

        fh = self.file_mgr.get_by_b_addr(fh_b_addr)
        if mode == 0xFFFFFFFF:
            mode_str = "BEGINNING"
            whence = 0
        elif mode == 0:
            mode_str = "CURRENT"
            whence = 1
            if pos >= 0x80000000:
                pos = pos - 0x100000000
        elif mode == 1:
            mode_str = "END"
            if pos > 0:
                pos = pos - 0x100000000
            whence = 2
        else:
            raise UnsupportedFeatureError("Seek: mode=%d" % mode)

        old_pos = fh.tell()
        new_pos = fh.seek(pos, whence)
        log_dos.info(
            "Seek(%s, %06x, %s) -> old_pos=%06x" % (fh, pos, mode_str, old_pos)
        )
        if new_pos == -1:
            self.setioerr(ctx, ERROR_SEEK_ERROR)
        else:
            self.setioerr(ctx, 0)
        return old_pos

    def FGetC(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        fh = self.file_mgr.get_by_b_addr(fh_b_addr, False)
        ch = fh.getc()
        if ch == -1:
            log_dos.info("FGetC(%s) -> EOF (%d)" % (fh, ch))
        else:
            log_dos.info("FGetC(%s) -> '%c' (%d)" % (fh, ch, ch))
        return ch

    def FPutC(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        val = ctx.cpu.r_reg(REG_D2)
        fh = self.file_mgr.get_by_b_addr(fh_b_addr, True)
        log_dos.info("FPutC(%s, '%c' (%d))" % (fh, val, val))
        fh.write(bytes((val,)))
        return val

    def FPuts(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        str_ptr = ctx.cpu.r_reg(REG_D2)
        str_dat = ctx.mem.r_cbytes(str_ptr)
        # write to stdout
        fh = self.file_mgr.get_by_b_addr(fh_b_addr, True)
        ok = fh.write(str_dat)
        log_dos.info("FPuts(%s,'%s')" % (fh, str_dat))
        return 0  # ok

    def UnGetC(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        val = ctx.cpu.r_reg(REG_D2)
        fh = self.file_mgr.get_by_b_addr(fh_b_addr, False)
        ch = fh.ungetc(val)
        log_dos.info("UnGetC(%s, %d) -> ch=%d (%d)" % (fh, val, ch, ch))
        return ch

    # ----- StdOut -----

    def PutStr(self, ctx):
        str_ptr = ctx.cpu.r_reg(REG_D1)
        str_dat = ctx.mem.r_cbytes(str_ptr)
        # write to stdout
        fh = ctx.process.get_output()
        ok = fh.write(str_dat)
        log_dos.info("PutStr: '%s'", str_dat)
        return 0  # ok

    def Flush(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        fh = self.file_mgr.get_by_b_addr(fh_b_addr, True)
        fh.flush()
        return -1

    def VPrintf(self, ctx):
        format_ptr = ctx.cpu.r_reg(REG_D1)
        argv_ptr = ctx.cpu.r_reg(REG_D2)
        fmt = ctx.mem.r_cstr(format_ptr)
        # write on output
        fh = ctx.process.get_output()
        log_dos.info("VPrintf: format='%s' argv=%06x" % (fmt, argv_ptr))
        # now decode printf
        ps = Printf.printf_parse_string(fmt)
        Printf.printf_read_data(ps, ctx.mem, argv_ptr)
        log_dos.debug("VPrintf: parsed format: %s", ps)
        result = Printf.printf_generate_output(ps)
        # write result
        fh.write(result.encode("latin-1"))
        return len(result)

    def VFPrintf(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        fh = self.file_mgr.get_by_b_addr(fh_b_addr, True)
        format_ptr = ctx.cpu.r_reg(REG_D2)
        argv_ptr = ctx.cpu.r_reg(REG_D3)
        fmt = ctx.mem.r_cstr(format_ptr)
        # write on output
        log_dos.info("VFPrintf: format='%s' argv=%06x" % (fmt, argv_ptr))
        # now decode printf
        ps = Printf.printf_parse_string(fmt)
        Printf.printf_read_data(ps, ctx.mem, argv_ptr)
        log_dos.debug("VFPrintf: parsed format: %s", ps)
        result = Printf.printf_generate_output(ps)
        # write result
        fh.write(result.encode("latin-1"))
        return len(result)

    def WriteChars(self, ctx):
        fh = ctx.process.get_output()
        buf_addr = ctx.cpu.r_reg(REG_D1)
        siz = ctx.cpu.r_reg(REG_D2)
        buf = ctx.mem.r_cbytes(buf_addr)[:siz]
        fh.write(buf)
        return len(buf)

    def VFWritef(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        fh = self.file_mgr.get_by_b_addr(fh_b_addr, True)
        fmt_ptr = ctx.cpu.r_reg(REG_D2)
        args_ptr = ctx.cpu.r_reg(REG_D3)
        fmt = ctx.mem.r_cstr(fmt_ptr)
        log_dos.info("VFWritef: fh=%s format='%s' args_ptr=%06x" % (fh, fmt, args_ptr))
        out = ""
        pos = 0
        state = ""
        val = 0
        while pos < len(fmt):
            ch = fmt[pos].upper()
            pos = pos + 1
            if state[0:1] == "x":
                n = ord(ch)
                if n >= ord("0") and n <= ord("9"):
                    n = n - ord("0")
                elif n >= ord("A") and n <= ord("Z"):
                    n = (n - ord("A")) + 10
                else:
                    n = 0
                ch = state[1:2]
                if ch == "T":
                    out = out + ("%*s" % (-n, ctx.mem.r_cstr(val)))
                elif ch == "O":
                    out = out + ("%*O" % (-n, val))
                elif ch == "X":
                    out = out + ("%*X" % (-n, val))
                elif ch == "I":
                    out = out + ("%*ld" % (-n, ctypes.c_long(val).value))
                elif ch == "U":
                    out = out + ("%*lu" % (-n, ctypes.c_ulong(val).value))
                else:
                    out = out + "%" + state[1] + state[0]
                state = ""
            elif state == "%":
                if ch == "S":
                    out = out + ctx.mem.r_cstr(val)
                    state = ""
                elif ch == "C":
                    out = out + chr(val & 0xFF)
                    state = ""
                elif ch == "N":
                    out = out + ("%ld" % ctypes.c_long(val).value)
                    state = ""
                elif ch == "$":
                    state = ""
                elif ch == "T" or ch == "O" or ch == "X" or ch == "I" or ch == "U":
                    state = "x" + ch
                else:
                    out = out + "%" + ch
                    state = ""
            else:
                if ch == "%":
                    state = "%"
                    val = ctx.mem.r32(args_ptr)
                    args_ptr = args_ptr + 4
                else:
                    out = out + ch
        data = out.encode("latin-1")
        fh.write(data)
        return len(data)

    # ----- Stdin --------

    def FGets(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        bufaddr = ctx.cpu.r_reg(REG_D2)
        buflen = ctx.cpu.r_reg(REG_D3)

        # Hack for 'endcli': check FH if fh_End was set to 0 (faked EOF)
        fh_acc = AccessStruct(ctx.mem, FileHandleStruct, fh_b_addr << 2)
        fh_end = fh_acc.r_s("fh_End")
        if fh_end == 0:
            return 0

        fh = self.file_mgr.get_by_b_addr(fh_b_addr, False)
        line = fh.gets(buflen)
        # Bummer! FIXME: There is currently no way this can communicate an I/O error
        self.setioerr(ctx, 0)
        log_dos.info("FGetS(%s,%d) -> '%s'" % (fh, buflen, line))
        ctx.mem.w_cstr(bufaddr, line)
        if line == "":
            return 0
        return bufaddr

    # ----- File Ops -----

    def DeleteFile(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        name = ctx.mem.r_cstr(name_ptr)
        self.setioerr(ctx, self.file_mgr.delete(self.get_current_dir(ctx), name))
        log_dos.info("DeleteFile: '%s': err=%s" % (name, self.io_err))
        if self.io_err == NO_ERROR:
            return self.DOSTRUE
        else:
            return self.DOSFALSE

    def Rename(self, ctx):
        old_name_ptr = ctx.cpu.r_reg(REG_D1)
        old_name = ctx.mem.r_cstr(old_name_ptr)
        new_name_ptr = ctx.cpu.r_reg(REG_D2)
        new_name = ctx.mem.r_cstr(new_name_ptr)
        lock = self.get_current_dir(ctx)
        self.setioerr(ctx, self.file_mgr.rename(lock, old_name, new_name))
        log_dos.info("Rename: '%s' -> '%s': err=%s" % (old_name, new_name, self.io_err))
        if self.io_err == NO_ERROR:
            return self.DOSTRUE
        else:
            return self.DOSFALSE

    def SetProtection(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        name = ctx.mem.r_cstr(name_ptr)
        mask = ctx.cpu.r_reg(REG_D2)
        lock = self.get_current_dir(ctx)
        self.setioerr(ctx, self.file_mgr.set_protection(lock, name, mask))
        log_dos.info("SetProtection: '%s' mask=%04x: err=%s", name, mask, self.io_err)
        if self.io_err == NO_ERROR:
            return self.DOSTRUE
        else:
            return self.DOSFALSE

    def IsInteractive(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        log_dos.info("IsInteractive: @%06x" % fh_b_addr)
        if fh_b_addr == 0:
            return self.DOSFALSE
        fh = self.file_mgr.get_by_b_addr(fh_b_addr, False)
        res = fh.is_interactive()
        log_dos.info("IsInteractive(%s): %s" % (fh, res))
        if res:
            return self.DOSTRUE
        else:
            return self.DOSFALSE

    def IsFileSystem(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        name = ctx.mem.r_cstr(name_ptr)
        log_dos.info("IsFileSystem('%s'):" % name)
        lock = self.get_current_dir(ctx)
        res = self.file_mgr.is_file_system(lock, name)
        log_dos.info("IsFileSystem('%s'): %s" % (name, res))
        if res:
            return self.DOSTRUE
        else:
            return self.DOSFALSE

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

        lock = self.lock_mgr.create_lock(
            self.get_current_dir(ctx), name, lock_exclusive
        )
        log_dos.info(
            "Lock: (%s) '%s' exc=%s -> %s"
            % (self.get_current_dir(ctx), name, lock_exclusive, lock)
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
            log_dos.info("UnLock: %s" % (lock))
            self.lock_mgr.release_lock(lock)

    def DupLock(self, ctx):
        lock_b_addr = ctx.cpu.r_reg(REG_D1)
        lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
        dup_lock = self.lock_mgr.dup_lock(lock)
        log_dos.info("DupLock: %s -> %s", lock, dup_lock)
        self.setioerr(ctx, NO_ERROR)
        return dup_lock.b_addr

    def SameLock(self, ctx):
        lock1_b_addr = ctx.cpu.r_reg(REG_D1)
        lock2_b_addr = ctx.cpu.r_reg(REG_D1)
        lock1 = self.lock_mgr.get_by_b_addr(lock1_b_addr)
        lock2 = self.lock_mgr.get_by_b_addr(lock2_b_addr)
        if lock1 == lock2:
            return self.DOSTRUE
        if lock1 != None and lock2 != None:
            return lock1.key == lock2.key
        return self.DOSFALSE

    def Examine(self, ctx):
        lock_b_addr = ctx.cpu.r_reg(REG_D1)
        fib_ptr = ctx.cpu.r_reg(REG_D2)

        lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
        fib = AccessStruct(ctx.mem, FileInfoBlockStruct, struct_addr=fib_ptr)
        err = lock.examine_lock(fib)
        name_addr = fib.s_get_addr("fib_FileName")
        name = ctx.mem.r_cstr(name_addr)
        log_dos.info("Examine: %s fib=%06x(%s) -> %s" % (lock, fib_ptr, name, err))
        self.setioerr(ctx, err)
        if err == NO_ERROR:
            return self.DOSTRUE
        else:
            return self.DOSFALSE

    def ExamineFH(self, ctx):
        fh_b_addr = ctx.cpu.r_reg(REG_D1)
        fib_ptr = ctx.cpu.r_reg(REG_D2)

        fh = self.file_mgr.get_by_b_addr(fh_b_addr, False)
        lock = self.lock_mgr.create_lock(self.get_current_dir(ctx), fh.ami_path, False)
        log_dos.info(
            "Lock: (%s) '%s' exc=%s -> %s"
            % (self.get_current_dir(ctx), fh.ami_path, False, lock)
        )
        if lock == None:
            self.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
            return self.DOSFALSE

        fib = AccessStruct(ctx.mem, FileInfoBlockStruct, struct_addr=fib_ptr)
        err = lock.examine_lock(fib)
        name_addr = fib.s_get_addr("fib_FileName")
        name = ctx.mem.r_cstr(name_addr)
        log_dos.info("ExamineFH: %s fib=%06x(%s) -> %s" % (fh, fib_ptr, name, err))
        self.setioerr(ctx, err)

        log_dos.info("UnLock: %s" % (lock))
        self.lock_mgr.release_lock(lock)
        if err == NO_ERROR:
            return self.DOSTRUE
        else:
            return self.DOSFALSE

    def Info(self, ctx):
        lock_b_addr = ctx.cpu.r_reg(REG_D1)
        info_ptr = ctx.cpu.r_reg(REG_D2)
        lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
        info = AccessStruct(ctx.mem, InfoDataStruct, struct_addr=info_ptr)
        vol = lock.find_volume_node(self.dos_list)
        if vol != None:
            info.w_s("id_NumSoftErrors", 0)
            info.w_s("id_UnitNumber", 0)  # not that we really care...
            info.w_s("id_DiskState", 0)  # disk is not write protected
            info.w_s("id_NumBlocks", 0x7FFFFFFF)  # a really really big disk....
            info.w_s("id_NumBlocksUsed", 0x0FFFFFFF)  # some...
            info.w_s("id_BytesPerBlock", 512)  # let's take regular FFS blocks
            info.w_s("id_DiskType", 0x444F5303)  # international FFS
            info.w_s("id_VolumeNode", vol)
            info.w_s("id_InUse", 0)
            log_dos.info("Info: %s info=%06x -> true" % (lock, info_ptr))
            return self.DOSTRUE
        else:
            log_dos.info("Info: %s info=%06x -> false" % (lock, info_ptr))
            return self.DOSFALSE

    def ExNext(self, ctx):
        lock_b_addr = ctx.cpu.r_reg(REG_D1)
        fib_ptr = ctx.cpu.r_reg(REG_D2)
        lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
        fib = AccessStruct(ctx.mem, FileInfoBlockStruct, struct_addr=fib_ptr)
        err = lock.examine_next(fib)
        name_addr = fib.s_get_addr("fib_FileName")
        name = ctx.mem.r_cstr(name_addr)
        log_dos.info("ExNext: %s fib=%06x (%s) -> %s" % (lock, fib_ptr, name, err))
        self.setioerr(ctx, err)
        if err == NO_ERROR:
            self.setioerr(ctx, 0)
            return self.DOSTRUE
        else:
            self.setioerr(ctx, err)
            return self.DOSFALSE

    def ParentDir(self, ctx):
        lock_b_addr = ctx.cpu.r_reg(REG_D1)
        lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
        parent_lock = self.lock_mgr.create_parent_lock(lock)
        log_dos.info("ParentDir: %s -> %s" % (lock, parent_lock))
        if parent_lock != None:
            return parent_lock.b_addr
        else:
            return 0

    def CurrentDir(self, ctx):
        lock_b_addr = ctx.cpu.r_reg(REG_D1)
        old_lock = self.get_current_dir(ctx)
        new_lock = self.lock_mgr.get_by_b_addr(lock_b_addr)
        log_dos.info("CurrentDir(b@%x): %s -> %s" % (lock_b_addr, old_lock, new_lock))
        if new_lock == None:
            ctx.process.set_current_dir(0)
        else:
            ctx.process.set_current_dir(new_lock.b_addr << 2)
        if old_lock == None:
            return 0
        else:
            return old_lock.b_addr

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
            return self.DOSFALSE
        else:
            ctx.mem.w_cstr(buf, name)
            return self.DOSTRUE

    def CreateDir(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        name = ctx.mem.r_cstr(name_ptr)
        lock = self.get_current_dir(ctx)
        err = self.file_mgr.create_dir(lock, name)
        if err != NO_ERROR:
            self.setioerr(ctx, err)
            return 0
        else:
            lock = self.lock_mgr.create_lock(lock, name, True)
            log_dos.info("CreateDir: '%s' -> %s" % (name, lock))
        if lock == None:
            self.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
            return 0
        else:
            return lock.b_addr

    # ----- DevProc -----

    def GetDeviceProc(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        last_devproc = ctx.cpu.r_reg(REG_D2)
        name = ctx.mem.r_cstr(name_ptr)
        uname = name.upper()
        #
        # First filter out "real" devices.
        if uname.startswith("NIL:") or uname == "*" or uname.startswith("CONSOLE:"):
            log_dos.info("GetDeviceProc: %s -> None" % name)
            vol_lock = 0
        else:
            # Otherwise, create a lock for the path
            abs_name = ctx.path_mgr.ami_abs_path(self.get_current_dir(ctx), name)
            volume = ctx.path_mgr.ami_volume_of_path(abs_name)
            vol_lock = self.lock_mgr.create_lock(None, volume + ":", False)
        fs_port = self.file_mgr.get_fs_handler_port()
        addr = self._alloc_mem("DevProc:%s" % name, DevProcStruct.get_size())
        log_dos.info(
            "GetDeviceProc: name='%s' devproc=%06x -> volume=%s devproc=%06x lock=%s",
            name,
            last_devproc,
            volume,
            addr,
            vol_lock,
        )
        devproc = AccessStruct(ctx.mem, DevProcStruct, struct_addr=addr)
        devproc.w_s("dvp_Port", fs_port)
        if vol_lock == None:
            devproc.w_s("dvp_Lock", 0)
        else:
            devproc.w_s(
                "dvp_Lock", vol_lock.b_addr << 2
            )  # THOR: Compensate for BADDR adjustment.
        self.setioerr(ctx, NO_ERROR)
        return addr

    def FreeDeviceProc(self, ctx):
        addr = ctx.cpu.r_reg(REG_D1)
        devproc = AccessStruct(ctx.mem, DevProcStruct, struct_addr=addr)
        vol_lock = devproc.r_s("dvp_Lock")
        if vol_lock != 0:
            lock = self.lock_mgr.get_by_b_addr(vol_lock >> 2)
            self.lock_mgr.release_lock(lock)
        self._free_mem(addr)
        log_dos.info("FreeDeviceProc: devproc=%06x", addr)

    # ----- Matcher -----

    def MatchFirst(self, ctx):
        pat_ptr = ctx.cpu.r_reg(REG_D1)
        pat = ctx.mem.r_cstr(pat_ptr)
        anchor_ptr = ctx.cpu.r_reg(REG_D2)
        anchor = AccessStruct(ctx.mem, AnchorPathStruct, struct_addr=anchor_ptr)

        # create MatchFirstNext instance
        mfn = MatchFirstNext(
            ctx.path_mgr, self.lock_mgr, self.get_current_dir(ctx), pat, anchor
        )
        log_dos.info(
            "MatchFirst: pat='%s' anchor=%06x strlen=%d flags=%02x-> ok=%s"
            % (pat, anchor_ptr, mfn.str_len, mfn.flags, mfn.ok)
        )
        if not mfn.ok:
            self.matches[anchor_ptr] = mfn
            self.setioerr(ctx, ERROR_BAD_TEMPLATE)
            return self.io_err
        log_dos.debug("MatchFirst: %s" % mfn.matcher)

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
        log_dos.info("MatchNext: anchor=%06x" % (anchor_ptr))
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
        log_dos.info("MatchEnd: anchor=%06x " % (anchor_ptr))
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
            rdargs = ctx.alloc.map_struct(rdargs_ptr, RDArgsStruct, label="RDArgs")
            csrc_buf_ptr = rdargs.access.r_s("RDA_Source.CS_Buffer")
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
            flags = rdargs.access.r_s("RDA_Flags")
            ext_help_ptr = rdargs.access.r_s("RDA_ExtHelp")
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
                rdargs = ctx.alloc.alloc_struct(RDArgsStruct, label="RDArgs")
                rdargs_ptr = rdargs.addr
                own = True
            else:
                own = False
            # own house keeping
            self.rdargs[rdargs.addr] = (rdargs, own)

            # 9. store extra buffer
            rdargs.access.w_s("RDA_Buffer", extra_ptr)
            rdargs.access.w_s("RDA_BufSiz", total_bytes)

        # done
        self.setioerr(ctx, error)
        return rdargs_ptr

    def FreeArgs(self, ctx):
        rdargs_ptr = ctx.cpu.r_reg(REG_D1)
        log_dos.info("FreeArgs: %06x" % rdargs_ptr)
        # find rdargs
        if rdargs_ptr not in self.rdargs:
            raise VamosInternalError("Can't find RDArgs: %06x" % rdargs_ptr)
        rdargs, own = self.rdargs[rdargs_ptr]
        del self.rdargs[rdargs_ptr]
        # clean up rdargs
        addr = rdargs.access.r_s("RDA_Buffer")
        if addr != 0:
            self._free_mem(addr)
        # free our memory
        if own:
            self.alloc.free_struct(rdargs)

    def ReadItem(self, ctx):
        buff_ptr = ctx.cpu.r_reg(REG_D1)
        maxchars = ctx.cpu.r_reg(REG_D2)
        csrc_ptr = ctx.cpu.r_reg(REG_D3)
        log_dos.info(
            "ReadItem: buff_ptr=%06x maxchars=%d csource_ptr=%06x"
            % (buff_ptr, maxchars, csrc_ptr)
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
        log_dos.info("ReadItem: res=%d data=%s" % (res, data))
        # Write back the updated csource ptr if we have one
        if csrc_ptr:
            csrc.update_s(ctx.alloc, csrc_ptr)
        # write string
        if data is not None:
            ctx.mem.w_cstr(buff_ptr, data)
        return res

    # ----- System/Execute -----

    def SystemTagList(self, ctx):
        cmd_ptr = ctx.cpu.r_reg(REG_D1)
        tagitem_ptr = ctx.cpu.r_reg(REG_D2)
        cmd = ctx.mem.r_cstr(cmd_ptr)
        tag_list = taglist_parse_tagitem_ptr(ctx.mem, tagitem_ptr, DosTags)
        log_dos.info("SystemTagList: cmd='%s' tags=%s", cmd, tag_list)
        # cmd is at this point a full string of commands to execute.
        # If we're running from the Amiga shell, forward this to the shell
        # anyhow.
        if ctx.process.is_native_shell():
            cli_addr = ctx.process.get_cli_struct()
            cli = AccessStruct(ctx.mem, CLIStruct, struct_addr=cli_addr)
            new_input = self.file_mgr.open(None, "NIL:", "r")
            if new_input == None:
                log_dos.warning(
                    "SystemTagList: can't create new input file handle for SystemTagList('%s')",
                    cmd,
                )
                return 0xFFFFFFFF
            # Push-back the commands into the input buffer.
            new_input.setbuf(cmd)
            new_stdin = self.file_mgr.open(None, "*", "rw")
            outtag = tag_list.find_tag("SYS_Output")
            # print "setting new input to %s" % new_input
            # and install this as current input. The shell will read from that
            # instead until it hits the EOF
            input_fhsi = cli.r_s("cli_StandardInput")
            input_fhci = cli.r_s("cli_CurrentInput")
            if outtag != None and outtag.data != 0:
                output_fhci = cli.r_s("cli_StandardOutput")
                cli.w_s("cli_StandardOutput", outtag.data << 2)
            else:
                output_fhci = None
            cli.w_s("cli_CurrentInput", new_input.mem.addr)
            cli.w_s("cli_StandardInput", new_stdin.mem.addr)
            cli.w_s("cli_Background", self.DOSTRUE_S)
            # Create the Packet for the background process.
            packet = ctx.process.run_system()
            stack_size = cli.r_s("cli_DefaultStack") << 2
            current_dir = ctx.process.get_current_dir()
            cur_lock = self.lock_mgr.get_by_b_addr(current_dir >> 2)
            dup_lock = self.lock_mgr.dup_lock(self.get_current_dir(ctx))
            cur_module = cli.r_s("cli_Module")
            cur_out = ctx.process.this_task.access.r_s("pr_COS")
            cur_setname = ctx.mem.r_bstr(cli.r_s("cli_SetName"))
            cli.w_s("cli_Module", 0)
            ctx.process.set_current_dir(dup_lock.mem.addr)
            self.cur_dir_lock = dup_lock

            # run command
            reg_d1 = packet >> 2
            code_start = ctx.process.shell_start
            log_dos.info("(Shell)SystemTagList: pc=%06x", code_start)
            ret_code = run_command(
                ctx.scheduler, ctx.process, code_start, 0, 0, stack_size, reg_d1
            )
            log_dos.info(
                "(Shell)SystemTagList returned: cmd='%s' tags=%s: ret_code=%d",
                cmd,
                tag_list,
                ret_code,
            )

            # shutdown
            cli.w_s("cli_CurrentInput", input_fhci)
            cli.w_s("cli_StandardInput", input_fhsi)
            cli.w_s("cli_Background", self.DOSFALSE)
            cli.w_s("cli_Module", cur_module)
            if output_fhci != None:
                cli.w_s("cli_StandardOutput", output_fhci)
            # Channels are closed by the dying shell
            ctx.mem.w_bstr(cli.r_s("cli_SetName"), cur_setname)
            ctx.process.this_task.access.w_s("pr_CIS", input_fhci)
            ctx.process.this_task.access.w_s("pr_COS", cur_out)
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
                return self.DOSTRUE
            return run_sub_process(ctx.scheduler, proc)

    def LoadSeg(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        name = ctx.mem.r_cstr(name_ptr)
        lock = self.get_current_dir(ctx)
        sys_path = self.path_mgr.ami_to_sys_path(lock, name, searchMulti=True)
        if sys_path and os.path.exists(sys_path):
            b_addr = ctx.seg_loader.load_sys_seglist(sys_path)
            log_dos.info("LoadSeg: '%s' -> %06x" % (name, b_addr))
            self.seg_lists[b_addr] = name
            return b_addr
        else:
            log_dos.warning("LoadSeg: '%s' -> not found!" % (name))
            return 0

    def UnLoadSeg(self, ctx):
        b_addr = ctx.cpu.r_reg(REG_D1)
        if b_addr != 0:
            if b_addr not in self.seg_lists:
                raise VamosInternalError(
                    "Trying to unload unknown LoadSeg seg_list: b_addr=%06x" % b_addr
                )
            else:
                del self.seg_lists[b_addr]
                ctx.seg_loader.unload_seglist(b_addr)
                log_dos.info("UnLoadSeg: %06x" % b_addr)
        else:
            log_dos.info("UnLoadSeg:  NULL")

    def InternalLoadSeg(self, ctx):
        fh_baddr = ctx.cpu.r_reg(REG_D0)
        table_ptr = ctx.cpu.r_reg(REG_A0)
        func_ptr = ctx.cpu.r_reg(REG_A1)
        stack_ptr = ctx.cpu.r_reg(REG_A2)
        # FIXME: For now, just fail
        log_dos.warning(
            "InternalLoadSeg: fh=%06x table=%06x funcptr=%06x stack_ptr=%06x -> not implemented!"
            % (fh_baddr, table_ptr, func_ptr, stack_ptr)
        )
        self.setioerr(ctx, ERROR_OBJECT_WRONG_TYPE)
        return 0

    def RunCommand(self, ctx):
        b_addr = ctx.cpu.r_reg(REG_D1)
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
            "RunCommand: seglist=%06x(%s) stack=%d args=%s"
            % (b_addr, name, stack, cmdline)
        )
        # round up the stack
        stack = (stack + 3) & -4
        prog_start = (b_addr << 2) + 4
        ret_code = run_command(
            ctx.scheduler, ctx.process, prog_start, args, length, stack
        )
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
            return self.DOSTRUE
        else:
            return self.DOSFALSE

    # ----- DosObjects -----

    def AllocDosObject(self, ctx):
        obj_type = ctx.cpu.r_reg(REG_D1)
        tags_ptr = ctx.cpu.r_reg(REG_D2)
        if obj_type == 0:  # DOS_FILEHANDLE
            name = "DOS_FILEHANDLE"
            struct_def = FileHandleStruct
        elif obj_type == 1:  # DOS_EXALLCONTROL
            name = "DOS_EXALLCONTROL"
            struct_def = None
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
        dos_obj = ctx.alloc.alloc_struct(struct_def, label=name)
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
            dos_obj.access.w_s("fh_Pos", 0xFFFFFFFF)
            dos_obj.access.w_s("fh_End", 0xFFFFFFFF)
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
            # free struct
            ctx.alloc.free_struct(entry[0])
        else:
            log_dos.error(
                "FreeDosObject: type=%d ptr=%08x -> NOT FOUND!", obj_type, ptr
            )

    # ----- Cli support ---

    def CliInit(self, ctx):
        log_dos.info("CliInit")
        clip_addr = self.Cli(ctx)
        clip = AccessStruct(ctx.mem, CLIStruct, clip_addr)
        clip.w_s("cli_FailLevel", 10)
        clip.w_s(
            "cli_DefaultStack", ctx.process.get_stack().get_size() >> 2
        )  # in longs
        # Typically, the creator of the CLI would also initialize
        # the prompt and command name arguments. Unfortunately,
        # vamos does not necessarily do that, so cover this here.
        prompt_ptr = clip.r_s("cli_Prompt")
        ctx.mem.w_bstr(prompt_ptr, "%N.%S> ")
        # Get the current dir and install it.
        setname = clip.r_s("cli_SetName")
        ctx.mem.w_bstr(setname, "SYS:")
        # The native CliInit opens the CON window here. Don't do that
        # instead use Input and Output.
        # cli_CurrentInput would also be set to the input handle of
        # the S:Startup-Sequence
        infh = self.Input(ctx) << 2
        outfh = self.Output(ctx) << 2
        clip.w_s("cli_StandardInput", infh)
        clip.w_s("cli_CurrentInput", infh)
        clip.w_s("cli_StandardOutput", outfh)
        clip.w_s("cli_CurrentOutput", outfh)
        fh = self.file_mgr.open(self.get_current_dir(ctx), "S:Vamos-Startup", "rb+")
        if fh != None:
            clip.w_s("cli_CurrentInput", fh.mem.addr)
        #
        # Create the path
        cmd_dir_addr = clip.r_s("cli_CommandDir")
        for p in ctx.path_mgr.get_cmd_paths():
            if p != "C:" and p != "c:":
                lock = self.lock_mgr.create_lock(None, p, False)
                if lock != None:
                    path = ctx.alloc.alloc_struct(PathStruct, label="Path(%s)" % p)
                    path.access.w_s("path_Lock", lock.mem.addr)
                    path.access.w_s("path_Next", cmd_dir_addr)
                    cmd_dir_addr = path.addr
                    clip.w_s("cli_CommandDir", cmd_dir_addr)
                    self.path.append((path, lock))
                else:
                    log_dos.warning("Path %s does not exist, expect problems!", p)
        return 0

    def CliInitRun(self, ctx):
        clip_addr = self.Cli(ctx)
        clip = AccessStruct(ctx.mem, CLIStruct, struct_addr=clip_addr)
        pkt = ctx.cpu.r_reg(REG_A0)
        log_dos.info("CliInitRun (0x%06x)" % pkt)
        # This would typically initialize the CLI for running a command
        # from the packet. Anyhow, this is already done, so do nothing here
        return 0x80000004  # valid, and a System() call.

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

    def AssignLock(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_D1)
        lockbaddr = ctx.cpu.r_reg(REG_D2)
        name = ctx.mem.r_cstr(name_ptr)
        if lockbaddr == 0:
            log_dos.info("AssignLock (%s -> null)" % name)
            self.dos_list.remove_assign(name)
            return -1
        else:
            lock = self.lock_mgr.get_by_b_addr(lockbaddr)
            log_dos.info("AssignLock (%s -> %s)" % (name, lock))
            if self.dos_list.create_assign(name, lock) != None:
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
        cli = AccessStruct(ctx.mem, CLIStruct, struct_addr=cli_addr)
        setaddr = cli.r_s("cli_SetName")
        ctx.mem.w_bstr(setaddr, string)
        return self.DOSTRUE

    def SetPrompt(self, ctx):
        str_addr = ctx.cpu.r_reg(REG_D1)
        string = ctx.mem.r_cstr(str_addr)[:59]
        cli_addr = self.Cli(ctx)
        cli = AccessStruct(ctx.mem, CLIStruct, struct_addr=cli_addr)
        setaddr = cli.r_s("cli_Prompt")
        ctx.mem.w_bstr(setaddr, string)
        return self.DOSTRUE

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
        return ctx.process.this_task.access.r_s("pr_FileSystemTask")

    def SetFileSysTask(self, ctx):
        port = ctx.cpu.r_reg(REG_D1)
        ctx.process.this_task.access.w_s("pr_FileSystemTask", port)

    # ----- Helpers -----

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
