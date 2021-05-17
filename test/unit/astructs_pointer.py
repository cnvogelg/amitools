import pytest
from amitools.vamos.astructs.typebase import TypeBase
from amitools.vamos.astructs.pointer import (
    PointerType,
    BCPLPointerType,
    APTR,
    BPTR,
    VOID,
    APTR_VOID,
    BPTR_VOID,
)
from amitools.vamos.machine import MockMemory, MockCPU, REG_D0
from amitools.vamos.mem import MemoryAlloc

cpu = MockCPU()
mem = MockMemory()
alloc = MemoryAlloc(mem)


def astructs_pointer_aptr_void_test():
    assert PointerType.get_byte_size() == 4
    void_ptr = APTR_VOID(mem=mem, addr=0x40)
    mem.w32(0x40, 0x80)
    ref = void_ptr.ref
    assert type(ref) is VOID
    assert ref.get_addr() == 0x80
    assert void_ptr.get_ref_addr() == 0x80
    assert int(void_ptr) == 0x80
    # change pointer
    void_ptr.set_ref_addr(0x100)
    assert void_ptr.get_ref_addr() == 0x100
    assert int(void_ptr) == 0x100
    new_ref = void_ptr.ref
    assert type(new_ref) is VOID
    assert new_ref.get_addr() == 0x100
    assert mem.r32(0x40) == 0x100
    # signature
    assert void_ptr.get_signature() == "VOID*"
    # check 'aptr'
    void_ptr.aptr = 0x200
    assert void_ptr.aptr == 0x200
    # invalid .val access
    with pytest.raises(AttributeError):
        void_ptr.val = 12


def astructs_pointer_aptr_null_test():
    null_ptr = APTR_VOID(mem=mem, addr=0x40)
    mem.w32(0x40, 0)
    assert null_ptr.ref is None
    assert int(null_ptr) == 0
    assert null_ptr.get_ref_addr() == 0


def astructs_pointer_bptr_void_test():
    assert BCPLPointerType.get_byte_size() == 4
    void_ptr = BPTR_VOID(mem=mem, addr=0x40)
    mem.w32(0x40, 0x20)  # 0x20 = BCPL addr of 0x80
    ref = void_ptr.ref
    assert type(ref) is VOID
    assert ref.get_addr() == 0x80
    assert void_ptr.get_ref_addr() == 0x80
    # int conversion is BPTR!
    assert int(void_ptr) == 0x20
    # change pointer
    void_ptr.set_ref_addr(0x100)
    assert void_ptr.get_ref_addr() == 0x100
    new_ref = void_ptr.ref
    assert type(new_ref) is VOID
    assert new_ref.get_addr() == 0x100
    # int conversion is BPTR!
    assert int(void_ptr) == 0x40
    assert mem.r32(0x40) == 0x40  # 0x40 = BCPL addr of 0x100
    # change pointer by baddr
    void_ptr.set_ref_baddr(0x200)
    assert void_ptr.get_ref_addr() == 0x200 << 2
    assert void_ptr.get_ref_baddr() == 0x200
    assert mem.r32(0x40) == 0x200
    # signature
    assert void_ptr.get_signature() == "VOID#"
    # check 'aptr'
    void_ptr.aptr = 0x400
    assert void_ptr.aptr == 0x400
    assert void_ptr.get() == 0x100
    void_ptr.bptr = 0x200
    assert void_ptr.bptr == 0x200
    assert void_ptr.get() == 0x200
    # invalid .val access
    with pytest.raises(AttributeError):
        void_ptr.val = 12


def astructs_pointer_bptr_null_test():
    null_ptr = BPTR_VOID(mem=mem, addr=0x40)
    mem.w32(0x40, 0)
    assert null_ptr.ref is None
    assert int(null_ptr) == 0
    assert null_ptr.get_ref_addr() == 0
