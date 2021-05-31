from amitools.vamos.astructs.typebase import TypeBase
from amitools.vamos.astructs.string import CSTR, BSTR, CStringType, BStringType
from amitools.vamos.machine import MockMemory, MockCPU, REG_D0
from amitools.vamos.mem import MemoryAlloc

cpu = MockCPU()
mem = MockMemory()
alloc = MemoryAlloc(mem)


def astructs_string_cstr_test():
    # prepare mem
    txt = "hello, world!"
    mem.w32(0x20, 0x40)
    mem.w_cstr(0x40, txt)
    # now access with cstr
    cstr = CSTR(mem=mem, addr=0x20)
    assert cstr.get_signature() == "CSTR"
    val = cstr.get_str()
    assert val == txt
    assert str(cstr) == txt
    # modify cstr
    txt2 = "wow, str!"
    cstr.set_str(txt2)
    val = mem.r_cstr(0x40)
    assert val == txt2
    assert str(cstr) == txt2
    # modify ptr
    mem.w_cstr(0x80, txt)
    cstr.set(0x80)
    assert cstr.get_str() == txt
    assert str(cstr) == txt
    # access via 'str'
    cstr.str = "now!"
    assert cstr.str == "now!"


def astructs_string_cstr_reg_test():
    txt = "hello, world!"
    mem.w_cstr(0x40, txt)
    cpu.w_reg(REG_D0, 0x40)
    cstr = CSTR(cpu=cpu, reg=REG_D0, mem=mem)
    assert cstr.str == txt


def astructs_string_cstr_null_test():
    mem.w32(0, 0)
    cstr = CSTR(mem=mem, addr=0)
    assert cstr.str is None
    assert str(cstr) == "None"
    mem.w32(4, 0)
    cstr2 = CSTR(mem=mem, addr=4)
    assert cstr2.str is None
    assert str(cstr2) == "None"
    assert cstr != cstr2


def astructs_string_cstr_compare_test():
    txt = "hello, world!"
    mem.w32(0x20, 0x40)
    mem.w_cstr(0x40, txt)
    cstr = CSTR(mem=mem, addr=0x20)
    assert cstr == 0x20
    assert cstr.aptr == 0x40
    assert cstr.str == txt
    cstr2 = CSTR(mem=mem, addr=0x20)
    assert cstr == cstr2
    cstr3 = CSTR(mem=mem, addr=0x24)
    assert cstr != cstr3


def astructs_string_cstr_alloc_test():
    mem.w32(0x20, 0)
    cstr = CSTR(mem=mem, addr=0x20)
    assert cstr.str is None
    assert cstr.aptr == 0
    txt = "hello, world!"
    res = cstr.alloc_str(alloc, txt)
    assert res is not None
    assert type(res) is CStringType
    assert cstr.str == txt
    assert cstr.aptr != 0
    assert mem.r_cstr(cstr.aptr) == txt
    cstr.free_str()
    assert cstr.str is None
    assert cstr.aptr == 0
    assert alloc.is_all_free()


def astructs_string_bstr_test():
    # prepare mem
    txt = "hello, world!"
    mem.w32(0x20, 0x10)  # baddr for 0x40
    mem.w_bstr(0x40, txt)
    # now access with cstr
    bstr = BSTR(mem=mem, addr=0x20)
    assert bstr.get_signature() == "BSTR"
    val = bstr.get_str()
    assert val == txt
    assert str(bstr) == txt
    # modify cstr
    txt2 = "wow, str!"
    bstr.set_str(txt2)
    val = mem.r_bstr(0x40)
    assert val == txt2
    assert str(bstr) == txt2
    # modify ptr
    mem.w_bstr(0x80, txt)
    bstr.set(0x20)  # 0x20 is baddr of 0x80
    assert bstr.get_str() == txt
    assert str(bstr) == txt
    # access via 'str'
    bstr.str = "now!"
    assert bstr.str == "now!"


def astructs_string_cstr_reg_test():
    txt = "hello, world!"
    mem.w_bstr(0x40, txt)
    cpu.w_reg(REG_D0, 0x10)  # BADDR
    bstr = BSTR(cpu=cpu, reg=REG_D0, mem=mem)
    assert bstr.str == txt


def astructs_string_bstr_null_test():
    mem.w32(0, 0)
    bstr = BSTR(mem=mem, addr=0)
    assert bstr.str is None
    assert str(bstr) == "None"
    mem.w32(4, 0)
    bstr2 = BSTR(mem=mem, addr=4)
    assert bstr2.str is None
    assert str(bstr2) == "None"
    assert bstr != bstr2


def astructs_string_cstr_compare_test():
    txt = "hello, world!"
    mem.w32(0x20, 0x10)
    mem.w_bstr(0x40, txt)
    bstr = BSTR(mem=mem, addr=0x20)
    assert bstr == 0x20
    assert bstr.aptr == 0x40
    assert bstr.bptr == 0x10
    assert bstr.str == txt
    bstr2 = BSTR(mem=mem, addr=0x20)
    assert bstr == bstr2
    cstr3 = BSTR(mem=mem, addr=0x24)
    assert bstr != cstr3


def astructs_string_bstr_alloc_test():
    mem.w32(0x20, 0)
    bstr = BSTR(mem=mem, addr=0x20)
    assert bstr.str is None
    assert bstr.aptr == 0
    txt = "hello, world!"
    res = bstr.alloc_str(alloc, txt)
    assert res is not None
    assert type(res) is BStringType
    assert bstr.str == txt
    assert bstr.aptr != 0
    assert mem.r_bstr(bstr.aptr) == txt
    bstr.free_str()
    assert bstr.str is None
    assert bstr.aptr == 0
    assert alloc.is_all_free()
