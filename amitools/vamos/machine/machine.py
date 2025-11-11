from .opcodes import op_rts, op_rte
from .error import InvalidMemoryAccessError, CPUHWExceptionError, ResetOpcodeError
from .hwexc import CPUHWExceptionHandler
from .backend import Backend
from amitools.vamos.log import log_machine
from amitools.vamos.label import LabelManager


class Machine(object):
    """the main interface to the m68k emulation including CPU, memory,
    and traps. The machine does only a minimal setup of RAM and the CPU.
    It provides a way to run m68k code.

    Minimal Memory Layout:
    ----------------------

    VBR

    000000    SP before Reset / Later mem0
    000004    PC before Reset / Later mem4

    000008    BEGIN CPU Exception Vectors
    ...
    0003FC    END CPU Exception Vectors

    Trap Table for HW Exceptions

    000400    run_exit_trap
    000408    BEGIN CPU Exception Table: hwexc_trap + RTE
    ...
    0007FC    END CPU Exception Table

    Machine Area

    000800    Quick Trap 0
    000802    Quick Trap 1
    ...       ...
    0008FC    Quick Trap 127

    000900    BEGIN of scratch area
    ...       e.g. used for sys stack
    000FFC    END of scratch area

    User Sapce

    001000    RAM begin. useable by applications
    ...
    """

    run_exit_addr = 0x400
    hw_exc_table = 0x400
    ram_begin = 0x1000
    scratch_begin = 0x900
    scratch_end = 0xFFC
    quick_trap_begin = 0x800
    quick_trap_num = 64

    def __init__(
        self,
        raw_machine=None,
        use_labels=True,
        supervisor=False,
    ):
        if not raw_machine:
            raw_machine = Backend.get_default().create_machine()
            assert raw_machine

        self.raw_machine = raw_machine
        self.cpu = self.raw_machine.cpu
        self.mem = self.raw_machine.mem
        self.traps = self.raw_machine.traps
        # ram
        ram_size_kib = self.mem.get_ram_size_kib()
        self.ram_total = ram_size_kib * 1024
        self.ram_bytes = self.ram_total - self.ram_begin
        # start as supervisor
        self.supervisor = supervisor
        # labels
        if use_labels:
            self.label_mgr = LabelManager()
        else:
            self.label_mgr = None
        # hooks
        self.instr_hook = None
        self.reset_hook = None
        self.hw_exc_hook = None
        self.addr_err_hook = None
        # call init
        self._setup_handler()
        self._setup_quick_traps()
        self._init_cpu()
        self._init_base_mem()

    def cleanup(self):
        """clean up after use"""
        self._cleanup_handler()
        self._cleanup_quick_traps()
        self.raw_machine.cleanup()
        self.cpu = None
        self.mem = None
        self.traps = None

    @classmethod
    def from_cfg(cls, machine_cfg, use_labels=False):
        """extract machine parameters from the config

        return new Machine() or None on config error
        """
        cpu_name = machine_cfg.cpu
        ram_size = machine_cfg.ram_size
        hw_exc = machine_cfg.hw_exc
        backend = machine_cfg.backend
        return cls.from_name(cpu_name, ram_size, use_labels, hw_exc, backend)

    @classmethod
    def from_name(
        cls, cpu_name, ram_size=1024, use_labels=False, hw_exc=None, backend_cfg=None
    ):
        log_machine.info(
            "cpu_name=%s, ram_size=%d, labels=%s",
            cpu_name,
            ram_size,
            use_labels,
        )
        # get backend for machine creation
        backend = Backend.from_cfg(backend_cfg)
        if not backend:
            log_machine.error("can't create backend for machine!")
            return None
        # create raw machine from backend
        raw_machine = backend.create_machine(cpu_name, ram_size)
        if not raw_machine:
            log_machine.error(
                "can't create raw machine for cpu=%s, ram=%d", cpu_name, ram_size
            )
            return None
        # finally create machine
        machine = cls(
            raw_machine,
            use_labels=use_labels,
        )
        # setup CPU HW exception handler
        if hw_exc:
            handler = CPUHWExceptionHandler.from_cfg(hw_exc)
            if handler:
                machine.set_hw_exc_hook(handler.handle_error)
        return machine

    def _init_cpu(self):
        # sp and pc does not matter we will overwrite it anyway
        self.mem.w32(0, 0x800)  # init sp
        self.mem.w32(4, 0x400)  # init pc
        # set supervisor stacks
        self.cpu.w_isp(0x700)
        self.cpu.w_msp(0x780)
        # trigger reset (read sp and init pc)
        reset_cycles = self.cpu.pulse_reset()
        # consume reset cycles
        self.cpu.execute(reset_cycles)
        # drop supervisor
        if not self.supervisor:
            sr = self.cpu.r_sr()
            sr &= ~0x2000
            self.cpu.w_sr(sr)

    def _init_base_mem(self):
        m = self.mem
        # m68k exception vector table
        # map all vectors to hw exc table
        vbr_addr = 8
        table_addr = self.hw_exc_table + 8
        for i in range(254):
            m.w32(vbr_addr, table_addr)
            # place a trap and an RTE in each table entry
            m.w16(table_addr, self.hw_exc_tid | 0xA000)
            m.w16(table_addr + 2, op_rte)
            vbr_addr += 4
            table_addr += 4

    def _setup_handler(self):
        # "reset" opcode handler
        self.cpu.set_reset_instr_callback(self._reset_opcode_handler)
        # set invalid access handler for memory
        self.mem.set_invalid_func(self._invalid_mem_access)
        # allocate a trap for hw_exception
        self.hw_exc_tid = self.traps.alloc(self._hw_exc_handler)
        # create a trap result object that marks the end of execution
        self.exit_obj = self.raw_machine.create_execute_end("exit")

        def exit_handler(opcode, pc):
            log_machine.debug("exit handler reached")
            return self.exit_obj

        self.run_exit_tid = self.traps.alloc(exit_handler)
        # place trap to exit obj at run_exit_addr
        opc = 0xA000 | self.run_exit_tid
        self.mem.w16(self.run_exit_addr, opc)

    def _cleanup_handler(self):
        self.traps.free(self.hw_exc_tid)
        self.traps.free(self.run_exit_tid)

    def _setup_quick_traps(self):
        m = self.mem
        addr = self.quick_trap_begin
        for i in range(self.quick_trap_num):
            m.w16(addr, 0)
            m.w16(addr + 2, op_rts)
            addr += 4

    def _cleanup_quick_traps(self):
        m = self.mem
        addr = self.quick_trap_begin
        for i in range(self.quick_trap_num):
            v = m.r16(addr)
            addr += 4
            if v != 0:
                tid = v & 0xFFF
                self.traps.free(tid)

    def setup_quick_trap(self, func):
        m = self.mem
        addr = self.quick_trap_begin
        for i in range(self.quick_trap_num):
            v = m.r16(addr)
            if v == 0:
                tid = self.traps.alloc(func)
                opc = 0xA000 | tid
                m.w16(addr, opc)
                return addr
            addr += 4

    def free_quick_trap(self, addr):
        off = addr - self.quick_trap_begin
        if off < 0 or off >= self.quick_trap_num or off & 1:
            raise ValueError("invalid quick trap addr: %06x" % addr)
        m = self.mem
        opc = m.r16(addr)
        tid = opc & 0xFFF
        self.traps.free(tid)
        m.w16(addr, 0)

    def get_cpu(self):
        return self.cpu

    def get_cpu_type(self):
        return self.cpu.get_cpu_type()

    def get_cpu_name(self):
        return self.cpu.get_cpu_name()

    def get_mem(self):
        return self.mem

    def get_traps(self):
        return self.traps

    def get_label_mgr(self):
        return self.label_mgr

    def get_scratch_top(self):
        return self.ram_begin - 4

    def get_scratch_begin(self):
        return self.scratch_begin

    def get_ram_begin(self):
        """start of useable RAM for applications"""
        return self.ram_begin

    def get_ram_bytes(self):
        """number of useable bytes for applications starting at ram begin"""
        return self.ram_bytes

    def get_ram_kib(self):
        """number of useable bytes for applications starting at ram begin"""
        return self.ram_bytes // 1024

    def get_ram_total(self):
        """number of total bytes in RAM including zero range"""
        return self.ram_total

    def get_ram_total_kib(self):
        return self.ram_total // 1024

    def set_zero_mem(self, mem0, mem4):
        """define the long words at memory address 0 and 4 that are written
        after a reset was performed. On Amiga typically 0 and ExecBase.
        """
        self.mem.w32(0, mem0)
        self.mem.w32(4, mem4)

    def get_run_exit_addr(self):
        return self.run_exit_addr

    def get_sp(self):
        return self.cpu.r_sp()

    def set_sp(self, sp):
        self.cpu.w_sp(sp)

    def get_pc(self):
        return self.cpu.r_pc()

    def set_pc(self, pc):
        self.cpu.w_pc(pc)

    def set_mem(self, mem):
        """replace the memory instance with a wrapped one, e.g. for tracing"""
        self.mem = mem

    def set_instr_hook(self, func):
        self.cpu.set_instr_hook_callback(func)

    def set_reset_hook(self, func):
        """on RESET opcode call func.

        Return True to continue execution or False to raise Error"""
        self.reset_hook = func

    def set_hw_exc_hook(self, func):
        """on CPU HW exception call func.

        Return True to continue execution or False to raise Error"""
        self.hw_exc_hook = func

    def set_addr_err_hook(self, func):
        """on address error call func.

        Return True to continue execution or False to raise Error"""
        self.addr_err_hook = func

    def set_cpu_mem_trace_hook(self, func):
        if func:
            self.mem.set_trace_mode(1)
            self.mem.set_trace_func(func)
        else:
            self.mem.set_trace_mode(0)
            self.mem.set_trace_func(None)

    def _exit_code_handler(self, opcode, pc):
        """regular end of a machine run"""
        sp = self.cpu.r_sp()
        callee_pc = self.mem.r32(sp)
        log_machine.debug(
            "exit code: opcode=%04x, pc=%06x, sp=%06x, callee=%06x",
            opcode,
            pc,
            sp,
            callee_pc,
        )
        # return sentinel for the run loop to exit
        return self.exit_sentinel

    def _invalid_mem_access(self, mode, width, addr):
        """triggered by invalid memory access"""
        log_machine.error(
            "invalid memory access: mode=%s width=%d addr=%06x", mode, width, addr
        )
        pc = self.get_pc()
        sp = self.get_sp()
        self._handle_error(
            InvalidMemoryAccessError(pc, sp, mode, width, addr), self.addr_err_hook
        )

    def _handle_error(self, error, func):
        if func:
            log_machine.debug("handle_error: %s -> func", error)
            handled = func(error)
        else:
            handled = False
        if not handled:
            log_machine.debug("handle_error: raise %s", error)
            raise error

    def _hw_exc_handler(self, opcode, pc):
        """an m68k Hardware Exception was triggered"""
        # get current pc
        sp = self.get_sp()
        # m68k Exception Triggered
        sr = self.mem.r16(sp)
        pc = self.mem.r32(sp + 2)
        log_machine.debug("HW exception: pc=%06x sp=%06x sr=%04x", pc, sp, sr)
        cur_pc = self.get_pc()
        exc_num = (cur_pc - self.hw_exc_table) // 4
        self._handle_error(CPUHWExceptionError(pc, sp, sr, exc_num), self.hw_exc_hook)

    def _reset_opcode_handler(self):
        """a reset opcode was encountered"""
        pc = self.cpu.r_pc() - 2
        sp = self.get_sp()
        log_machine.debug("RESET opcode: pc=%06x sp=%06x", pc, sp)
        self._handle_error(ResetOpcodeError(pc, sp), self.reset_hook)

    def was_exit(self, execute_result):
        """check if a execute() result reached the exit trap"""
        return execute_result.result is self.exit_obj

    def prepare(self, pc, sp):
        self.cpu.w_pc(pc)
        # place end trap on stack
        sp -= 4
        self.mem.w32(sp, self.run_exit_addr)
        self.cpu.w_sp(sp)
        log_machine.debug("  cpu.prepare pc=%06x sp=%06x", pc, sp)

    def execute(self, max_cycles=1000):
        pc = self.cpu.r_pc()
        sp = self.cpu.r_sp()
        log_machine.debug(
            "+ cpu.execute pc=%06x sp=%06x max_cycles=%d", pc, sp, max_cycles
        )

        er = self.raw_machine.execute(max_cycles)

        pc = self.cpu.r_pc()
        sp = self.cpu.r_sp()
        log_machine.debug("- cpu.execute pc=%06x sp=%06x result=%r", pc, sp, er)

        return er
