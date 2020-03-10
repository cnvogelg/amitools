import pytest
from amitools.vamos.machine.regs import *
from amitools.vamos.machine import MockCPU


def machine_mockcpu_rw_reg_test():
    cpu = MockCPU()
    cpu.w_reg(REG_D0, 0xDEADBEEF)
    assert cpu.r_reg(REG_D0) == 0xDEADBEEF
    cpu.w_reg(REG_A6, 0xCAFEBABE)
    assert cpu.r_reg(REG_A6) == 0xCAFEBABE
    cpu.w_pc(0x123456)
    assert cpu.r_pc() == 0x123456
    cpu.w_sr(0x4711)
    assert cpu.r_sr() == 0x4711
    # invalid values
    with pytest.raises(OverflowError):
        cpu.w_reg(REG_D0, 0xDEAFBEEF12)
    with pytest.raises(OverflowError):
        cpu.w_reg(REG_D0, -1)
    with pytest.raises(TypeError):
        cpu.w_reg(REG_D0, "hello, world!")


def machine_mockcpu_rws_reg_test():
    cpu = MockCPU()
    cpu.ws_reg(REG_D0, -23)
    assert cpu.rs_reg(REG_D0) == -23
    # invalid values
    with pytest.raises(OverflowError):
        cpu.ws_reg(REG_D0, 0x80000000)
    with pytest.raises(OverflowError):
        cpu.ws_reg(REG_D0, -0x80000001)
    with pytest.raises(TypeError):
        cpu.ws_reg(REG_D0, "hello, world!")
