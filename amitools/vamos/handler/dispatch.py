"""Handler dispatcher: a handler's own packet port.

Like a real AmigaDOS handler process, a handler bound to a volume is reachable
through its own message port. :class:`HandlerDispatcher` bundles that port with
the :class:`~amitools.vamos.handler.decode.PacketDecoder` that serves the
handler: a message put on the port is decoded onto the handler and the reply is
posted back to the packet's ``dp_Port``.

The dispatcher is injected as ``handler.dispatcher`` by
:meth:`~amitools.vamos.handler.mgr.HandlerManager.attach_dispatchers` and is
reported by ``GetDeviceProc``/``fh_Type``/``fl_Task``.
"""

from amitools.vamos.lib.dos.action import DosAction
from amitools.vamos.libstructs import DosPacketStruct, MessageStruct
from amitools.vamos.log import log_handler


class HandlerDispatcher:
    """a handler's packet port wired to its packet decoder"""

    def __init__(self, port_mgr, mem, name, decoder):
        self.port_mgr = port_mgr
        self.mem = mem
        self.name = name
        self.decoder = decoder
        self.port = port_mgr.create_port(name, self.put_msg)

    def put_msg(self, port_mgr, msg_addr):
        """decode one packet and post the reply to the sender's reply port"""
        msg = MessageStruct(self.mem, msg_addr)
        dos_pkt_addr = msg.node.name.aptr
        dos_pkt = DosPacketStruct(self.mem, dos_pkt_addr)
        reply_port_addr = dos_pkt.port.aptr
        pkt_type = dos_pkt.type.val
        try:
            pkt_name = DosAction(pkt_type).name
        except ValueError:
            pkt_name = "?"
        log_handler.info(
            "DosPacket: msg=%06x -> pkt=%06x: reply_port=%06x type=%06x (%s)",
            msg_addr,
            dos_pkt_addr,
            reply_port_addr,
            pkt_type,
            pkt_name,
        )
        self.decoder.decode(dos_pkt)
        # do reply
        if not port_mgr.has_port(reply_port_addr):
            port_mgr.register_port(reply_port_addr)
        port_mgr.put_msg(reply_port_addr, msg_addr)

    def free(self):
        if self.port:
            self.port_mgr.free_port(self.port)
            self.port = 0
