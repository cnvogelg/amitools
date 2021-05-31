import pytest
from amitools.vamos.astructs.typebase import TypeBase
from amitools.vamos.astructs.scalar import ULONG, LONG, UWORD, WORD, UBYTE, BYTE
from amitools.vamos.machine import MockMemory, MockCPU, REG_D0

cpu = MockCPU()
mem = MockMemory()


def astructs_scalar_mem_test():
    # unsigned
    mem.w32(8, 1234)
    l = ULONG(mem=mem, addr=8)
    assert l.get() == 1234
    l.set(5432)
    assert mem.r32(8) == 5432
    # signed
    mem.w32s(16, -2233)
    l = LONG(mem=mem, addr=16)
    assert l.get() == -2233
    l.set(-3322)
    assert mem.r32s(16) == -3322
    # test val access
    l.val = 42
    assert l.val == 42
    # invalid .aptr or .bptr access
    with pytest.raises(AttributeError):
        l.aptr = 42
    with pytest.raises(AttributeError):
        l.bptr = 42


def astructs_scalar_reg_test():
    # unsigned
    cpu.w_reg(REG_D0, 42)
    l = ULONG(reg=REG_D0, cpu=cpu)
    assert l.get() == 42
    l.set(112)
    assert cpu.r_reg(REG_D0) == 112
    # signed
    cpu.ws_reg(REG_D0, -23)
    l = LONG(reg=REG_D0, cpu=cpu)
    assert l.get() == -23
    l.set(-112)
    assert cpu.rs_reg(REG_D0) == -112


def astructs_scalar_ulong_test():
    assert ULONG.get_byte_size() == 4
    assert ULONG.get_mem_width() == 2
    assert not ULONG.is_signed()
    mem.w32(0, 10)
    l = ULONG(mem=mem, addr=0)
    assert l.get() == 10
    assert repr(l) == "ULONG(value=10, addr=0)"
    assert l.get_signature() == "ULONG"


def astructs_scalar_long_test():
    assert LONG.get_byte_size() == 4
    assert LONG.get_mem_width() == 2
    assert LONG.is_signed()
    mem.w32s(0, -10)
    l = LONG(mem=mem, addr=0)
    assert repr(l) == "LONG(value=-10, addr=0)"
    assert l.get_signature() == "LONG"


def astructs_scalar_uword_test():
    assert UWORD.get_byte_size() == 2
    assert UWORD.get_mem_width() == 1
    assert not UWORD.is_signed()
    mem.w16(0, 10)
    l = UWORD(mem=mem, addr=0)
    assert repr(l) == "UWORD(value=10, addr=0)"
    assert l.get_signature() == "UWORD"


def astructs_scalar_word_test():
    assert WORD.get_byte_size() == 2
    assert WORD.get_mem_width() == 1
    assert WORD.is_signed()
    mem.w16s(0, -10)
    l = WORD(mem=mem, addr=0)
    assert repr(l) == "WORD(value=-10, addr=0)"
    assert l.get_signature() == "WORD"


def astructs_scalar_ubyte_test():
    assert UBYTE.get_byte_size() == 1
    assert UBYTE.get_mem_width() == 0
    assert not UBYTE.is_signed()
    mem.w8(0, 10)
    l = UBYTE(mem=mem, addr=0)
    assert repr(l) == "UBYTE(value=10, addr=0)"
    assert l.get_signature() == "UBYTE"


def astructs_scalar_byte_test():
    assert BYTE.get_byte_size() == 1
    assert BYTE.get_mem_width() == 0
    assert BYTE.is_signed()
    mem.w8s(0, -10)
    l = BYTE(mem=mem, addr=0)
    assert repr(l) == "BYTE(value=-10, addr=0)"
    assert l.get_signature() == "BYTE"
