import pytest
from amitools.vamos.machine.regs import *
from amitools.vamos.machine.mock import MockCPU


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


def machine_mockcpu_rw_partial_reg_test():
    cpu = MockCPU()
    cpu.w_reg(REG_D0, 0xCAFEBABE)
    # read partial
    assert cpu.r32_reg(REG_D0) == 0xCAFEBABE
    assert cpu.r16_reg(REG_D0) == 0xBABE
    assert cpu.r8_reg(REG_D0) == 0xBE
    # write partial
    cpu.w8_reg(REG_D0, 0xFE)
    assert cpu.r_reg(REG_D0) == 0xCAFEBAFE
    cpu.w16_reg(REG_D0, 0xF000)
    assert cpu.r_reg(REG_D0) == 0xCAFEF000
    cpu.w32_reg(REG_D0, 0xDEADBEEF)
    assert cpu.r_reg(REG_D0) == 0xDEADBEEF
    # write too large
    with pytest.raises(OverflowError):
        cpu.w8_reg(REG_D0, 0xF00)
    with pytest.raises(OverflowError):
        cpu.w16_reg(REG_D0, 0xF0000)
    with pytest.raises(OverflowError):
        cpu.w32_reg(REG_D0, 0xF00000000)


def machine_mockcpu_rws_partial_reg_test():
    cpu = MockCPU()
    cpu.w_reg(REG_D0, 0xF000F0F0)
    # read partial
    assert cpu.r32s_reg(REG_D0) == -268373776
    assert cpu.r16s_reg(REG_D0) == -3856
    assert cpu.r8s_reg(REG_D0) == -16
    # write partial
    cpu.w8s_reg(REG_D0, -1)
    assert cpu.r_reg(REG_D0) == 0xF000F0FF
    cpu.w16s_reg(REG_D0, -1)
    assert cpu.r_reg(REG_D0) == 0xF000FFFF
    cpu.w32s_reg(REG_D0, -1)
    assert cpu.r_reg(REG_D0) == 0xFFFFFFFF
    # write too large
    with pytest.raises(OverflowError):
        cpu.w8s_reg(REG_D0, 0x80)
    with pytest.raises(OverflowError):
        cpu.w16s_reg(REG_D0, 0x8000)
    with pytest.raises(OverflowError):
        cpu.w32s_reg(REG_D0, 0x80000000)
