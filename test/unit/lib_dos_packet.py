"""dos.library message packet calls: SendPkt, DoPkt and AbortPkt.

These tests drive the real :class:`DosLibrary` front-ends (``DosPacket``):

* ``SendPkt`` only fills the packet's ``dp_Port``/``dp_Link`` and the
  message's ``ln_Name`` and then hands the message to the handler port. A
  recording port manager asserts exactly what was delivered.
* ``DoPkt`` builds a StandardPacket (message followed by packet), sends it
  and waits for the synchronous reply on the process's own port. A real
  :class:`PortManager` with a server callback answers the packet.
* ``AbortPkt`` is currently a no-op stub: it never touches the queue and
  always reports ``DOSFALSE``. Both the "queued packet" and the
  "unknown packet" case are covered.

Note: ``SendPkt`` (a ``void`` call in AmigaDOS) always returns ``DOSFALSE``
in this implementation, so the unknown-port case is asserted by the port
manager's recorded delivery rather than by a distinct return value.
"""

from types import SimpleNamespace

from amitools.vamos.lib.dos.Error import DOSFALSE, DOSTRUE
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.lib.lexec.PortManager import PortManager
from amitools.vamos.libstructs import (
    DosPacketStruct,
    MessageStruct,
    ProcessStruct,
)
from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc


class _RecordingPortMgr:
    """record ``put_msg`` calls and reject unknown ports"""

    def __init__(self, known=()):
        self.known = set(known)
        self.calls = []
        self.delivered = []
        self.rejected = []

    def has_port(self, port_addr):
        return port_addr in self.known

    def put_msg(self, port_addr, msg_addr):
        self.calls.append((port_addr, msg_addr))
        if port_addr not in self.known:
            self.rejected.append((port_addr, msg_addr))
            return DOSFALSE
        self.delivered.append((port_addr, msg_addr))
        return DOSTRUE


def _send_ctx(port_mgr):
    """a minimal ctx for SendPkt/AbortPkt: memory and a port manager"""
    mem = MockMemory(size_kib=32)
    alloc = MemoryAlloc(mem)
    ctx = SimpleNamespace(
        mem=mem,
        alloc=alloc,
        exec_lib=SimpleNamespace(port_mgr=port_mgr),
    )
    return ctx, mem, alloc


# ----- SendPkt -----


def lib_dos_packet_send_standard_test():
    # a StandardPacket stores the message immediately before the packet, so
    # dp_Link is still zero when SendPkt is called
    port_addr = 0x1000
    reply_addr = 0x2000
    mgr = _RecordingPortMgr(known={port_addr})
    ctx, mem, alloc = _send_ctx(mgr)
    lib = DosLibrary()

    block = alloc.alloc_memory(
        MessageStruct.get_size() + DosPacketStruct.get_size(), label="pkt"
    )
    msg_addr = block.addr
    pkt_addr = msg_addr + MessageStruct.get_size()
    pkt = DosPacketStruct(mem, pkt_addr)
    pkt.link.aptr = 0

    assert lib.SendPkt(ctx, pkt_addr, port_addr, reply_addr) == DOSFALSE

    # the message was delivered to the handler port
    assert mgr.calls == [(port_addr, msg_addr)]
    assert mgr.delivered == [(port_addr, msg_addr)]
    assert mgr.rejected == []
    # _send_pkt filled in the reply port, the link and the message's name
    assert pkt.port.aptr == reply_addr
    assert pkt.link.aptr == msg_addr
    assert MessageStruct(mem, msg_addr).node.name.aptr == pkt_addr

    alloc.free_memory(block)


def lib_dos_packet_send_explicit_link_test():
    # when dp_Link is already set the packet keeps that message instead of
    # deriving it from the packet address
    port_addr = 0x1000
    reply_addr = 0x2000
    mgr = _RecordingPortMgr(known={port_addr})
    ctx, mem, alloc = _send_ctx(mgr)
    lib = DosLibrary()

    msg_block = alloc.alloc_memory(MessageStruct.get_size(), label="msg")
    pkt_block = alloc.alloc_memory(DosPacketStruct.get_size(), label="pkt")
    pkt = DosPacketStruct(mem, pkt_block.addr)
    pkt.link.aptr = msg_block.addr

    assert lib.SendPkt(ctx, pkt_block.addr, port_addr, reply_addr) == DOSFALSE

    assert mgr.delivered == [(port_addr, msg_block.addr)]
    assert pkt.link.aptr == msg_block.addr
    assert MessageStruct(mem, msg_block.addr).node.name.aptr == pkt_block.addr

    alloc.free_memory(msg_block)
    alloc.free_memory(pkt_block)


def lib_dos_packet_send_unknown_port_test():
    # an unknown port is never delivered to; the call still reports DOSFALSE
    port_addr = 0x1000
    reply_addr = 0x2000
    mgr = _RecordingPortMgr(known=set())
    ctx, mem, alloc = _send_ctx(mgr)
    lib = DosLibrary()

    block = alloc.alloc_memory(
        MessageStruct.get_size() + DosPacketStruct.get_size(), label="pkt"
    )
    msg_addr = block.addr
    pkt_addr = msg_addr + MessageStruct.get_size()
    pkt = DosPacketStruct(mem, pkt_addr)
    pkt.link.aptr = 0

    assert lib.SendPkt(ctx, pkt_addr, port_addr, reply_addr) == DOSFALSE

    # the send was attempted on the unknown port but not delivered
    assert mgr.calls == [(port_addr, msg_addr)]
    assert mgr.delivered == []
    assert mgr.rejected == [(port_addr, msg_addr)]

    alloc.free_memory(block)


# ----- AbortPkt -----


def lib_dos_packet_abort_queued_test():
    # AbortPkt is a no-op stub: it reports DOSFALSE and never touches the
    # port manager, even for a packet that was queued before
    port_addr = 0x1000
    mgr = _RecordingPortMgr(known={port_addr})
    ctx, mem, alloc = _send_ctx(mgr)
    lib = DosLibrary()

    block = alloc.alloc_memory(DosPacketStruct.get_size(), label="pkt")
    pkt_addr = block.addr
    pkt = DosPacketStruct(mem, pkt_addr)
    pkt.link.aptr = 0

    assert lib.AbortPkt(ctx, port_addr, pkt_addr) == DOSFALSE
    assert mgr.calls == []

    alloc.free_memory(block)


def lib_dos_packet_abort_unknown_test():
    # an unknown packet address is also reported as DOSFALSE and is ignored
    port_addr = 0x1000
    mgr = _RecordingPortMgr(known={port_addr})
    ctx, _mem, _alloc = _send_ctx(mgr)
    lib = DosLibrary()

    assert lib.AbortPkt(ctx, port_addr, 0xDEAD) == DOSFALSE
    assert mgr.calls == []


# ----- DoPkt -----


class _DoPktEnv:
    """a real PortManager with a server callback answering DoPkt packets"""

    def __init__(self, result=0x1234, error=0):
        self.mem = MockMemory(size_kib=64)
        self.alloc = MemoryAlloc(self.mem)
        self.port_mgr = PortManager(self.alloc)
        self.result = result
        self.error = error
        self.calls = []

        proc_mem = self.alloc.alloc_astruct(ProcessStruct, label="Proc")
        self.proc_mem = proc_mem
        self.proc = ProcessStruct(self.mem, proc_mem.addr)
        self.proc_port = self.proc.pr_MsgPort.addr
        self.port_mgr.register_port(self.proc_port)

        self.handler_port = self.port_mgr.create_port("handler", self._server)

        exec_lib = SimpleNamespace(this_task=SimpleNamespace(aptr=proc_mem.addr))
        self.ctx = SimpleNamespace(
            mem=self.mem,
            alloc=self.alloc,
            process=None,
            exec_lib=SimpleNamespace(exec_lib=exec_lib, port_mgr=self.port_mgr),
        )
        self.lib = DosLibrary()

    def _server(self, port_mgr, msg_addr):
        msg = MessageStruct(self.mem, msg_addr)
        pkt = DosPacketStruct(self.mem, msg.node.name.aptr)
        self.calls.append(
            {
                "msg": msg_addr,
                "pkt": pkt.addr,
                "action": pkt.type.val,
                "args": (
                    pkt.arg1.val,
                    pkt.arg2.val,
                    pkt.arg3.val,
                    pkt.arg4.val,
                    pkt.arg5.val,
                ),
            }
        )
        pkt.res1.val = self.result
        pkt.res2.val = self.error
        port_mgr.put_msg(pkt.port.aptr, msg_addr)


def lib_dos_packet_dopkt_test():
    env = _DoPktEnv(result=0x1234, error=0)
    free_before = env.alloc.get_free_bytes()

    res = env.lib.DoPkt(env.ctx, env.handler_port, 5, 11, 22, 33, 44, 55)

    # the synchronous reply is returned and its res2 becomes IoErr
    assert res == 0x1234
    assert env.lib.io_err == 0
    # the server saw the action and all five arguments
    assert len(env.calls) == 1
    call = env.calls[0]
    assert call["action"] == 5
    assert call["args"] == (11, 22, 33, 44, 55)
    # the reply message was collected off the process port
    assert env.port_mgr.has_msg(env.proc_port) is False
    # the StandardPacket block allocated for the call was freed again
    assert env.alloc.get_free_bytes() == free_before


def lib_dos_packet_dopkt_error_test():
    # a negative-ish result and a non-zero res2 are passed through
    env = _DoPktEnv(result=0, error=205)

    res = env.lib.DoPkt(env.ctx, env.handler_port, 33, 0, 0, 0, 0, 0)

    assert res == 0
    assert env.lib.io_err == 205
    assert env.calls[0]["action"] == 33
    assert env.port_mgr.has_msg(env.proc_port) is False
