import pytest
from machine import emu
from machine.m68k import *
from amitools.vamos.machine import *


def machine_emu_cpustate_rw_test():
    cpu = emu.CPU(M68K_CPU_TYPE_68000)
    cpu.w_pc(0)
    cpu.w_sr(0x2700)
    for i in range(16):
        cpu.w_reg(i, i)
    # get state
    s = CPUState()
    s.get(cpu)
    assert s.pc == 0
    assert s.sr == 0x2700
    for i in range(8):
        assert s.dx[i] == i
    for i in range(8):
        assert s.ax[i] == i + 8
    # modify state
    for i in range(8):
        s.dx[i] = i + 0x100
        s.ax[i] = i + 0x200
    s.pc = 0x400
    s.sr = 0x2701
    # set state
    s.set(cpu)
    # check state
    assert cpu.r_sr() == s.sr
    assert cpu.r_pc() == s.pc
    for i in range(8):
        assert s.dx[i] == cpu.r_reg(i)
    for i in range(8):
        assert s.ax[i] == cpu.r_reg(i + 8)
