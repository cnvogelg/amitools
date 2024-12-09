import pytest
import struct
from amitools.vamos.machine.mock import MockMemory, MultiMockMemory


BASE_LIST = (0, 0x1000, 0x1234560)


@pytest.fixture(params=BASE_LIST)
def base(request):
    return request.param


@pytest.fixture(params=(0, 1))
def mem(request, base):
    variant = request.param
    if variant == 0:
        return MockMemory(base_addr=base)
    elif variant == 1:
        m = MockMemory(base_addr=base)
        mm = MultiMockMemory()
        mm.add(m)
        mm.base_addr = base
        return mm


def machine_mem_rw_test(mem):
    base = mem.base_addr

    mem.w8(0x100 + base, 42)
    assert mem.r8(0x100 + base) == 42

    mem.w16(0x200 + base, 0xDEAD)
    assert mem.r16(0x200 + base) == 0xDEAD

    mem.w32(0x300 + base, 0xCAFEBABE)
    assert mem.r32(0x300 + base) == 0xCAFEBABE

    mem.write(0, 0x101 + base, 43)
    assert mem.read(0, 0x101 + base) == 43

    mem.write(1, 0x202 + base, 0x1234)
    assert mem.read(1, 0x202 + base) == 0x1234

    mem.write(2, 0x304 + base, 0x11223344)
    assert mem.read(2, 0x304 + base) == 0x11223344

    # invalid values
    with pytest.raises(ValueError):
        mem.w8(0x100 + base, 0x100)
    with pytest.raises(ValueError):
        mem.w8(0x100 + base, -1)
    # invalid values
    with pytest.raises(struct.error):
        mem.w16(0x100 + base, 0x10000)
    with pytest.raises(struct.error):
        mem.w16(0x100 + base, -2)
    # invalid values
    with pytest.raises(struct.error):
        mem.w32(0x100 + base, 0x100000000)
    with pytest.raises(struct.error):
        mem.w32(0x100 + base, -3)
    # invalid type
    with pytest.raises(TypeError):
        mem.w8(0x100 + base, "hello")
    # invalid type
    with pytest.raises(struct.error):
        mem.w16(0x100 + base, "hello")
    # invalid type
    with pytest.raises(struct.error):
        mem.w32(0x100 + base, "hello")
    # invalid width
    with pytest.raises(ValueError):
        mem.write(7, 0x202 + base, 12)
    with pytest.raises(ValueError):
        mem.read(7, 0x202 + base)


def machine_mem_rws_test(mem):
    base = mem.base_addr

    mem.w8s(0x100 + base, 42)
    assert mem.r8s(0x100 + base) == 42
    mem.w8s(0x100 + base, -23)
    assert mem.r8s(0x100 + base) == -23

    mem.w16s(0x200 + base, 0x7EAD)
    assert mem.r16s(0x200 + base) == 0x7EAD
    mem.w16s(0x200 + base, -0x1000)
    assert mem.r16s(0x200 + base) == -0x1000

    mem.w32s(0x300 + base, 0x1AFEBABE)
    assert mem.r32s(0x300 + base) == 0x1AFEBABE
    mem.w32s(0x300 + base, -0xAFEBABE)
    assert mem.r32s(0x300 + base) == -0xAFEBABE

    mem.writes(0, 0x101 + base, -43)
    assert mem.reads(0, 0x101 + base) == -43
    mem.writes(1, 0x202 + base, -0x1234)
    assert mem.reads(1, 0x202 + base) == -0x1234
    mem.writes(2, 0x304 + base, -0x11223344)
    assert mem.reads(2, 0x304 + base) == -0x11223344

    # invalid values
    with pytest.raises(struct.error):
        mem.w8s(0x100 + base, 0x80)
    with pytest.raises(struct.error):
        mem.w8s(0x100 + base, -0x81)
    # invalid values
    with pytest.raises(struct.error):
        mem.w16s(0x100 + base, 0x8000)
    with pytest.raises(struct.error):
        mem.w16s(0x100 + base, -0x8001)
    # invalid values
    with pytest.raises(struct.error):
        mem.w32s(0x100 + base, 0x80000000)
    with pytest.raises(struct.error):
        mem.w32s(0x100 + base, -0x80000001)
    # invalid type
    with pytest.raises(struct.error):
        mem.w8s(0x100 + base, "hello")
    # invalid type
    with pytest.raises(struct.error):
        mem.w16s(0x100 + base, "hello")
    # invalid type
    with pytest.raises(struct.error):
        mem.w32s(0x100 + base, "hello")
    # invalid width
    with pytest.raises(ValueError):
        mem.writes(7, 0x202 + base, 12)
    with pytest.raises(ValueError):
        mem.reads(7, 0x202 + base)


def machine_mem_block_test(mem):
    base = mem.base_addr

    data = b"hello, world!"
    mem.w_block(base, data)
    assert mem.r_block(base, len(data)) == data
    bdata = bytearray(data)
    mem.w_block(0x100 + base, bdata)
    assert mem.r_block(0x100 + base, len(bdata)) == bdata
    mem.clear_block(0x200 + base, 100, 42)
    assert mem.r_block(0x200 + base, 100) == bytes([42] * 100)
    mem.copy_block(0x200 + base, 0x300 + base, 20)
    assert mem.r_block(0x300 + base, 21) == bytes([42] * 20) + b"\0"


def machine_mem_cstr_test(mem):
    base = mem.base_addr

    data = "hello, world"
    mem.w_cstr(base, data)
    assert mem.r_cstr(base) == data
    empty = ""
    mem.w_cstr(100 + base, empty)
    assert mem.r_cstr(100 + base) == empty


def machine_mem_bstr_test(mem):
    base = mem.base_addr

    data = "hello, world"
    mem.w_bstr(base, data)
    assert mem.r_bstr(base) == data
    empty = ""
    mem.w_bstr(100 + base, empty)
    assert mem.r_bstr(100 + base) == empty


def machine_mem_rom_test(base):
    mem = MockMemory(read_only=True, base_addr=base)

    with pytest.raises(ValueError):
        mem.w8(0x100 + base, 42)
    with pytest.raises(ValueError):
        mem.w16(0x200 + base, 0xDEAD)
    with pytest.raises(ValueError):
        mem.w32(0x300 + base, 0xCAFEBABE)
    with pytest.raises(ValueError):
        mem.write(0, 0x101 + base, 43)

    with pytest.raises(ValueError):
        mem.w8s(0x100 + base, 42)
    with pytest.raises(ValueError):
        mem.w16s(0x200 + base, 0x7EAD)
    with pytest.raises(ValueError):
        mem.w32s(0x300 + base, 0x1AFEBABE)
    with pytest.raises(ValueError):
        mem.writes(0, 0x101 + base, -43)

    with pytest.raises(ValueError):
        data = b"hello"
        mem.w_block(base, data)
    with pytest.raises(ValueError):
        mem.clear_block(0x200 + base, 100, 42)
    with pytest.raises(ValueError):
        mem.copy_block(0x200 + base, 0x300, 20)

    data = "hello, world"
    with pytest.raises(ValueError):
        mem.w_cstr(base, data)
    with pytest.raises(ValueError):
        mem.w_bstr(base, data)
