import pytest
from amitools.vamos.astructs.scalar import ULONG, LONG, UWORD, WORD, UBYTE, BYTE
from amitools.vamos.machine.mock import MockMemory, MockCPU
from amitools.vamos.machine import REG_D0

cpu = MockCPU()
mem = MockMemory()


def astructs_scalar_mem_test():
    # unsigned
    mem.w32(8, 1234)
    obj = ULONG(mem=mem, addr=8)
    assert obj.get() == 1234
    obj.set(5432)
    assert mem.r32(8) == 5432
    # signed
    mem.w32s(16, -2233)
    obj = LONG(mem=mem, addr=16)
    assert obj.get() == -2233
    obj.set(-3322)
    assert mem.r32s(16) == -3322
    # test val access
    obj.val = 42
    assert obj.val == 42
    # invalid .aptr or .bptr access
    with pytest.raises(AttributeError):
        obj.aptr = 42
    with pytest.raises(AttributeError):
        obj.bptr = 42


def astructs_scalar_reg_test():
    # unsigned
    cpu.w_reg(REG_D0, 42)
    obj = ULONG(reg=REG_D0, cpu=cpu)
    assert obj.get() == 42
    obj.set(112)
    assert cpu.r_reg(REG_D0) == 112
    # signed
    cpu.ws_reg(REG_D0, -23)
    obj = LONG(reg=REG_D0, cpu=cpu)
    assert obj.get() == -23
    obj.set(-112)
    assert cpu.rs_reg(REG_D0) == -112


def astructs_scalar_ulong_test():
    assert ULONG.get_byte_size() == 4
    assert ULONG.get_mem_width() == 2
    assert not ULONG.is_signed()
    mem.w32(0, 10)
    obj = ULONG(mem=mem, addr=0)
    assert obj.get() == 10
    assert repr(obj) == "ULONG(value=10, addr=0)"
    assert obj.get_signature() == "ULONG"
    # cpu reg test
    cpu.w_reg(REG_D0, 0xCAFEBABE)
    obj = ULONG(reg=REG_D0, cpu=cpu)
    assert obj.val == 0xCAFEBABE


def astructs_scalar_long_test():
    assert LONG.get_byte_size() == 4
    assert LONG.get_mem_width() == 2
    assert LONG.is_signed()
    mem.w32s(0, -10)
    obj = LONG(mem=mem, addr=0)
    assert repr(obj) == "LONG(value=-10, addr=0)"
    assert obj.get_signature() == "LONG"
    # cpu reg test
    cpu.ws_reg(REG_D0, -21)
    obj = LONG(reg=REG_D0, cpu=cpu)
    assert obj.val == -21
    # real long signed
    cpu.w_reg(REG_D0, 0xFFFFFFFF)
    obj = LONG(reg=REG_D0, cpu=cpu)
    assert obj.val == -1


def astructs_scalar_uword_test():
    assert UWORD.get_byte_size() == 2
    assert UWORD.get_mem_width() == 1
    assert not UWORD.is_signed()
    mem.w16(0, 10)
    obj = UWORD(mem=mem, addr=0)
    assert repr(obj) == "UWORD(value=10, addr=0)"
    assert obj.get_signature() == "UWORD"
    # cpu reg test
    cpu.w_reg(REG_D0, 0xBABE)
    w = UWORD(reg=REG_D0, cpu=cpu)
    assert w.val == 0xBABE
    # only word value
    cpu.w_reg(REG_D0, 0xFFBABE)
    w = UWORD(reg=REG_D0, cpu=cpu)
    assert w.val == 0xBABE


def astructs_scalar_word_test():
    assert WORD.get_byte_size() == 2
    assert WORD.get_mem_width() == 1
    assert WORD.is_signed()
    mem.w16s(0, -10)
    obj = WORD(mem=mem, addr=0)
    assert repr(obj) == "WORD(value=-10, addr=0)"
    assert obj.get_signature() == "WORD"
    # cpu reg test
    cpu.ws_reg(REG_D0, -21)
    w = WORD(reg=REG_D0, cpu=cpu)
    assert w.val == -21
    # real word signed
    cpu.w_reg(REG_D0, 0xFFFF)
    w = WORD(reg=REG_D0, cpu=cpu)
    assert w.val == -1
    # extended signed
    cpu.w_reg(REG_D0, 0xFFFFFF)
    w = WORD(reg=REG_D0, cpu=cpu)
    assert w.val == -1


def astructs_scalar_ubyte_test():
    assert UBYTE.get_byte_size() == 1
    assert UBYTE.get_mem_width() == 0
    assert not UBYTE.is_signed()
    mem.w8(0, 10)
    obj = UBYTE(mem=mem, addr=0)
    assert repr(obj) == "UBYTE(value=10, addr=0)"
    assert obj.get_signature() == "UBYTE"
    # cpu reg test
    cpu.w_reg(REG_D0, 0xBA)
    b = UBYTE(reg=REG_D0, cpu=cpu)
    assert b.val == 0xBA
    # only byte value
    cpu.w_reg(REG_D0, 0xFFBA)
    b = UBYTE(reg=REG_D0, cpu=cpu)
    assert b.val == 0xBA


def astructs_scalar_byte_test():
    assert BYTE.get_byte_size() == 1
    assert BYTE.get_mem_width() == 0
    assert BYTE.is_signed()
    mem.w8s(0, -10)
    obj = BYTE(mem=mem, addr=0)
    assert repr(obj) == "BYTE(value=-10, addr=0)"
    assert obj.get_signature() == "BYTE"
    # cpu reg test
    cpu.ws_reg(REG_D0, -21)
    b = BYTE(reg=REG_D0, cpu=cpu)
    assert b.val == -21
    # real byte signed
    cpu.w_reg(REG_D0, 0xFF)
    b = BYTE(reg=REG_D0, cpu=cpu)
    assert b.val == -1
    # extended signed
    cpu.w_reg(REG_D0, 0xFFFF)
    b = BYTE(reg=REG_D0, cpu=cpu)
    assert b.val == -1
