"""dos.library message packet calls (RKRM AmigaDOS 3, SendPkt/DoPkt/AbortPkt
and the ReplyPkt reply path).

A DOS packet travels as a ``Message`` whose ``ln_Name`` points at the packet
itself; vamos locates the packet through the message, so ``_send_pkt`` fills
``dp_Port``/``dp_Link`` and puts the message on the handler port. ``DoPkt``
allocates one block holding a StandardPacket (message followed by packet),
sends it and waits for the synchronous reply.
"""

from amitools.vamos.error import UnsupportedFeatureError
from amitools.vamos.libstructs import (
    DosPacketStruct,
    MessageStruct,
    NodeType,
    ProcessStruct,
)
from amitools.vamos.libtypes import DosPacket, Message, MsgPort
from amitools.vamos.log import log_dos

from . import Helper
from .Error import DOSFALSE


def wait_pkt(dos, ctx):
    """WaitPkt(): wait for a packet on the current process's message port"""
    proc_addr = ctx.exec_lib.exec_lib.this_task.aptr
    if proc_addr == 0:
        log_dos.warning("WaitPkt: ThisTask is NULL")
        return 0
    proc = ProcessStruct(ctx.mem, proc_addr)
    port_addr = proc.pr_MsgPort.addr
    log_dos.info("WaitPkt: proc=%06x port=%06x", proc_addr, port_addr)
    if not ctx.exec_lib.port_mgr.has_port(port_addr):
        # A real signal port the Python port manager does not own: a native
        # (68k) handler receives its packets on its process port through the
        # exec message path, so receive one the same way a real WaitPkt does
        # (WaitPort followed by GetMsg).
        msg_func = ctx.exec_lib
        msg_func.wait_port(proc.msg_port)
        msg = msg_func.get_msg(proc.msg_port)
        if msg is None:
            return 0
        return msg.name.aptr
    if not ctx.exec_lib.port_mgr.has_msg(port_addr):
        raise UnsupportedFeatureError(
            f"WaitPkt on empty message queue called: Port ({port_addr:06x})"
        )
    msg_addr = ctx.exec_lib.port_mgr.get_msg(port_addr)
    Helper.unlink_msg(dos, ctx, msg_addr)
    msg = MessageStruct(ctx.mem, msg_addr)
    return msg.mn_Node.ln_Name.aptr


def reply_pkt(dos, ctx, dp: DosPacket, res1, res2):
    log_dos.info("ReplyPkt(%s, %d, %d)", dp, res1, res2)
    if res1 > 0x7FFFFFFF:
        res1 -= 0x100000000
    if res2 > 0x7FFFFFFF:
        res2 -= 0x100000000
    dp.res1.val = res1
    dp.res2.val = res2
    if dp.link.aptr == 0 or dp.port.aptr == 0:
        return 0
    reply_port = dp.port.aptr
    proc_addr = ctx.exec_lib.exec_lib.this_task.aptr
    if proc_addr != 0:
        proc = ProcessStruct(ctx.mem, proc_addr)
        dp.port.aptr = proc.msg_port.addr
    msg = MessageStruct(ctx.mem, dp.link.aptr)
    msg.node.type.val = NodeType.NT_REPLYMSG
    msg.node.succ.aptr = 0
    msg.node.pred.aptr = 0
    # ReplyMsg semantics: put the message on the reply port and signal its
    # task. Going through the exec message path (not the port manager queue
    # alone) also wakes a real signal port, e.g. the reply port of a native
    # (68k) handler's caller, while a Python port manager port still reaches
    # its callback.
    ctx.exec_lib.put_msg(
        MsgPort(ctx.mem, reply_port),
        Message(ctx.mem, dp.link.aptr),
        msg_type=NodeType.NT_REPLYMSG,
    )
    log_dos.info(
        "ReplyPkt: pkt=%06x res1=%d res2=%d -> port=%06x",
        dp.addr,
        res1,
        res2,
        reply_port,
    )
    return 0


def _proc_reply_port(ctx):
    """the current process's message port (DoPkt's reply port)"""
    proc_addr = ctx.exec_lib.exec_lib.this_task.aptr
    if proc_addr == 0:
        return 0
    return ProcessStruct(ctx.mem, proc_addr).pr_MsgPort.addr


def _send_pkt(ctx, dp_addr, port_addr, reply_addr):
    """fill ``dp_Port``/``dp_Link`` and put the packet on the handler port"""
    dp = DosPacketStruct(ctx.mem, dp_addr)
    msg_addr = dp.link.aptr
    if msg_addr == 0:
        # a StandardPacket: the message immediately precedes the packet
        msg_addr = dp_addr - MessageStruct.get_size()
    dp.port.aptr = reply_addr
    dp.link.aptr = msg_addr
    # vamos locates the packet through the message's ln_Name
    MessageStruct(ctx.mem, msg_addr).node.name.aptr = dp_addr
    log_dos.info(
        "SendPkt: pkt=%06x port=%06x reply=%06x msg=%06x",
        dp_addr,
        port_addr,
        reply_addr,
        msg_addr,
    )
    ctx.exec_lib.port_mgr.put_msg(port_addr, msg_addr)
    return msg_addr


def send_pkt(dos, ctx, dp_addr, port_addr, reply_addr):
    _send_pkt(ctx, dp_addr, port_addr, reply_addr)
    return 0


def do_pkt(dos, ctx, port_addr, action, arg1, arg2, arg3, arg4, arg5):
    args = (arg1, arg2, arg3, arg4, arg5)
    # one block holds the StandardPacket: message followed by packet
    mem = ctx.alloc.alloc_memory(
        MessageStruct.get_size() + DosPacketStruct.get_size(), label="DoPkt"
    )
    try:
        msg_addr = mem.addr
        pkt_addr = msg_addr + MessageStruct.get_size()
        MessageStruct(ctx.mem, msg_addr).node.name.aptr = pkt_addr
        pkt = DosPacketStruct(ctx.mem, pkt_addr)
        pkt.link.aptr = msg_addr
        pkt.type.val = action
        pkt.arg1.val = args[0]
        pkt.arg2.val = args[1]
        pkt.arg3.val = args[2]
        pkt.arg4.val = args[3]
        pkt.arg5.val = args[4]
        reply_port = _proc_reply_port(ctx)
        _send_pkt(ctx, pkt_addr, port_addr, reply_port)
        # the handler replies synchronously while put_msg runs
        reply = dos.WaitPkt(ctx)
        res1 = pkt.res1.val
        res2 = pkt.res2.val
        log_dos.info(
            "DoPkt: port=%06x action=%d args=%s -> res1=%d res2=%d (reply=%06x)",
            port_addr,
            action,
            args,
            res1,
            res2,
            reply,
        )
        dos.setioerr(ctx, res2)
        return res1
    finally:
        ctx.alloc.free_memory(mem)


def abort_pkt(dos, ctx, port_addr, pkt_addr):
    log_dos.info("AbortPkt: port=%06x pkt=%06x -> DOSFALSE", port_addr, pkt_addr)
    return DOSFALSE


class DosPacketMixin:
    """dos.library fd methods (HANDLER.md step 22m)."""

    def WaitPkt(self, ctx):
        return wait_pkt(self, ctx)

    def ReplyPkt(self, ctx, dp: DosPacket, res1, res2):
        return reply_pkt(self, ctx, dp, res1, res2)

    def SendPkt(self, ctx, dp_addr, port_addr, reply_addr):
        return send_pkt(self, ctx, dp_addr, port_addr, reply_addr)

    def DoPkt(self, ctx, port_addr, action, arg1, arg2, arg3, arg4, arg5):
        return do_pkt(self, ctx, port_addr, action, arg1, arg2, arg3, arg4, arg5)

    def AbortPkt(self, ctx, port_addr, pkt_addr):
        return abort_pkt(self, ctx, port_addr, pkt_addr)
