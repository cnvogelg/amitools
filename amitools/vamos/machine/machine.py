import time
import sys
from machine import emu
from machine.m68k import *
from .regs import *
from .opcodes import *
from .error import ErrorReporter
from .cpustate import CPUState
from amitools.vamos.error import *
from amitools.vamos.log import log_machine
from amitools.vamos.label import LabelManager


class RunState(object):
    def __init__(self, name, pc, sp, ret_addr):
        self.name = name
        self.pc = pc
        self.sp = sp
        self.ret_addr = ret_addr
        self.error = None
        self.done = False
        self.cycles = 0
        self.time_delta = 0
        self.regs = None

    def __str__(self):
        return (
            "RunState('%s', pc=%06x,sp=%06x,ret_addr=%06x,error=%s,done=%s,"
            "cycles=%s,time_delta=%s,regs=%s)"
            % (
                self.name,
                self.pc,
                self.sp,
                self.ret_addr,
                self.error,
                self.done,
                self.cycles,
                self.time_delta,
                self.regs,
            )
        )


class Machine(object):
    """the main interface to the m68k emulation including CPU, memory,
    and traps. The machine does only a minimal setup of RAM and the CPU.
    It provides a way to run m68k code.

    Minimal Memory Layout:
    ----------------------

    VBR

    000000    SP before Reset / Later mem0
    000004    PC before Reset / Later mem4

    000008    BEGIN Exception Vectors
    ......
    0003FC    END Exception Vectors

    Machine Area

    000400    run_exit trap
    000402    exception handling trap

    000500    Quick Trap 0
    000502    Quick Trap 1
    ...       ...
    0005FC    Quick Trap 127

    000600    BEGIN of scratch area
    ...       e.g. used for sys stack
    0007FC    END of scratch area
    000800    RAM begin. useable by applications
    """

    CPU_TYPE_68000 = M68K_CPU_TYPE_68000
    CPU_TYPE_68020 = M68K_CPU_TYPE_68020
    CPU_TYPE_68040 = M68K_CPU_TYPE_68040

    run_exit_addr = 0x400
    hw_exc_addr = 0x402
    ram_begin = 0x800
    scratch_begin = 0x600
    quick_trap_begin = 0x500
    quick_trap_num = 128

    def __init__(
        self,
        cpu_type=M68K_CPU_TYPE_68000,
        ram_size_kib=1024,
        use_labels=True,
        raise_on_main_run=True,
        cycles_per_run=1000,
        max_cycles=0,
        cpu_name=None,
    ):
        if cpu_name is None:
            cpu_name = self._get_cpu_name(cpu_type)
        # setup musashi components
        self.cpu_type = cpu_type
        self.cpu_name = cpu_name
        self.cpu = emu.CPU(cpu_type)
        self.mem = emu.Memory(ram_size_kib)
        self.traps = emu.Traps()
        # internal state
        if use_labels:
            self.label_mgr = LabelManager()
        else:
            self.label_mgr = None
        self.raise_on_main_run = raise_on_main_run
        self.ram_total = ram_size_kib * 1024
        self.ram_bytes = self.ram_total - self.ram_begin
        self.error_reporter = ErrorReporter(self)
        self.run_states = []
        self.instr_hook = None
        self.cycles_per_run = cycles_per_run
        self.max_cycles = max_cycles
        self.bail_out = False
        # call init
        self._setup_handler()
        self._setup_quick_traps()
        self._init_cpu()
        self._init_base_mem()

    def cleanup(self):
        """clean up after use"""
        self._cleanup_handler()
        self._cleanup_quick_traps()
        self.cpu.cleanup()
        self.mem.cleanup()
        self.traps.cleanup()
        self.cpu = None
        self.mem = None
        self.traps = None

    @classmethod
    def from_cfg(cls, machine_cfg, use_labels=False):
        """extract machine parameters from the config

        return new Machine() or None on config error
        """
        cpu = machine_cfg.cpu
        cpu_type, cpu_name = cls.parse_cpu_type(cpu)
        if cpu_type is None:
            log_machine.error("invalid CPU type given: %s", cpu)
            return None
        ram_size = machine_cfg.ram_size
        cycles_per_run = machine_cfg.cycles_per_run
        max_cycles = machine_cfg.max_cycles
        log_machine.info(
            "cpu=%s(%d), ram_size=%d, labels=%s, " "cycles_per_run=%d, max_cycles=%d",
            cpu_name,
            cpu_type,
            ram_size,
            use_labels,
            cycles_per_run,
            max_cycles,
        )
        return cls(
            cpu_type,
            ram_size,
            raise_on_main_run=False,
            use_labels=use_labels,
            cycles_per_run=cycles_per_run,
            max_cycles=max_cycles,
            cpu_name=cpu_name,
        )

    @classmethod
    def parse_cpu_type(cls, cpu_str):
        if cpu_str in ("68000", "000", "00"):
            return cls.CPU_TYPE_68000, "68000"
        elif cpu_str in ("68020", "020", "20"):
            return cls.CPU_TYPE_68020, "68020"
        elif cpu_str in ("68030", "030", "30"):
            # fake 030 CPU only to set AttnFlags accordingly
            return cls.CPU_TYPE_68020, "68030(fake)"
        elif cpu_str in ("68040", "040", "40"):
            return cls.CPU_TYPE_68040, "68040"
        else:
            return None, None

    def _get_cpu_name(self, cpu_type):
        if cpu_type == self.CPU_TYPE_68000:
            return "68000"
        elif cpu_type == self.CPU_TYPE_68020:
            return "68020"
        elif cpu_type == self.CPU_TYPE_68040:
            return "68040"
        else:
            return None

    def _init_cpu(self):
        # sp and pc does not matter we will overwrite it anyway
        self.mem.w32(0, 0x800)  # init sp
        self.mem.w32(4, 0x400)  # init pc
        # set supervisor stacks
        self.cpu.w_isp(0x700)
        self.cpu.w_msp(0x780)
        # trigger reset (read sp and init pc)
        self.cpu.pulse_reset()
        # drop supervisor
        sr = self.cpu.r_sr()
        sr &= ~0x2000
        self.cpu.w_sr(sr)

    def _init_base_mem(self):
        m = self.mem
        # m68k exception vector table
        addr = 8
        for i in range(254):
            m.w32(addr, self.hw_exc_addr)
            addr += 4
        # run_exit trap
        addr = self.run_exit_addr
        m.w16(addr, self.run_exit_tid | 0xA000)
        # hw_exc trap
        addr = self.hw_exc_addr
        m.w16(addr, self.hw_exc_tid | 0xA000)

    def _setup_handler(self):
        # reset opcode handler
        self.cpu.set_reset_instr_callback(self._reset_opcode_handler)
        # set invalid access handler for memory
        self.mem.set_invalid_func(self._invalid_mem_access)
        # set traps exception handler
        self.traps.set_exc_func(self._trap_exc_handler)
        # allocate a trap for exit_run and hw_exception
        self.run_exit_tid = self.traps.setup(self._run_exit_handler)
        self.hw_exc_tid = self.traps.setup(self._hw_exc_handler)

    def _cleanup_handler(self):
        self.traps.free(self.hw_exc_tid)
        self.traps.free(self.run_exit_tid)

    def _setup_quick_traps(self):
        m = self.mem
        addr = self.quick_trap_begin
        for i in range(self.quick_trap_num):
            m.w16(addr, 0)
            addr += 2

    def _cleanup_quick_traps(self):
        m = self.mem
        addr = self.quick_trap_begin
        for i in range(self.quick_trap_num):
            v = m.r16(addr)
            addr += 2
            if v != 0:
                tid = v & 0xFFF
                self.traps.free(tid)

    def setup_quick_trap(self, func):
        m = self.mem
        addr = self.quick_trap_begin
        for i in range(self.quick_trap_num):
            v = m.r16(addr)
            if v == 0:
                tid = self.traps.setup(func, auto_rts=True)
                opc = 0xA000 | tid
                m.w16(addr, opc)
                return addr
            addr += 2

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
        return self.cpu_type

    def get_cpu_name(self):
        return self.cpu_name

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

    def set_mem(self, mem):
        """replace the memory instance with a wrapped one, e.g. for tracing"""
        self.mem = mem

    def set_cycles_per_run(self, num):
        self.cycles_per_run = num

    def set_instr_hook(self, func):
        self.cpu.set_instr_hook_callback(func)

    def show_instr(self, show_regs=False):
        if show_regs:
            state = CPUState()

            def instr_hook():
                state.get(self.cpu)
                res = state.dump()
                for r in res:
                    log_machine.info(r)
                pc = self.cpu.r_pc()
                _, txt = self.cpu.disassemble(pc)
                log_machine.info("%06x: %s", pc, txt)

        else:

            def instr_hook():
                pc = self.cpu.r_pc()
                _, txt = self.cpu.disassemble(pc)
                log_machine.info("%06x: %s", pc, txt)

        self.set_instr_hook(instr_hook)

    def hide_instr(self):
        self.set_instr_hook(None)

    def set_cpu_mem_trace_hook(self, func):
        self.mem.set_trace_mode(1)
        self.mem.set_trace_func(func)

    def get_cur_run_state(self):
        assert len(self.run_states) > 0
        return self.run_states[-1]

    def _run_exit_handler(self, opcode, pc):
        """regular end of a machine run"""
        sp = self.cpu.r_reg(REG_A7)
        callee_pc = self.mem.r32(sp)
        log_machine.debug(
            "run exit: opcode=%04x, pc=%06x, sp=%06x, callee=%06x",
            opcode,
            pc,
            sp,
            callee_pc,
        )
        run_state = self.get_cur_run_state()
        run_state.done = True
        self.cpu.end()

    def _terminate_run(self, error):
        """end a machine run with error state"""
        run_state = self.get_cur_run_state()
        # already a pending error?
        if run_state.error:
            return
        run_state.error = error
        run_state.done = True
        # end time slice of cpu
        self.cpu.end()
        # report error
        self.error_reporter.report_error(run_state.error)

    def _invalid_mem_access(self, mode, width, addr):
        """triggered by invalid memory access"""
        log_machine.debug(
            "invalid memory access: mode=%s width=%d addr=%06x", mode, width, addr
        )
        error = InvalidMemoryAccessError(mode, width, addr)
        self._terminate_run(error)

    def _trap_exc_handler(self, op, pc):
        """triggerd if Python code in a trap raised a Python exception"""
        log_machine.debug("trap exception handler: op=%04x pc=%06x", op, pc)
        # get pending exception
        exc_info = sys.exc_info()
        if exc_info:
            error = exc_info[1]
        else:
            error = RuntimeError("No exception?!")
        self._terminate_run(error)

    def _hw_exc_handler(self, opcode, pc):
        """an m68k Hardware Exception was triggered"""
        # get current pc
        sp = self.cpu.r_reg(REG_A7)
        callee_pc = self.mem.r32(sp)
        log_machine.debug(
            "hw exception: pc=%06x sp=%06x callee=%06x", pc, sp, callee_pc
        )
        # m68k Exception Triggered
        sr = self.mem.r16(sp)
        pc = self.mem.r32(sp + 2)
        txt = "m68k Exception: sr=%04x" % sr
        error = InvalidCPUStateError(pc, txt)
        self._terminate_run(error)

    def _reset_opcode_handler(self):
        """a reset opcode was encountered"""
        pc = self.cpu.r_pc() - 2
        txt = "Unexpected RESET opcode"
        error = InvalidCPUStateError(pc, txt)
        self._terminate_run(error)

    def get_run_nesting(self):
        return len(self.run_states)

    def run(
        self,
        pc,
        sp=None,
        set_regs=None,
        get_regs=None,
        max_cycles=0,
        cycles_per_run=0,
        name=None,
    ):
        mem = self.mem
        cpu = self.cpu

        if name is None:
            name = "default"

        # current run nesting level
        nesting = len(self.run_states)

        # return address of a run is always run_end_addr
        ret_addr = self.run_exit_addr

        # get cpu context
        if nesting > 0:
            cpu_ctx = cpu.get_cpu_context()
        else:
            cpu_ctx = None

        # share stack with last run if not specified
        if sp is None:
            if nesting == 0:
                raise ValueError("stack must be specified!")
            else:
                sp = cpu.r_reg(REG_A7)
                sp -= 4

        log_machine.info(
            "run#%d(%s): begin pc=%06x, sp=%06x, ret_addr=%06x",
            nesting,
            name,
            pc,
            sp,
            ret_addr,
        )

        # store return address on stack
        mem.w32(sp, ret_addr)

        # setup pc, sp
        cpu.w_pc(pc)
        cpu.w_reg(REG_A7, sp)

        # create run state for this run and push it
        run_state = RunState(name, pc, sp, ret_addr)
        self.run_states.append(run_state)

        # setup regs
        if set_regs:
            set_regs_txt = self._print_regs(set_regs)
            log_machine.info("run#%d: set_regs=%s", nesting, set_regs_txt)
            for reg in set_regs:
                val = set_regs[reg]
                cpu.w_reg(reg, val)

        # get cycle params either from this call or from default
        if not cycles_per_run:
            cycles_per_run = self.cycles_per_run
        if not max_cycles:
            max_cycles = self.max_cycles

        # main execution loop of run
        total_cycles = 0
        start_time = time.perf_counter()
        try:
            while not run_state.done:
                log_machine.debug("+ cpu.execute")
                total_cycles += cpu.execute(cycles_per_run)
                log_machine.debug("- cpu.execute")
                # end after enough cycles
                if max_cycles > 0 and total_cycles >= max_cycles:
                    break
        except Exception as e:
            self.error_reporter.report_error(e)
        end_time = time.perf_counter()

        # retrieve regs
        if get_regs:
            regs = {}
            for reg in get_regs:
                val = cpu.r_reg(reg)
                regs[reg] = val
            regs_text = self._print_regs(regs)
            log_machine.info("run #%d: get_regs=%s", nesting, regs_text)
            run_state.regs = regs

        # restore cpu context
        if cpu_ctx:
            cpu.set_cpu_context(cpu_ctx)

        # update run state
        run_state.time_delta = end_time - start_time
        run_state.cycles = total_cycles
        # pop
        self.run_states.pop()

        log_machine.info("run #%d(%s): end. state=%s", nesting, name, run_state)

        # if run_state has error and we are not a top-level raise an error
        # so the running trap code gets aborted and propagates the abort
        if run_state.error:
            if nesting > 0 or self.raise_on_main_run:
                pc = cpu.r_pc()
                raise NestedCPURunError(pc, run_state.error)

        return run_state

    def _print_regs(self, regs):
        res = {}
        for r in regs:
            v = regs[r]
            key = reg_to_str[r]
            val = "%06x" % v
            res[key] = val
        return res
