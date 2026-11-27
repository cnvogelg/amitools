from amitools.vamos.lib.lexec.interruptfunc import InterruptMixin
from amitools.vamos.libstructs import InterruptStruct
from amitools.vamos.machine.mock import MockCPU
from amitools.vamos.machine.regs import REG_D0
from lib_exec_helper import ExecHost, make_exec_lib


class Host(ExecHost, InterruptMixin):
    pass


def _host():
    mem, alloc, el = make_exec_lib()
    return Host(mem, alloc, el, cpu=MockCPU())


def exec_set_sr_test():
    host = _host()
    cpu = host.ctx.cpu
    cpu.w_sr(0x0010)
    # SetSR returns the old SR in D0
    assert host.SetSR(host.ctx, 0x2700, 0x00FF) is None
    assert cpu.r_reg(REG_D0) == 0x0010
    # only the masked (low) byte changed
    assert cpu.r_sr() == 0x0000
    # a read-only SetSR(0,0) returns the SR and changes nothing
    cpu.w_sr(0x1234)
    host.SetSR(host.ctx, 0, 0)
    assert cpu.r_reg(REG_D0) == 0x1234
    assert cpu.r_sr() == 0x1234


def exec_super_state_user_state_test():
    host = _host()
    cpu = host.ctx.cpu
    cpu.w_sr(0x0010)
    assert host.SuperState(host.ctx) is None
    old = cpu.r_reg(REG_D0)
    assert old == 0x0010
    assert cpu.r_sr() & 0x2000
    assert host.UserState(host.ctx, old) is None
    assert cpu.r_sr() == 0x0010


def exec_set_int_vector_test():
    host = _host()
    intr = host.alloc.alloc_astruct(InterruptStruct, label="intr")
    intr.is_Data.aptr = 0x1234
    intr.is_Code.aptr = 0x5678
    # vector 7 is an exception handler: the node is kept
    old = host.SetIntVector(host.ctx, 7, intr)
    assert old == 0
    vec = host.exec_lib.int_vects[7]
    assert vec.iv_Node.aptr == intr.addr
    assert vec.iv_Data.aptr == 0x1234
    assert vec.iv_Code.aptr == 0x5678
    # a second SetIntVector returns the previous node
    intr2 = host.alloc.alloc_astruct(InterruptStruct, label="intr2")
    assert host.SetIntVector(host.ctx, 7, intr2) == intr.addr
    # clearing marks the data/code as invalid (~0) and drops the node
    host.SetIntVector(host.ctx, 7, None)
    vec = host.exec_lib.int_vects[7]
    assert vec.iv_Node.aptr == 0
    assert vec.iv_Data.aptr == 0xFFFFFFFF
    assert vec.iv_Code.aptr == 0xFFFFFFFF
    # vector 3 is not an exception handler: no node is stored
    host.SetIntVector(host.ctx, 3, intr)
    assert host.exec_lib.int_vects[3].iv_Node.aptr == 0


def exec_add_rem_int_server_test():
    host = _host()
    mem = host.mem
    a = host.alloc.alloc_astruct(InterruptStruct, label="a")
    b = host.alloc.alloc_astruct(InterruptStruct, label="b")
    host.AddIntServer(host.ctx, 7, a)
    host.AddIntServer(host.ctx, 7, b)
    vec = host.exec_lib.int_vects[7]
    # b was added last: it heads the chain and links to a
    assert vec.iv_Node.aptr == b.addr
    assert mem.r32(b.addr) == a.addr
    assert mem.r32(a.addr) == 0
    # remove the head
    host.RemIntServer(host.ctx, 7, b)
    assert vec.iv_Node.aptr == a.addr
    # remove the tail
    host.RemIntServer(host.ctx, 7, a)
    assert vec.iv_Node.aptr == 0
