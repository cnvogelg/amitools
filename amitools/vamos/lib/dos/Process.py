from amitools.vamos.libstructs.dos import DosPacketStruct
from amitools.vamos.libstructs.exec_ import MessageStruct
from amitools.vamos.handler import DosProtection, HandlerError, HostFileSysHandler
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
from amitools.vamos.path.amipath import AmiPath
from amitools.vamos.task import DosProcess
from .ucli import MicroCLI


NT_PROCESS = 13


class ProcessBase(DosProcess):
    """shared lifecycle for running an AmigaDOS program.

    The single-binary and the shell path live behind the overridable hooks
    ``init_environment``/``free_environment``, ``_setup_entry``,
    ``_add_program_regs`` and ``_setup_cli_input`` so that the concrete
    ``BinProcess``/``ShellProcess`` subclasses can specialize them.
    """

    def __init__(
        self,
        ctx,
        bin_file,
        arg_str,
        input_fh=None,
        output_fh=None,
        stack_size=4096,
        cwd=None,
        cwd_lock=None,
    ):
        """bin_file  Amiga path to binary for process
        arg_str   Shell-style parameter string with trailing newline
        """
        self.ctx = ctx
        self.bin_file = bin_file
        self.arg_str = arg_str

        if input_fh is None:
            input_fh = self.ctx.dos_lib.file_mgr.get_input()
        if output_fh is None:
            output_fh = self.ctx.dos_lib.file_mgr.get_output()

        self.init_cwd(cwd, cwd_lock)

        # load the binary
        self.ok = self.load_binary(self.cwd_lock, bin_file)
        if not self.ok:
            self.free_cwd()
            return

        self.init_environment(arg_str, input_fh)

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

        self.init_cli_struct(input_fh, output_fh, self.bin_basename)
        self.init_task_struct(input_fh, output_fh)
        self.set_cwd()

    def free(self):
        self.free_environment()
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
    def load_binary(self, lock, ami_bin_file):
        self.bin_basename = self.ctx.path_mgr.ami_name_of_path(lock, ami_bin_file)
        # search the command on the command path and try each candidate
        cmd_paths = self.ctx.path_mgr.ami_command_paths(lock, ami_bin_file)
        # a bare command name is looked up on the command path: only pick up a
        # Python command there when it is marked executable (an explicit path
        # with a directory component is loaded without the gate)
        search = AmiPath(str(ami_bin_file)).is_name_only()
        ami_path = None
        self.bin_seg_list = 0
        for path in cmd_paths:
            if search and not self._command_allowed(path, lock):
                log_proc.info("skip non-executable command: %s", path)
                continue
            baddr = self.ctx.seg_loader.load_ami_seglist(path, lock)
            if baddr:
                ami_path = path
                self.bin_seg_list = baddr
                break
        if ami_path is None:
            log_proc.error("failed loading binary: %s", ami_bin_file)
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
        self._setup_entry()
        log_proc.info("loaded binary: %s", self.bin_seg_info)
        for seg in self.bin_seg_info.seglist:
            log_proc.info(seg)
        return True

    def _command_allowed(self, ami_path, lock):
        """apply the executable gate to a command-path candidate.

        A native binary is always allowed. A Python command is only allowed
        when it is marked executable: the host execute bit on a host-backed
        volume, the Amiga ``s`` (script) protection bit on any other volume.
        """
        seg_loader = getattr(self.ctx, "seg_loader", None)
        if seg_loader is None or not seg_loader.is_python_command(ami_path, lock):
            return True
        return self._is_command_executable(ami_path, lock)

    def _is_command_executable(self, ami_path, lock):
        handler_mgr = getattr(self.ctx, "handler_mgr", None)
        if handler_mgr is None:
            # no handler layer to ask: don't block the command
            return True
        cwd = lock.ami_path if lock is not None else None
        try:
            handler, handler_lock = handler_mgr.locate_object(ami_path, cwd=cwd)
        except HandlerError:
            return False
        try:
            info = handler.examine_object(handler_lock)
        except HandlerError:
            return False
        finally:
            handler.free_lock(handler_lock)
        prot = DosProtection(info.protection)
        if isinstance(handler, HostFileSysHandler):
            # host-backed volume: the host execute bit (active low)
            return prot.is_e()
        # other volume (RAM:, ADF, ...): the Amiga script bit
        return bool(prot.mask & DosProtection.FIBF_SCRIPT)

    def _setup_entry(self):
        # a single binary is entered at the start of its first segment;
        # ShellProcess overrides this to use the BCPL call-in at +8
        pass

    def unload_binary(self):
        self.ctx.seg_loader.unload_seglist(self.bin_seg_list)
        # unlock home dir
        lock_mgr = self.ctx.dos_lib.lock_mgr
        lock_mgr.release_lock(self.home_lock)

    # ----- environment: args vs shell packet -----
    def init_environment(self, arg_str, input_fh):
        # the non-shell default: hand the argument string to the program.
        # ShellProcess overrides this to build the shell startup packet.
        self.init_args(arg_str, input_fh)

    def free_environment(self):
        self.free_cwd()

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
        self._add_program_regs(regs)
        # d2=stack_size.  this value is also in 4(sp) (see Process.init_stack), but
        # various C programs rely on it being present (1.3-3.1 at least have it).
        regs[REG_D2] = stack_size
        # fill old dos regs with guard
        regs[REG_A2] = self.ctx.odg_base
        regs[REG_A5] = self.ctx.odg_base
        regs[REG_A6] = self.ctx.odg_base
        return regs

    def _add_program_regs(self, regs):
        # the concrete processes add their startup registers: BinProcess
        # passes the argument string in D0/A0, ShellProcess the startup
        # packet in D1
        pass

    # ----- cli struct -----
    def init_cli_struct(self, input_fh, output_fh, bin_name):
        # build the minimal ("micro") CLI, then let the subclass adjust it
        self.ucli = MicroCLI(
            self.ctx, input_fh, output_fh, bin_name, self.stack.get_size()
        )
        self._setup_cli_input(self.ucli.cli)

    def _setup_cli_input(self, cli):
        # a single binary keeps reading from its standard input; ShellProcess
        # overrides this to redirect cli_CurrentInput to S:Vamos-Startup
        pass

    def free_cli_struct(self):
        self.ucli.free()

    # ----- task struct -----

    def _handler_port(self, name):
        """the packet port of the handler serving ``name`` (0 if none)"""
        mgr = getattr(self.ctx.dos_lib, "handler_mgr", None)
        if mgr is None:
            return 0
        get_dispatcher = getattr(mgr, "get_dispatcher", None)
        if get_dispatcher is None:
            return 0
        dispatcher = get_dispatcher(name)
        return dispatcher.port if dispatcher is not None else 0

    def init_task_struct(self, input_fh, output_fh):
        task = self.proc
        # Inject arguments into input stream (Needed for C:Execute)
        self.seglist = self.ctx.alloc.alloc_memory(24, label="Process Seglist")
        task.pr_SegList.aptr = self.seglist.addr
        task.pr_CLI.aptr = self.ucli.addr
        task.pr_CIS.aptr = input_fh.b_addr << 2  # compensate BCPL auto-conversion
        task.pr_COS.aptr = output_fh.b_addr << 2  # compensate BCPL auto-conversion
        # setup console task: the console handler's packet port
        task.pr_ConsoleTask.aptr = self._handler_port("console")
        # setup file sys task: the handler of the process's current volume
        volume = self.ctx.path_mgr.ami_volume_of_path(self.home_lock.ami_path)
        task.pr_FileSystemTask.aptr = self._handler_port(volume)
        # set home dir
        task.pr_HomeDir.aptr = self.home_lock.b_addr << 2
        varlist = self.get_local_vars()
        varlist_struct = varlist
        # Initialize the list of local shell variables
        varlist_struct.mlh_Head.aptr = varlist.addr + 4
        varlist_struct.mlh_Tail.aptr = 0
        varlist_struct.mlh_TailPred.aptr = varlist.addr
        # setup arg string
        self.set_arg_str_ptr(self.arg_base)

    def free_task_struct(self):
        self.ctx.alloc.free_memory(self.seglist)

    def get_input(self):
        fh_b = self.proc.pr_CIS.aptr >> 2
        return self.ctx.dos_lib.file_mgr.get_by_b_addr(fh_b)

    def set_input(self, input_fh):
        if input_fh is None:  # BNULL
            self.proc.pr_CIS.aptr = 0
        else:
            self.proc.pr_CIS.aptr = (
                input_fh.b_addr << 2
            )  # compensate BCPL auto-conversion

    def get_output(self):
        fh_b = self.proc.pr_COS.aptr >> 2
        return self.ctx.dos_lib.file_mgr.get_by_b_addr(fh_b)

    def set_output(self, output_fh):
        if output_fh is None:  # BNULL
            self.proc.pr_COS.aptr = 0
        else:
            self.proc.pr_COS.aptr = (
                output_fh.b_addr << 2
            )  # compensate BCPL auto-conversion

    def is_native_shell(self):
        return False

    def get_program_name(self):
        return self.bin_basename

    def get_arg_str_ptr(self):
        return self.proc.pr_Arguments.aptr

    def set_arg_str_ptr(self, ptr):
        self.proc.pr_Arguments.aptr = ptr

    def get_current_dir_lock(self):
        lock_mgr = self.ctx.dos_lib.lock_mgr
        lock_baddr = self.get_current_dir() >> 2
        return lock_mgr.get_by_b_addr(lock_baddr)

    def get_home_dir_lock(self):
        lock_mgr = self.ctx.dos_lib.lock_mgr
        lock_baddr = self.get_home_dir() >> 2
        return lock_mgr.get_by_b_addr(lock_baddr)


class BinProcess(ProcessBase):
    """run a single binary with a minimal CLI (the ``proc`` mode).

    The non-shell counterpart of ``ShellProcess``: the argument string is
    handed to the program in D0/A0 and it gets a uCLI, with no startup packet
    and no ``S:Vamos-Startup`` redirect.
    """

    def __init__(
        self,
        ctx,
        bin_file,
        arg_str,
        input_fh=None,
        output_fh=None,
        stack_size=4096,
        cwd=None,
        cwd_lock=None,
    ):
        super().__init__(
            ctx,
            bin_file,
            arg_str,
            input_fh=input_fh,
            output_fh=output_fh,
            stack_size=stack_size,
            cwd=cwd,
            cwd_lock=cwd_lock,
        )

    def _add_program_regs(self, regs):
        # a single binary receives its argument string in D0/A0
        regs[REG_D0] = self.arg_len
        regs[REG_A0] = self.arg_base

    def is_native_shell(self):
        return False


class ShellProcess(ProcessBase):
    """run a shell segment, e.g. ``L:shell-seg`` (the ``shell`` mode).

    The shell counterpart of ``BinProcess``: the entry point is the BCPL
    call-in at seglist ``+8``, the shell receives a startup ``DosPacket`` in
    D1 instead of an argument string in D0/A0, ``cli_CurrentInput`` is
    redirected to ``S:Vamos-Startup`` when that file exists, and A6 holds the
    BCPL return address the entry stub returns through.
    """

    def __init__(
        self,
        ctx,
        bin_file,
        arg_str=None,
        input_fh=None,
        output_fh=None,
        stack_size=4096,
        cwd=None,
        cwd_lock=None,
    ):
        super().__init__(
            ctx,
            bin_file,
            arg_str,
            input_fh=input_fh,
            output_fh=output_fh,
            stack_size=stack_size,
            cwd=cwd,
            cwd_lock=cwd_lock,
        )

    def _setup_entry(self):
        # THOR: If this is a shell, then the seglist requires BCPL linkage and
        # initialization of the GlobVec. Fortunately, for the 3.9 shell all
        # this magic is not really required, and the BCPL call-in (we use) is
        # at offset +8
        self.prog_start += 8
        self.shell_start = self.prog_start

    def init_environment(self, arg_str, input_fh):
        # a shell gets no argument string, only a startup packet
        self.arg = None
        self.arg_base = 0
        self.init_shell_packet()

    def free_environment(self):
        self.free_shell_packet()

    def _get_start_regs(self, stack_size):
        regs = super()._get_start_regs(stack_size)
        # A BCPL shell returns through the address in A6: the BCPL startup
        # stub ends with "jmp (a6)" and A6 is the address of the BCPL return
        # code (see RKRM-dos "Runtime binding of BCPL programs").  Point it
        # at the machine's exit trap so the shell leaves the process cleanly
        # instead of jumping into odg_base.
        regs[REG_A6] = self.ctx.machine.get_run_exit_addr()
        return regs

    def _add_program_regs(self, regs):
        # thor: If we run a shell through vamos, then BPCL places the BPTR to
        # the parameter packet into d1. The default shell can work without
        # ParmPkt thus leave this at zero for this time.
        regs[REG_D1] = self.shell_packet.addr >> 2
        log_proc.info("shell startup packet: BPTR %08x", regs[REG_D1])

    def _setup_cli_input(self, cli):
        # a shell reads its startup commands from S:Vamos-Startup
        startup_file = "S:Vamos-Startup"
        file_mgr = self.ctx.dos_lib.file_mgr
        fh = file_mgr.open(self.cwd_lock, startup_file, "rb+")
        if fh is not None:
            log_proc.info("using startup file: %s", startup_file)
            cli.cli_CurrentInput.aptr = fh.mem.addr
        else:
            log_proc.info("startup file not found: %s", startup_file)

    def is_native_shell(self):
        return True

    # ----- shell startup packet -----

    def init_shell_packet(self):
        self.shell_message = self.ctx.alloc.alloc_astruct(
            MessageStruct, label="Shell Startup Message"
        )
        self.shell_packet = self.ctx.alloc.alloc_astruct(
            DosPacketStruct, label="Shell Startup Packet"
        )
        self.shell_port = self.ctx.exec_lib.port_mgr.create_port(
            "Shell Startup Port", None
        )
        shell_packet = self.shell_packet
        shell_message = self.shell_message
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
        if self.shell_message is not None:
            self.shell_message.free()
            self.shell_message = None
        if self.shell_packet is not None:
            self.shell_packet.free()
            self.shell_packet = None
        if self.shell_port is not None:
            self.ctx.exec_lib.port_mgr.free_port(self.shell_port)
            self.shell_port = None

    def run_system(self):
        while self.ctx.exec_lib.port_mgr.has_msg(self.shell_port):
            self.ctx.exec_lib.port_mgr.get_msg(self.shell_port)
        return self.shell_packet.addr
