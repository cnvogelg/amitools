import pytest

from amitools.vamos.astructs import AccessStruct
from amitools.vamos.error import UnsupportedFeatureError
from amitools.vamos.libstructs import DosPacketStruct, MessageStruct, ProcessStruct
from amitools.vamos.libtypes import DosPacket, Message, MsgPort


def pytask_dos_waitpkt_replypkt_test(vamos_task):
    def proc(ctx, task):
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        dos_proxy = ctx.proxies.get_dos_lib_proxy()

        proc_addr = ctx.process.proc.addr
        proc_access = AccessStruct(ctx.mem, ProcessStruct, proc_addr)
        proc_port_addr = proc_access.s_get_addr("pr_MsgPort")
        proc_port = MsgPort(ctx.mem, proc_port_addr)
        if not ctx.exec_lib.port_mgr.has_port(proc_port_addr):
            ctx.exec_lib.port_mgr.register_port(proc_port_addr)

        with pytest.raises(UnsupportedFeatureError):
            dos_proxy.WaitPkt()

        reply_port = exec_proxy.CreateMsgPort()
        if not ctx.exec_lib.port_mgr.has_port(reply_port.addr):
            ctx.exec_lib.port_mgr.register_port(reply_port.addr)

        msg = Message.alloc(ctx.alloc)
        pkt_mem = ctx.alloc.alloc_struct(DosPacketStruct, label="DosPacket")
        pkt = DosPacket(ctx.mem, pkt_mem.addr)

        pkt.link.ref = msg
        pkt.port.ref = reply_port
        msg_access = AccessStruct(ctx.mem, MessageStruct, msg.addr)
        msg_access.w_s("mn_Node.ln_Name", pkt.addr)

        exec_proxy.PutMsg(proc_port, msg)
        assert dos_proxy.WaitPkt() == pkt.addr
        assert exec_proxy.GetMsg(proc_port) is None

        dos_proxy.ReplyPkt(pkt, 0xFFFFFFFF, 0x80000002)

        assert pkt.res1.val == -1
        assert pkt.res2.val == -2147483646
        assert pkt.port.aptr == proc_port_addr

        reply_msg = exec_proxy.GetMsg(reply_port)
        assert reply_msg == msg
        assert exec_proxy.GetMsg(reply_port) is None

        exec_proxy.DeleteMsgPort(reply_port)
        msg.free()
        ctx.alloc.free_struct(pkt_mem)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]
