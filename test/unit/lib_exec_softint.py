import struct
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from amitools.vamos.lib.lexec.msgfunc import MessageFunc
from amitools.vamos.lib.lexec.PortManager import PortManager
from amitools.vamos.lib.lexec.softint import SoftIntFunc
from amitools.vamos.libstructs import InterruptStruct, MsgPortFlags, NodeType
from amitools.vamos.libtypes import Message, MsgPort
from amitools.vamos.machine import REG_A1, REG_A5, REG_A6, REG_D0, Code, Machine
from amitools.vamos.machine import Runtime
from amitools.vamos.machine.backend import Machine68kBackend
from amitools.vamos.mem import MemoryAlloc

EXEC_BASE = 0x4000

# addq.l #1,(a1); move.l a6,4(a1); move.l a5,8(a1); rts
COUNT_HANDLER = bytes.fromhex("5291234e0004234d00084e75")


class Env:
    def __init__(self):
        self.machine = Machine(Machine68kBackend().create_machine("68000"))
        self.mem = self.machine.mem
        self.alloc = MemoryAlloc.for_machine(self.machine)
        self.runtime = Runtime(self.machine, default_sp=self.machine.get_scratch_top())
        self.ctx = SimpleNamespace(
            machine=self.machine,
            cpu=self.machine.cpu,
            mem=self.mem,
            alloc=self.alloc,
            runner=self.runtime.run,
        )
        self.soft = SoftIntFunc(self.ctx, EXEC_BASE)
        self._mems = []

    def block(self, size, data=b""):
        m = self.alloc.alloc_memory(size)
        self._mems.append(m)
        self.mem.w_block(m.addr, data.ljust(size, b"\0"))
        return m.addr

    def interrupt(self, code, data=0, pri=0):
        addr = self.block(InterruptStruct.get_size())
        intr = InterruptStruct(self.mem, addr)
        intr.is_Node.ln_Type.val = NodeType.NT_INTERRUPT
        intr.is_Node.ln_Pri.val = pri
        intr.is_Data.aptr = data
        intr.is_Code.aptr = code
        return addr

    def py_handler(self, func):
        """an interrupt handler that calls func from 68k code"""
        trap = self.machine.setup_quick_trap(lambda op, pc: func())
        return self.block(8, struct.pack(">HIH", 0x4EB9, trap, 0x4E75))

    def run_from_68k(self, func, set_regs=None, get_regs=None):
        """run func in a trap called from a 68k program"""
        trap = self.machine.setup_quick_trap(lambda op, pc: func())
        prog = self.block(8, struct.pack(">HIH", 0x4EB9, trap, 0x4E75))
        result = self.runtime.run(Code(prog, None, set_regs or {}, get_regs or []))
        assert result.mach_error is None
        return result

    def close(self):
        for m in self._mems:
            self.alloc.free_memory(m)
        assert self.alloc.is_all_free()
        self.machine.cleanup()


@pytest.fixture
def env():
    e = Env()
    yield e
    e.close()


def exec_cause_runs_handler_with_regs_test(env):
    data = env.block(12)
    intr = env.interrupt(env.block(16, COUNT_HANDLER), data)
    # the caller's registers survive the nested call
    regs = {REG_A1: 0x1111, REG_A5: 0x5555, REG_A6: 0x6666, REG_D0: 7}
    result = env.run_from_68k(
        lambda: env.soft.cause(intr), regs, [REG_A1, REG_A5, REG_A6, REG_D0]
    )
    assert result.regs == regs
    assert env.mem.r32(data) == 1
    assert env.mem.r32(data + 4) == EXEC_BASE
    assert env.mem.r32(data + 8) == env.mem.r32(intr + 18)
    assert env.mem.r8(intr + 8) == NodeType.NT_INTERRUPT


def exec_cause_outside_68k_test(env):
    data = env.block(12)
    intr = env.interrupt(env.block(16, COUNT_HANDLER), data)
    env.soft.cause(intr)
    env.soft.cause(intr)
    assert env.mem.r32(data) == 2


def exec_cause_pending_is_ignored_test(env):
    data = env.block(12)
    intr = env.interrupt(env.block(16, COUNT_HANDLER), data)
    env.mem.w8(intr + 8, NodeType.NT_SOFTINT)
    env.soft.cause(intr)
    assert env.mem.r32(data) == 0


def exec_cause_does_not_nest_test(env):
    order = []
    low = env.interrupt(env.py_handler(lambda: order.append("low")), pri=-32)
    high = env.interrupt(env.py_handler(lambda: order.append("high")), pri=32)
    again = []

    def first():
        order.append("first")
        env.soft.cause(low)
        env.soft.cause(high)
        # an interrupt may Cause() itself while it runs
        if not again:
            again.append(True)
            env.soft.cause(first_intr)
        order.append("first done")

    first_intr = env.interrupt(env.py_handler(first))
    env.run_from_68k(lambda: env.soft.cause(first_intr))
    # the second "first" causes "high" again (served) but not "low" (pending)
    assert order == [
        "first",
        "first done",
        "high",
        "first",
        "first done",
        "high",
        "low",
    ]


def exec_putmsg_softint_port_test(env):
    signal = SimpleNamespace(signal=Mock())
    msgs = MessageFunc(env.ctx, None, signal, None, PortManager(env.alloc), env.soft)
    port = MsgPort(env.mem, env.block(MsgPort.get_size()))
    got = []

    def handler():
        # the message is queued before the interrupt runs
        msg = msgs.get_msg(port)
        got.append(msg.addr if msg else None)

    intr = env.interrupt(env.py_handler(handler))
    port.new(flags=MsgPortFlags.PA_SOFTINT)
    port.sig_task.aptr = intr  # mp_SoftInt
    msg = Message(env.mem, env.block(Message.get_size()))
    msg.new()
    env.run_from_68k(lambda: msgs.put_msg(port, msg))
    assert got == [msg.addr]
    signal.signal.assert_not_called()
