from enum import Enum
from dataclasses import dataclass
from typing import Optional
import sys
import logging

try:
    import machine68k
except ImportError:
    logging.error("package 'machine68k' missing! please install with pip.")
    sys.exit(1)

from .regs import *
from .opcodes import *
from .cpustate import CPUState
from .traps import Traps, TrapCall
from .error import InvalidMemoryAccessError, CPUHWExceptionError, ResetOpcodeError
from amitools.vamos.log import log_machine
from amitools.vamos.label import LabelManager


class ExecutionStatus(Enum):
    EXIT_CODE = 0
    MAX_CYCLES = 1
    TRAP = 2
    ERROR = 3


@dataclass
class ExecutionResult:
    status: ExecutionStatus
    trap: Optional[TrapCall] = None
    error: Optional[Exception] = None
    cycles: int = 0


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

    run_exit_addr = 0x400
    hw_exc_addr = 0x402
    ram_begin = 0x800
    scratch_begin = 0x600
    quick_trap_begin = 0x500
    quick_trap_num = 64

    def __init__(
        self,
        cpu_type=machine68k.CPUType.M68000,
        ram_size_kib=1024,
        use_labels=True,
        supervisor=False,
    ):
        self.cpu_type = cpu_type
        self.cpu_name = machine68k.cpu_type_to_str(cpu_type)
        # setup machine68k
        self.machine = machine68k.Machine(cpu_type, ram_size_kib)
        self.cpu = self.machine.cpu
        self.mem = self.machine.mem
        # ram
        self.ram_total = ram_size_kib * 1024
        self.ram_bytes = self.ram_total - self.ram_begin
        # start as supervisor
        self.supervisor = supervisor

        # execute state
        self.result = None

        # traps
        def store_trap_call(call):
            self.result = ExecutionResult(ExecutionStatus.TRAP, trap=call)

        self.traps = Traps(self.machine, store_trap_call)

        # labels
        if use_labels:
            self.label_mgr = LabelManager()
        else:
            self.label_mgr = None
        # hooks
        self.instr_hook = None
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
        cpu_str = machine_cfg.cpu
        ram_size = machine_cfg.ram_size
        return cls.from_name(cpu_str, ram_size, use_labels)

    @classmethod
    def from_name(cls, cpu_str, ram_size=1024, use_labels=False):
        cpu_type = machine68k.cpu_type_from_str(cpu_str)
        if cpu_type is None:
            log_machine.error("invalid CPU type given: %s", cpu)
            return None
        log_machine.info(
            "cpu=%s(%s), ram_size=%d, labels=%s",
            cpu_type,
            cpu_str,
            ram_size,
            use_labels,
        )
        return cls(
            cpu_type,
            ram_size,
            use_labels=use_labels,
        )

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
        if not self.supervisor:
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
        # "reset" opcode handler
        self.cpu.set_reset_instr_callback(self._reset_opcode_handler)
        # set invalid access handler for memory
        self.mem.set_invalid_func(self._invalid_mem_access)
        # allocate a trap for exit_run and hw_exception
        self.run_exit_tid = self.machine.traps.setup(self._exit_code_handler)
        self.hw_exc_tid = self.machine.traps.setup(self._hw_exc_handler)

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
                tid = self.traps.setup(func)
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

    def get_sp(self):
        return self.cpu.r_reg(REG_A7)

    def get_pc(self):
        return self.cpu.r_pc()

    def set_mem(self, mem):
        """replace the memory instance with a wrapped one, e.g. for tracing"""
        self.mem = mem

    def set_instr_hook(self, func):
        self.cpu.set_instr_hook_callback(func)

    def set_cpu_mem_trace_hook(self, func):
        if func:
            self.mem.set_trace_mode(1)
            self.mem.set_trace_func(func)
        else:
            self.mem.set_trace_mode(0)
            self.mem.set_trace_func(None)

    def _exit_code_handler(self, opcode, pc):
        """regular end of a machine run"""
        sp = self.cpu.r_reg(REG_A7)
        callee_pc = self.mem.r32(sp)
        log_machine.debug(
            "exit code: opcode=%04x, pc=%06x, sp=%06x, callee=%06x",
            opcode,
            pc,
            sp,
            callee_pc,
        )
        # ent time slice of cpu
        self.cpu.end()
        # set done flag
        self.result = ExecutionResult(ExecutionStatus.EXIT_CODE)

    def _terminate_run(self, error):
        """end a machine run with error state"""
        # end time slice of cpu
        self.cpu.end()
        # store error
        self.result = ExecutionResult(ExecutionStatus.ERROR, error=error)

    def _invalid_mem_access(self, mode, width, addr):
        """triggered by invalid memory access"""
        log_machine.error(
            "invalid memory access: mode=%s width=%d addr=%06x", mode, width, addr
        )
        pc = self.get_pc()
        sp = self.get_sp()
        error = InvalidMemoryAccessError(pc, sp, mode, width, addr)
        self._terminate_run(error)

    def _trap_exc_handler(self, op, pc):
        """triggerd if Python code in a trap raised a Python exception"""
        log_machine.error("Python exception in trap: op=%04x pc=%06x", op, pc)
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
        sp = self.get_sp()
        # m68k Exception Triggered
        sr = self.mem.r16(sp)
        pc = self.mem.r32(sp + 2)
        log_machine.debug("HW exception: pc=%06x sp=%06x sr=%04x", pc, sp, sr)
        error = CPUHWExceptionError(pc, sp, sr)
        self._terminate_run(error)

    def _reset_opcode_handler(self):
        """a reset opcode was encountered"""
        pc = self.cpu.r_pc() - 2
        sp = self.get_sp()
        log_machine.debug("RESET opcode: pc=%06x sp=%06x", pc, sp)
        error = ResetOpcodeError(pc, sp)
        self._terminate_run(error)

    def prepare(self, pc, sp):
        """set pc to start address and stack pointer and place end trap on stack"""
        self.cpu.w_pc(pc)
        self.cpu.w_reg(REG_A7, sp)
        # place end trap on stack
        sp = self.cpu.r_reg(REG_A7)
        ret_addr = self.run_exit_addr
        sp -= 4
        self.mem.w32(sp, ret_addr)
        self.cpu.w_reg(REG_A7, sp)

    def execute(self, max_cycles=1000) -> ExecutionResult:
        # reset result
        self.result = None

        # perform run
        log_machine.debug("+ cpu.execute. max_cycles=%d", max_cycles)
        cycles = self.cpu.execute(max_cycles)
        log_machine.debug("- cpu.execute. cycles=%d", cycles)

        # check result
        if not self.result:
            # cycles exceeded
            self.result = ExecutionResult(ExecutionStatus.MAX_CYCLES)

        # update cycles
        self.result.cycles = cycles

        # return result
        log_machine.debug("-> result=%r", self.result)
        return self.result
