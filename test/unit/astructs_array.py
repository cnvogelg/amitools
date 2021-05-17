from amitools.vamos.astructs.typebase import TypeBase
from amitools.vamos.astructs.array import ARRAY, ArrayIter
from amitools.vamos.astructs.scalar import ULONG
from amitools.vamos.machine import MockMemory, MockCPU, REG_D0

cpu = MockCPU()
mem = MockMemory()


def astructs_array_test():
    ULONG_ARRAY = ARRAY(ULONG, 10)
    a = ULONG_ARRAY(mem, 0x40)
    assert a.get_array_size() == 10
    assert a.get_element_type() is ULONG
    assert a.get_byte_size() == 10 * 4
    e = a.get(0)
    assert type(e) is ULONG
    e.set(0xDEAD)
    assert mem.r32(0x40) == 0xDEAD
    e = a.get(9)
    e.set(0x1234)
    assert mem.r32(0x40 + 9 * 4) == 0x1234
    # signature
    assert a.get_signature() == "ULONG[10]"
    # access entry value
    a[0].val = 23
    assert a[0].val == 23
    assert a.get(0).val == 23


def astructs_array_iter_test():
    ULONG_ARRAY = ARRAY(ULONG, 10)
    a = ULONG_ARRAY(mem, 0x40)
    val = 1
    for e in ArrayIter(a):
        e.set(val)
        val += 1
    assert val == 11
    # check values
    addr = 0x40
    val = 1
    for i in range(10):
        v = mem.r32(addr)
        assert v == val
        addr += 4
        val += 1
