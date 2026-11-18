"""dos.library message packet calls (RKRM AmigaDOS 3, SendPkt/DoPkt/AbortPkt
and the ReplyPkt reply path).

A DOS packet travels as a ``Message`` whose ``ln_Name`` points at the packet
itself; vamos locates the packet through the message, so ``_send_pkt`` fills
``dp_Port``/``dp_Link`` and puts the message on the handler port. ``DoPkt``
allocates one block holding a StandardPacket (message followed by packet),
sends it and waits for the synchronous reply.
"""

from amitools.vamos.libstructs import (
    DosPacketStruct,
    MessageStruct,
    NodeType,
    ProcessStruct,
)
from amitools.vamos.libtypes import DosPacket
from amitools.vamos.log import log_dos

from .Error import DOSFALSE


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
    try:
        ctx.exec_lib.port_mgr.put_msg(reply_port, dp.link.aptr)
    except Exception:
        ctx.proxies.get_exec_lib_proxy().PutMsg(reply_port, dp.link.aptr)
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
