import pytest
from amitools.vamos.astructs import (
    AccessStruct,
    AmigaStruct,
    AmigaStructDef,
    APTR_SELF,
    APTR,
    APTR_VOID,
    UBYTE,
    BYTE,
    CSTR,
    BPTR_VOID,
)
from amitools.vamos.machine import MockMemory


@AmigaStructDef
class MyNodeStruct(AmigaStruct):
    _format = [
        (APTR_SELF, "ln_Succ"),
        (APTR_SELF, "ln_Pred"),
        (UBYTE, "ln_Type"),
        (BYTE, "ln_Pri"),
        (CSTR, "ln_Name"),
    ]


# Task
@AmigaStructDef
class MyTaskStruct(AmigaStruct):
    _format = [
        (MyNodeStruct, "tc_Node"),
    ]


@AmigaStructDef
class MyBCPLStruct(AmigaStruct):
    _format = [
        (BPTR_VOID, "bs_TestBptr"),
    ]


def mem_access_rw_field_node_test():
    mem = MockMemory()
    a = AccessStruct(mem, MyNodeStruct, 0x42)
    a.w_s("ln_Succ", 42)
    a.w_s("ln_Pred", 21)
    a.w_s("ln_Pri", -27)
    assert a.r_s("ln_Succ") == 42
    assert a.r_s("ln_Pred") == 21
    assert a.r_s("ln_Pri") == -27


def mem_access_rw_sub_field_task_test():
    mem = MockMemory()
    a = AccessStruct(mem, MyTaskStruct, 0x42)
    a.w_s("tc_Node.ln_Succ", 42)
    a.w_s("tc_Node.ln_Pred", 21)
    assert a.r_s("tc_Node.ln_Succ") == 42
    assert a.r_s("tc_Node.ln_Pred") == 21


def mem_access_invalid_node_test():
    mem = MockMemory()
    a = AccessStruct(mem, MyNodeStruct, 0x42)
    with pytest.raises(KeyError):
        a.w_s("bla", 12)
    with pytest.raises(KeyError):
        a.r_s("blub")


def mem_access_s_get_addr_test():
    mem = MockMemory()
    a = AccessStruct(mem, MyNodeStruct, 0x42)
    assert a.s_get_addr("ln_Succ") == 0x42
    assert a.s_get_addr("ln_Pred") == 0x46


def mem_access_bptr_test():
    mem = MockMemory()
    a = AccessStruct(mem, MyBCPLStruct, 0x42)
    # write/read addr
    a.w_s("bs_TestBptr", 44)
    assert a.r_s("bs_TestBptr") == 44
    # check auto converted baddr
    assert mem.r32(0x42) == 11
