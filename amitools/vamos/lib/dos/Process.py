from amitools.vamos.libstructs.dos import (
    CLIStruct,
    DosPacketStruct,
    ProcessStruct,
    PathStruct,
)
from amitools.vamos.libstructs.exec_ import MessageStruct, MinListStruct
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
from amitools.vamos.task import DosProcess


NT_PROCESS = 13


class Process(DosProcess):
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
        self.bin_file = bin_file
        self.arg_str = arg_str
        self.shell = shell
        self.cli_paths = []

        if input_fh is None:
            input_fh = self.ctx.dos_lib.file_mgr.get_input()
        if output_fh is None:
            output_fh = self.ctx.dos_lib.file_mgr.get_output()

        self.init_cwd(cwd, cwd_lock)

        # load the binary
        self.ok = self.load_binary(self.cwd_lock, bin_file, shell)
        if not self.ok:
            self.free_cwd()
            return

        if not shell:
            self.init_args(arg_str, input_fh)
        else:
            self.arg = None
            self.arg_base = 0
            self.init_shell_packet()

        # create the DosProcess
        super().__init__(
            ctx.machine,
            ctx.alloc,
            self.bin_basename,
            stack_size=stack_size,
            start_pc=self.prog_start,
            start_regs=self._get_start_regs(stack_size),
            return_regs=[REG_D0],
        )

        self.alloc_cli_struct()
        self.init_task_struct(input_fh, output_fh)
        self.init_cli_struct(input_fh, output_fh, self.bin_basename)
        self.set_cwd()

    def free(self):
        if self.shell:
            self.free_shell_packet()
        else:
            self.free_cwd()
        self.free_task_struct()
        self.free_cli_struct()
        self.free_args()
        self.unload_binary()

        super().free()

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
            log_proc.info("current dir: lock=%s", self.cwd_lock)
            self.set_current_dir(self.cwd_lock.b_addr << 2)

    def free_cwd(self):
        if self.cwd_lock is not None and not self.cwd_shared:
            log_proc.info("current_dir: free lock=%s", self.cwd_lock)
            lock_mgr = self.ctx.dos_lib.lock_mgr
            lock_mgr.release_lock(self.cwd_lock)

    # ----- binary -----
    def load_binary(self, lock, ami_bin_file, shell=False):
        self.bin_basename = self.ctx.path_mgr.ami_name_of_path(lock, ami_bin_file)
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

        self.bin_seg_info = self.ctx.seg_loader.get_info(self.bin_seg_list)
        if not self.bin_seg_info:
            log_proc.error("failed getting binary info: %s", ami_bin_file)
            return False

        self.prog_start = self.bin_seg_info.seglist.get_segment().get_addr()
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
        log_proc.info("loaded binary: %s", self.bin_seg_info)
        for seg in self.bin_seg_info.seglist:
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
    def _get_start_regs(self, stack_size):
        regs = {}
        if self.shell:
            # thor: If we run a shell through vamos, then
            # BPCL places the BPTR to the parameter packet into
            # d1. The default shell can work without ParmPkt
            # thus leave this at zero for this time.
            regs[REG_D1] = self.shell_packet.addr >> 2
            log_proc.info("shell startup packet: BPTR %08x", regs[REG_D1])
        else:
            regs[REG_D0] = self.arg_len
            regs[REG_A0] = self.arg_base
        # d2=stack_size.  this value is also in 4(sp) (see Process.init_stack), but
        # various C programs rely on it being present (1.3-3.1 at least have it).
        regs[REG_D2] = stack_size
        # fill old dos regs with guard
        regs[REG_A2] = self.ctx.odg_base
        regs[REG_A5] = self.ctx.odg_base
        regs[REG_A6] = self.ctx.odg_base
        return regs

    # ----- cli struct -----
    def alloc_cli_struct(self):
        self.cli = self.ctx.alloc.alloc_struct(
            CLIStruct, label=self.bin_basename + "_CLI"
        )

    def init_cli_struct(self, input_fh, output_fh, bin_name):
        cli = self.cli.struct
        cli.cli_DefaultStack.val = self.stack.get_size() // 4  # in longs
        cli.cli_FailLevel.val = 10
        # set input/output
        cli.cli_StandardInput.aptr = input_fh.b_addr << 2
        cli.cli_CurrentInput.aptr = input_fh.b_addr << 2
        cli.cli_StandardOutput.aptr = output_fh.b_addr << 2
        cli.cli_CurrentOutput.aptr = output_fh.b_addr << 2
        # shell uses startup file
        if self.shell:
            startup_file = "S:Vamos-Startup"
            file_mgr = self.ctx.dos_lib.file_mgr
            fh = file_mgr.open(self.cwd_lock, startup_file, "rb+")
            if fh != None:
                log_proc.info("using startup file: %s", startup_file)
                cli.cli_CurrentInput.aptr = fh.mem.addr
            else:
                log_proc.info("startup file not found: %s", startup_file)
        # alloc prompt/cmdname/cmdfile/setname
        self.prompt = self.ctx.alloc.alloc_memory(60, label="cli_Prompt")
        self.cmdname = self.ctx.alloc.alloc_memory(104, label="cli_CommandName")
        self.cmdfile = self.ctx.alloc.alloc_memory(40, label="cli_CommandFile")
        self.setname = self.ctx.alloc.alloc_memory(80, label="cli_SetName")
        cli.cli_Prompt.aptr = self.prompt.addr
        cli.cli_CommandName.aptr = self.cmdname.addr
        cli.cli_CommandFile.aptr = self.cmdfile.addr
        cli.cli_SetName.aptr = self.setname.addr
        # set default prompt
        self.ctx.mem.w_bstr(self.prompt.addr, "%N.%S> ")
        self.ctx.mem.w_bstr(self.setname.addr, "SYS:")
        self.ctx.mem.w_bstr(self.cmdname.addr, bin_name)
        log_proc.info(self.cli)
        # Create the path
        cmd_dir_addr = cli.cli_CommandDir.aptr
        for p in self.ctx.path_mgr.get_cmd_paths():
            if p != "C:" and p != "c:":
                lock = self.ctx.dos_lib.lock_mgr.create_lock(None, p, False)
                if lock != None:
                    path = self.ctx.alloc.alloc_struct(PathStruct, label="Path(%s)" % p)
                    path_struct = path.struct
                    path_struct.path_Lock.aptr = lock.mem.addr
                    path_struct.path_Next.aptr = cmd_dir_addr
                    cmd_dir_addr = path.addr
                    cli.cli_CommandDir.aptr = cmd_dir_addr
                    self.cli_paths.append((path, lock))
                else:
                    log_proc.warning("Path %s does not exist, expect problems!", p)

    def free_cli_struct(self):
        self.ctx.alloc.free_memory(self.prompt)
        self.ctx.alloc.free_memory(self.cmdname)
        self.ctx.alloc.free_memory(self.setname)
        self.ctx.alloc.free_memory(self.cmdfile)
        self.ctx.alloc.free_struct(self.cli)
        # free path
        for path, lock in self.cli_paths:
            self.ctx.alloc.free_struct(path)
            self.ctx.dos_lib.lock_mgr.release_lock(lock)

    def get_cli_struct(self):
        return self.cli.addr

    # ----- initialize for running a command in a shell -----

    def init_shell_packet(self):
        self.shell_message = self.ctx.alloc.alloc_struct(
            MessageStruct, label="Shell Startup Message"
        )
        self.shell_packet = self.ctx.alloc.alloc_struct(
            DosPacketStruct, label="Shell Startup Packet"
        )
        self.shell_port = self.ctx.exec_lib.port_mgr.create_port(
            "Shell Startup Port", None
        )
        shell_packet = self.shell_packet.struct
        shell_message = self.shell_message.struct
        shell_packet.dp_Type.val = 1  # indicate RUN
        shell_packet.dp_Res2.val = 0  # indicate correct startup
        shell_packet.dp_Res1.val = 0  # indicate RUN
        shell_packet.dp_Link.aptr = self.shell_message.addr
        shell_packet.dp_Port.aptr = self.shell_port
        shell_message.mn_Node.ln_Name.aptr = self.shell_packet.addr
        log_proc.info(
            "shell_packet: dp=%08x msg=%08x port=%08x",
            self.shell_packet.addr,
            self.shell_message.addr,
            self.shell_port,
        )

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
        while self.ctx.exec_lib.port_mgr.has_msg(self.shell_port):
            self.ctx.exec_lib.port_mgr.get_msg(self.shell_port)
        return self.shell_packet.addr

    # ----- task struct -----
    def init_task_struct(self, input_fh, output_fh):
        # memory adress of proc
        self.addr = self.ami_proc.addr
        # legacy: old struct mapping
        self.this_task = self.ctx.alloc.map_struct(self.addr, ProcessStruct)
        task = self.this_task.struct
        # Inject arguments into input stream (Needed for C:Execute)
        self.seglist = self.ctx.alloc.alloc_memory(24, label="Process Seglist")
        task.pr_SegList.aptr = self.seglist.addr
        task.pr_CLI.aptr = self.cli.addr
        task.pr_CIS.aptr = input_fh.b_addr << 2  # compensate BCPL auto-conversion
        task.pr_COS.aptr = output_fh.b_addr << 2  # compensate BCPL auto-conversion
        # setup console task
        console_task = self.ctx.dos_lib.file_mgr.get_console_handler_port()
        task.pr_ConsoleTask.aptr = console_task
        # setup file sys task
        fs_task = self.ctx.dos_lib.file_mgr.get_fs_handler_port()
        task.pr_FileSystemTask.aptr = fs_task
        # set home dir
        task.pr_HomeDir.aptr = self.home_lock.b_addr << 2
        varlist = self.get_local_vars()
        varlist_struct = varlist.struct
        # Initialize the list of local shell variables
        varlist_struct.mlh_Head.aptr = varlist.addr + 4
        varlist_struct.mlh_Tail.aptr = 0
        varlist_struct.mlh_TailPred.aptr = varlist.addr
        # setup arg string
        self.set_arg_str_ptr(self.arg_base)

    def free_task_struct(self):
        self.ctx.alloc.free_memory(self.seglist)

    def get_local_vars(self):
        localvars_addr = self.this_task.struct.pr_LocalVars.addr
        return self.ctx.alloc.map_struct(localvars_addr, MinListStruct, label="MinList")

    def get_input(self):
        fh_b = self.this_task.struct.pr_CIS.aptr >> 2
        return self.ctx.dos_lib.file_mgr.get_by_b_addr(fh_b)

    def set_input(self, input_fh):
        if input_fh is None:  # BNULL
            self.this_task.struct.pr_CIS.aptr = 0
        else:
            self.this_task.struct.pr_CIS.aptr = (
                input_fh.b_addr << 2
            )  # compensate BCPL auto-conversion

    def get_output(self):
        fh_b = self.this_task.struct.pr_COS.aptr >> 2
        return self.ctx.dos_lib.file_mgr.get_by_b_addr(fh_b)

    def set_output(self, output_fh):
        if output_fh is None:  # BNULL
            self.this_task.struct.pr_COS.aptr = 0
        else:
            self.this_task.struct.pr_COS.aptr = (
                output_fh.b_addr << 2
            )  # compensate BCPL auto-conversion

    def get_current_dir(self):
        return self.this_task.struct.pr_CurrentDir.aptr

    def set_current_dir(self, lock):
        self.this_task.struct.pr_CurrentDir.aptr = lock

    def get_home_dir(self):
        return self.this_task.struct.pr_HomeDir.aptr

    def set_home_dir(self, lock_addr):
        self.this_task.struct.pr_HomeDir.aptr = lock_addr

    def is_native_shell(self):
        return self.shell

    def get_program_name(self):
        return self.bin_basename

    def get_arg_str_ptr(self):
        return self.this_task.struct.pr_Arguments.aptr

    def set_arg_str_ptr(self, ptr):
        self.this_task.struct.pr_Arguments.aptr = ptr

    def get_current_dir_lock(self):
        lock_mgr = self.ctx.dos_lib.lock_mgr
        lock_baddr = self.get_current_dir() >> 2
        return lock_mgr.get_by_b_addr(lock_baddr)

    def get_home_dir_lock(self):
        lock_mgr = self.ctx.dos_lib.lock_mgr
        lock_baddr = self.get_home_dir() >> 2
        return lock_mgr.get_by_b_addr(lock_baddr)
