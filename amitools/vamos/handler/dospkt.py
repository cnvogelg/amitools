"""Real AmigaDOS packet transport for the handler API (step 11).

:class:`DosPktHandler` is a :class:`~amitools.vamos.handler.packet.PacketHandler`
whose ``_dopkt`` transport is a genuine handler ``MsgPort``: the built
``DosPacket`` is wrapped in a ``StandardPacket`` message (its ``mn_Node.ln_Name``
points at the packet), put on the handler port, and the reply is taken off a
per-handler reply port. The handler fills ``dp_Res1``/``dp_Res2`` before it
replies, so the base :class:`PacketHandler` translation applies unchanged.

A volume selects this transport with ``?handler=packet&port=<name|addr>``.
Because a volume is bound while the path manager is built -- before
``exec.library`` (and thus the port manager) exists -- the handler is created
*detached*: it records the port and is attached to the real ``PortManager``
once the exec/dos libraries are open via
:meth:`HandlerManager.attach_packet_transport`.

The reply is expected on the reply port. A synchronous handler (an emulated
one driven in-process) queues it while ``put_msg`` runs, so no wait is needed;
a handler that runs as its own task needs a ``pump`` callable that advances the
emulation until the reply arrives.
"""

from amitools.vamos.libstructs import DosPacketStruct, MessageStruct

from .base import ERROR_NOT_IMPLEMENTED, ERROR_OBJECT_NOT_FOUND, HandlerError
from .packet import PacketHandler


def _parse_port(value):
    """split a config ``port`` value into ``(addr, name)``

    An integer (or a string that parses as one, ``0x...`` allowed) is a port
    address; anything else is a port name to look up with ``FindPort``.
    """
    if value is None:
        return 0, None
    if isinstance(value, int):
        return value, None
    text = str(value)
    try:
        return int(text, 0), None
    except ValueError:
        return 0, text


class DosPktHandler(PacketHandler):
    """handler client that talks to a real handler ``MsgPort``

    Created detached by :func:`packet_factory` and attached to the machine with
    :meth:`attach_transport` once the exec/dos libraries are set up.
    """

    def __init__(self, name, alloc=None, port=None, is_filesystem=True):
        super().__init__(name, alloc, is_filesystem=is_filesystem)
        self.handler_port, self.port_name = _parse_port(port)
        self.port_mgr = None
        self.reply_port = 0
        self._own_reply_port = False
        self._find_port = None
        self._pump = None

    # ----- attaching the transport -----

    def attach_transport(self, alloc, port_mgr, mem, find_port=None, pump=None):
        """bind the handler to the live machine

        ``find_port(name)`` resolves a configured port name (defaults to a
        direct address); ``pump()`` advances the emulation while waiting for a
        reply from a handler that runs as its own task.
        """
        self.alloc = alloc
        self.mem = mem
        self.port_mgr = port_mgr
        self._find_port = find_port
        self._pump = pump
        if self.handler_port == 0 and self.port_name is not None:
            self.handler_port = self._resolve_port()
        if self.reply_port == 0:
            self.reply_port = port_mgr.create_port("%sReply" % self.name, None)
            self._own_reply_port = True

    def _resolve_port(self):
        if self._find_port is None:
            return 0
        port = self._find_port(self.port_name)
        if port is None:
            return 0
        return port.addr if hasattr(port, "addr") else int(port)

    def shutdown(self):
        """release the reply port this handler created"""
        if (
            self._own_reply_port
            and self.port_mgr is not None
            and self.reply_port != 0
            and self.port_mgr.has_port(self.reply_port)
        ):
            # free_port releases the struct but keeps it registered, so drop it
            # from the port table as well
            self.port_mgr.free_port(self.reply_port)
            self.port_mgr.unregister_port(self.reply_port)
        self._own_reply_port = False
        self.reply_port = 0

    # ----- transport hook -----

    def _call(self, action):
        # a detached handler has no allocator yet: fail with a DOS error
        # instead of an AttributeError while building the packet
        if self.alloc is None:
            raise HandlerError(ERROR_NOT_IMPLEMENTED, "packet transport not attached")
        return super()._call(action)

    def _dopkt(self, pkt):
        if self.port_mgr is None or self.alloc is None or self.handler_port == 0:
            raise HandlerError(ERROR_NOT_IMPLEMENTED, "packet transport not attached")
        if not self.port_mgr.has_port(self.handler_port):
            raise HandlerError(
                ERROR_OBJECT_NOT_FOUND,
                "handler port %06x not found" % self.handler_port,
            )
        # a StandardPacket: the message's ln_Name names the DosPacket
        msg = self.alloc.alloc_astruct(MessageStruct, label="DosPkt")
        try:
            msg.node.name.aptr = pkt.addr
            pkt.link.aptr = msg.addr
            pkt.port.aptr = self.reply_port
            self.port_mgr.put_msg(self.handler_port, msg.addr)
            reply_addr = self._wait_reply()
            self._copy_result(pkt, reply_addr)
        finally:
            msg.free()

    def _wait_reply(self):
        port_mgr = self.port_mgr
        reply_port = self.reply_port
        if not port_mgr.has_msg(reply_port):
            if self._pump is None:
                raise HandlerError(
                    ERROR_NOT_IMPLEMENTED, "no packet reply on port %06x" % reply_port
                )
            while not port_mgr.has_msg(reply_port):
                self._pump()
        return port_mgr.get_msg(reply_port)

    def _copy_result(self, pkt, reply_addr):
        """copy dp_Res1/dp_Res2 from the replied StandardPacket back

        A DOS handler replies with the same StandardPacket it received, so
        normally this is the packet itself; read it back anyway so a handler
        that replies with another message is handled too.
        """
        if reply_addr == 0:
            raise HandlerError(ERROR_NOT_IMPLEMENTED, "empty packet reply")
        reply = MessageStruct(self.mem, reply_addr)
        reply_pkt = DosPacketStruct(self.mem, reply.node.name.aptr)
        pkt.res1.val = reply_pkt.res1.val
        pkt.res2.val = reply_pkt.res2.val


def packet_factory(name, path, cfg, file_system):
    """registry factory for the ``packet`` handler type

    Reads the handler port from the volume config (``?handler=packet&port=``).
    The returned handler is detached until
    :meth:`HandlerManager.attach_packet_transport` is called.
    """
    return DosPktHandler(name, port=cfg.get("port"))
