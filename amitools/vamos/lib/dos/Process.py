from amitools.vamos.libstructs.dos import CLIStruct, DosPacketStruct, ProcessStruct
from amitools.vamos.libstructs.exec_ import MessageStruct, MinListStruct
from amitools.vamos.lib.dos import CommandLine
from amitools.vamos.log import log_proc
from amitools.vamos.machine.regs import (
    REG_D0,
    REG_D1,
    REG_D2,
    REG_A0,
    REG_A2,
    REG_A5,
    REG_A6,
)
from amitools.vamos.schedule import Stack, Task
import os

from .SysArgs import sys_args_to_ami_arg_str


NT_PROCESS = 13


class Process:
    def __init__(
        self,
        ctx,
        bin_file,
        arg_str,
        input_fh=None,
        output_fh=None,
        stack_size=4096,
        shell=False,
        cwd=None,
        cwd_lock=None,
    ):
        """bin_file  Amiga path to binary for process
        arg_str   Shell-style parameter string with trailing newline
        """
        self.ctx = ctx
        if input_fh == None:
            input_fh = self.ctx.dos_lib.file_mgr.get_input()
        if output_fh == None:
            output_fh = self.ctx.dos_lib.file_mgr.get_output()
        self.init_cwd(cwd, cwd_lock)

        self.ok = self.load_binary(self.cwd_lock, bin_file, shell)
        if not self.ok:
            return
        # setup stack
        self.stack = Stack.alloc(self.ctx.alloc, stack_size)
        log_proc.info(self.stack)
        # thor: the boot shell creates its own CLI if it is not there.
        # but for now, supply it with the Vamos CLI and let it initialize
        # it through the private CliInit() call of the dos.library
        if not shell:
            self.shell = False
            self.init_args(arg_str, input_fh)
            self.init_cli_struct(input_fh, output_fh, self.bin_basename)
        else:
            self.arg = None
            self.arg_base = 0
            self.shell = True
            self.init_cli_struct(None, None, None)
        self.shell_message = None
        self.shell_packet = None
        self.shell_port = None
        self.init_task_struct(input_fh, output_fh)
        self.set_cwd()
        self._init_task()

    def free(self):
        if self.shell == False:
            self.free_cwd()
        self.free_task_struct()
        self.free_shell_packet()
        self.free_cli_struct()
        self.free_args()
        # stack is freed by scheduler
        # self.stack.free()
        self.unload_binary()

    def __str__(self):
        return "[bin='%s']" % self.bin_file

    # ----- current working dir -----
    def init_cwd(self, cwd, cwd_lock):
        self.cwd = cwd
        if cwd is not None and cwd_lock is None:
            lock_mgr = self.ctx.dos_lib.lock_mgr
            dos_list = self.ctx.dos_lib.dos_list
            entry = dos_list.get_entry_by_name("root")
            lock = entry.locks[0]
            self.cwd_lock = lock_mgr.create_lock(lock, cwd, False)
            log_proc.info("current dir: cwd=%s create lock=%s", cwd, self.cwd_lock)
            self.cwd_shared = False
        else:
            self.cwd_lock = cwd_lock
            self.cwd_shared = True
            log_proc.info("current dir: cwd=%s shared lock=%s", cwd, self.cwd_lock)

    def set_cwd(self):
        if self.cwd_lock is not None:
            self.set_current_dir(self.cwd_lock.b_addr << 2)

    def free_cwd(self):
        if self.cwd_lock is not None and not self.cwd_shared:
            log_proc.info("current_dir: free lock=%s", self.cwd_lock)
            lock_mgr = self.ctx.dos_lib.lock_mgr
            lock_mgr.release_lock(self.cwd_lock)

    # ----- stack -----
    def get_stack(self):
        return self.stack

    # ----- binary -----
    def load_binary(self, lock, ami_bin_file, shell=False):
        self.bin_basename = self.ctx.path_mgr.ami_name_of_path(lock, ami_bin_file)
        self.bin_file = ami_bin_file
        sys_path, ami_path = self.ctx.path_mgr.ami_command_to_sys_path(
            lock, ami_bin_file
        )
        if not sys_path:
            log_proc.error("failed loading binary: %s -> %s", ami_bin_file, sys_path)
            return False
        self.bin_seg_list = self.ctx.seg_loader.load_sys_seglist(sys_path)
        if self.bin_seg_list == 0:
            log_proc.error("failed loading seglist: %s", sys_path)
            return False
        info = self.ctx.seg_loader.get_info(self.bin_seg_list)
        if not info:
            log_proc.error("failed getting binary info: %s", ami_bin_file)
            return False
        self.prog_start = info.seglist.get_segment().get_addr()
        # set home dir and get lock
        self.home_dir = self.ctx.path_mgr.ami_dir_of_path(lock, ami_path)
        lock_mgr = self.ctx.dos_lib.lock_mgr
        self.home_lock = lock_mgr.create_lock(lock, self.home_dir, False)
        log_proc.info("home dir: %s", self.home_lock)
        # THOR: If this is a shell, then the seglist requires BCPL linkage and
        # initialization of the GlobVec. Fortunately, for the 3.9 shell all this
        # magic is not really required, and the BCPL call-in (we use) is at
        # offset +8
        if shell:
            self.prog_start += 8
            self.shell_start = self.prog_start
        log_proc.info("loaded binary: %s", info)
        for seg in info.seglist:
            log_proc.info(seg)
        return True

    def unload_binary(self):
        self.ctx.seg_loader.unload_seglist(self.bin_seg_list)
        # unlock home dir
        lock_mgr = self.ctx.dos_lib.lock_mgr
        lock_mgr.release_lock(self.home_lock)

    # ----- args -----
    def init_args(self, arg_str, fh):
        # Tripos makes the input line available as buffered input for ReadItem()
        fh.setbuf(arg_str)
        # alloc and fill arg buffer
        self.arg_len = len(arg_str)
        name = self.bin_basename + "_args"
        self.arg = self.ctx.alloc.alloc_memory(self.arg_len + 1, label=name)
        self.arg_base = self.arg.addr
        self.ctx.mem.w_cstr(self.arg_base, arg_str)
        log_proc.info("args: '%s' (%d)", arg_str[:-1], self.arg_len)
        log_proc.info(self.arg)

    def free_args(self):
        if self.arg is not None:
            self.ctx.alloc.free_memory(self.arg)

    # ----- scheduler task setup -----
    def _get_start_regs(self):
        regs = {}
        if self.shell:
            # thor: If we run a shell through vamos, then
            # BPCL places the BPTR to the parameter packet into
            # d1. The default shell can work without ParmPkt
            # thus leave this at zero for this time.
            regs[REG_D1] = 0
        else:
            regs[REG_D0] = self.arg_len
            regs[REG_A0] = self.arg_base
        # d2=stack_size.  this value is also in 4(sp) (see Process.init_stack), but
        # various C programs rely on it being present (1.3-3.1 at least have it).
        regs[REG_D2] = self.stack.get_size()
        # fill old dos regs with guard
        regs[REG_A2] = self.ctx.odg_base
        regs[REG_A5] = self.ctx.odg_base
        regs[REG_A6] = self.ctx.odg_base
        return regs

    def _init_task(self):
        name = self.bin_basename
        init_pc = self.prog_start
        start_regs = self._get_start_regs()
        return_regs = [REG_D0]
        self.task = Task(name, init_pc, self.stack, start_regs, return_regs)
        # store back ref to process
        self.task.process = self

    def get_task(self):
        return self.task

    # ----- cli struct -----
    def init_cli_struct(self, input_fh, output_fh, name):
        self.cli = self.ctx.alloc.alloc_struct(
            CLIStruct, label=self.bin_basename + "_CLI"
        )
        self.cli.access.w_s("cli_DefaultStack", self.stack.get_size() // 4)  # in longs
        if input_fh != None:
            self.cli.access.w_s("cli_StandardInput", input_fh.b_addr << 2)
            self.cli.access.w_s("cli_CurrentInput", input_fh.b_addr << 2)
        if output_fh != None:
            self.cli.access.w_s("cli_StandardOutput", output_fh.b_addr << 2)
            self.cli.access.w_s("cli_CurrentOutput", output_fh.b_addr << 2)
        self.prompt = self.ctx.alloc.alloc_memory(60, label="cli_Prompt")
        self.cmdname = self.ctx.alloc.alloc_memory(104, label="cli_CommandName")
        self.cmdfile = self.ctx.alloc.alloc_memory(40, label="cli_CommandFile")
        self.setname = self.ctx.alloc.alloc_memory(80, label="cli_SetName")
        self.cli.access.w_s("cli_Prompt", self.prompt.addr)
        self.cli.access.w_s("cli_CommandName", self.cmdname.addr)
        self.cli.access.w_s("cli_CommandFile", self.cmdfile.addr)
        self.cli.access.w_s("cli_SetName", self.setname.addr)
        if name != None:
            self.ctx.mem.w_bstr(self.cmdname.addr, name)
        log_proc.info(self.cli)

    def free_cli_struct(self):
        self.ctx.alloc.free_memory(self.prompt)
        self.ctx.alloc.free_memory(self.cmdname)
        self.ctx.alloc.free_memory(self.setname)
        self.ctx.alloc.free_memory(self.cmdfile)
        self.ctx.alloc.free_struct(self.cli)

    def get_cli_struct(self):
        return self.cli.addr

    # ----- initialize for running a command in a shell -----

    def free_shell_packet(self):
        if self.shell_message != None:
            self.ctx.alloc.free_struct(self.shell_message)
            self.shell_message = None
        if self.shell_packet != None:
            self.ctx.alloc.free_struct(self.shell_packet)
            self.shell_packet = None
        if self.shell_port != None:
            self.ctx.exec_lib.port_mgr.free_port(self.shell_port)
            self.shell_port = None

    def run_system(self):
        if self.shell_packet == None:
            # Ok, here we have to create a DosPacket for the shell startup
            self.shell_message = self.ctx.alloc.alloc_struct(
                MessageStruct, label="Shell Startup Message"
            )
            self.shell_packet = self.ctx.alloc.alloc_struct(
                DosPacketStruct, label="Shell Startup Packet"
            )
            self.shell_port = self.ctx.exec_lib.port_mgr.create_port(
                "Shell Startup Port", None
            )
        self.shell_packet.access.w_s("dp_Type", 1)  # indicate RUN
        self.shell_packet.access.w_s("dp_Res2", 0)  # indicate correct startup
        self.shell_packet.access.w_s("dp_Res1", 0)  # indicate RUN
        self.shell_packet.access.w_s("dp_Link", self.shell_message.addr)
        self.shell_packet.access.w_s("dp_Port", self.shell_port)
        self.shell_message.access.w_s("mn_Node.ln_Name", self.shell_packet.addr)
        while self.ctx.exec_lib.port_mgr.has_msg(self.shell_port):
            self.ctx.exec_lib.port_mgr.get_msg(self.shell_port)
        return self.shell_packet.addr

    # ----- task struct -----
    def init_task_struct(self, input_fh, output_fh):
        # Inject arguments into input stream (Needed for C:Execute)
        self.this_task = self.ctx.alloc.alloc_struct(
            ProcessStruct, label=self.bin_basename + "_ThisTask"
        )
        self.seglist = self.ctx.alloc.alloc_memory(24, label="Process Seglist")
        self.this_task.access.w_s("pr_Task.tc_Node.ln_Type", NT_PROCESS)
        self.this_task.access.w_s("pr_SegList", self.seglist.addr)
        self.this_task.access.w_s("pr_CLI", self.cli.addr)
        self.this_task.access.w_s(
            "pr_CIS", input_fh.b_addr << 2
        )  # compensate BCPL auto-conversion
        self.this_task.access.w_s(
            "pr_COS", output_fh.b_addr << 2
        )  # compensate BCPL auto-conversion
        # setup console task
        console_task = self.ctx.dos_lib.file_mgr.get_console_handler_port()
        self.this_task.access.w_s("pr_ConsoleTask", console_task)
        # setup file sys task
        fs_task = self.ctx.dos_lib.file_mgr.get_fs_handler_port()
        self.this_task.access.w_s("pr_FileSystemTask", fs_task)
        # set home dir
        self.this_task.access.w_s("pr_HomeDir", self.home_lock.b_addr << 2)
        varlist = self.get_local_vars()
        # Initialize the list of local shell variables
        varlist.access.w_s("mlh_Head", varlist.addr + 4)
        varlist.access.w_s("mlh_Tail", 0)
        varlist.access.w_s("mlh_TailPred", varlist.addr)
        # setup arg string
        self.set_arg_str_ptr(self.arg_base)

    def free_task_struct(self):
        self.ctx.alloc.free_struct(self.this_task)
        self.ctx.alloc.free_memory(self.seglist)

    def get_local_vars(self):
        localvars_addr = self.this_task.access.s_get_addr("pr_LocalVars")
        return self.ctx.alloc.map_struct(localvars_addr, MinListStruct, label="MinList")

    def get_input(self):
        fh_b = self.this_task.access.r_s("pr_CIS") >> 2
        return self.ctx.dos_lib.file_mgr.get_by_b_addr(fh_b)

    def set_input(self, input_fh):
        if input_fh is None:  # BNULL
            self.this_task.access.w_s("pr_CIS", 0)
        else:
            self.this_task.access.w_s(
                "pr_CIS", input_fh.b_addr << 2
            )  # compensate BCPL auto-conversion

    def get_output(self):
        fh_b = self.this_task.access.r_s("pr_COS") >> 2
        return self.ctx.dos_lib.file_mgr.get_by_b_addr(fh_b)

    def set_output(self, output_fh):
        if output_fh is None:  # BNULL
            self.this_task.access.w_s("pr_COS", 0)
        else:
            self.this_task.access.w_s(
                "pr_COS", output_fh.b_addr << 2
            )  # compensate BCPL auto-conversion

    def get_current_dir(self):
        return self.this_task.access.r_s("pr_CurrentDir")

    def set_current_dir(self, lock):
        self.this_task.access.w_s("pr_CurrentDir", lock)

    def get_home_dir(self):
        return self.this_task.access.r_s("pr_HomeDir")

    def set_home_dir(self, lock_addr):
        self.this_task.access.w_s("pr_HomeDir", lock_addr)

    def is_native_shell(self):
        return self.shell

    def get_program_name(self):
        return self.bin_basename

    def get_arg_str_ptr(self):
        return self.this_task.access.r_s("pr_Arguments")

    def set_arg_str_ptr(self, ptr):
        self.this_task.access.w_s("pr_Arguments", ptr)

    def get_current_dir_lock(self):
        lock_mgr = self.ctx.dos_lib.lock_mgr
        lock_baddr = self.get_current_dir() >> 2
        return lock_mgr.get_by_b_addr(lock_baddr)

    def get_home_dir_lock(self):
        lock_mgr = self.ctx.dos_lib.lock_mgr
        lock_baddr = self.get_home_dir() >> 2
        return lock_mgr.get_by_b_addr(lock_baddr)

    # create main proc

    @classmethod
    def create_main_proc(cls, proc_cfg, path_mgr, dos_ctx):
        # a single Amiga-like raw arg was passed
        cmd_cfg = proc_cfg.command
        if cmd_cfg.raw_arg:
            # check args
            if len(cmd_cfg.args) > 0:
                log_proc.error("raw arg only allows a single argument!")
                return None
            # parse raw arg
            cl = CommandLine()
            res = cl.parse_line(cmd_cfg.binary)
            if res != cl.LINE_OK:
                log_proc.error("raw arg is invalid! (error %d)", res)
                return None
            binary = cl.get_cmd()
            arg_str = cl.get_arg_str()
        else:
            # setup binary
            binary = cmd_cfg.binary
            if not cmd_cfg.pure_ami_path:
                # if path exists on host system then make an ami path
                if os.path.exists(binary):
                    sys_binary = binary
                    binary = path_mgr.from_sys_path(binary)
                    if not binary:
                        log_proc.error("can't map binary: %s", sys_binary)
                        return None
            # combine remaining args to arg_str
            arg_str = sys_args_to_ami_arg_str(cmd_cfg.args)

        # summary
        stack_size = proc_cfg.stack * 1024
        shell = proc_cfg.command.shell
        log_proc.info("binary: '%s'", binary)
        log_proc.info("args:   '%s'", arg_str[:-1])
        log_proc.info("stack:  %d", stack_size)

        cwd = str(path_mgr.get_cwd())
        proc = cls(
            dos_ctx, binary, arg_str, stack_size=stack_size, shell=shell, cwd=cwd
        )
        if not proc.ok:
            return None
        log_proc.info("set main process: %s", proc)
        return proc
