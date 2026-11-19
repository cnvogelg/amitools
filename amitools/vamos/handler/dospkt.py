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
emulation until the reply arrives. Such a handler waits for the signal of its
port, which ``PortManager.put_msg`` alone does not send: the transport then
needs a ``put_msg`` that delivers like exec's ``PutMsg()``.

Packets in flight
-----------------

Every packet sent is tracked until its reply arrives, and a reply is matched to
its packet by the packet address in the message's ``ln_Name``, never by its
place in the queue: a handler can answer packets in any order, and a packet
whose wait was given up may still be answered later.

- A wait ends when the reply arrives, when ``timeout`` seconds have passed,
  when the pump returns ``False`` (nothing can make progress: every task
  waits, or the handler has ended), or when the pump raises. The wait then
  raises :class:`PacketTimeout` (or the pump's exception), and the packet is
  *abandoned*.
- An abandoned packet and every buffer it names stay allocated until the
  handler replies: the handler may still read them, or write its answer into
  them. That includes memory outside the call, such as a lock's
  ``FileInfoBlock``, which :meth:`_free_struct` keeps while a packet points
  to it.
- A late reply is taken by whichever wait or :meth:`poll` sees it first. What
  it grants is given back: a lock is freed with ``ACTION_FREE_LOCK``, an open
  file ended with ``ACTION_END``. Those packets are sent without a wait of
  their own, and their replies are late replies in turn.
- Waits may nest (the pump can run guest code that calls back into this
  handler), and a nested wait may take the outer packet's reply. Calls from
  several host threads are serialized by a lock. The pump runs on the calling
  thread, so an embedder whose emulation is bound to one thread calls from
  that thread.
"""

import threading
import time

from amitools.vamos.lib.dos.action import DosAction
from amitools.vamos.libstructs import (
    DosPacketStruct,
    FileHandleStruct,
    MessageStruct,
    NodeType,
)
from amitools.vamos.log import log_dos

from .base import (
    ERROR_NOT_IMPLEMENTED,
    ERROR_OBJECT_IN_USE,
    ERROR_OBJECT_NOT_FOUND,
    HandlerError,
)
from .packet import PacketHandler

# actions whose dp_Res1 is a lock the caller owns
_LOCK_ACTIONS = frozenset(
    {
        DosAction.ACTION_LOCATE_OBJECT,
        DosAction.ACTION_COPY_DIR,
        DosAction.ACTION_PARENT,
        DosAction.ACTION_CREATE_DIR,
        DosAction.ACTION_COPY_DIR_FH,
        DosAction.ACTION_PARENT_FH,
    }
)

# actions that open a file: dp_Arg1 is the BPTR of the FileHandle whose
# fh_Arg1 the handler fills in
_OPEN_ACTIONS = frozenset(
    {
        DosAction.ACTION_FINDINPUT,
        DosAction.ACTION_FINDOUTPUT,
        DosAction.ACTION_FINDUPDATE,
        DosAction.ACTION_FH_FROM_LOCK,
    }
)

_NUM_ARGS = 7


class PacketTimeout(HandlerError):
    """the handler did not answer a packet in time

    The packet is abandoned, not cancelled: the handler may still act on it
    and answer later (see the module documentation). The DOS error is
    ``ERROR_OBJECT_IN_USE``: the handler is still busy with the request.
    """

    def __init__(self, msg=None):
        super().__init__(ERROR_OBJECT_IN_USE, msg)


class _InFlight:
    """a packet put on the handler port and not yet answered"""

    def __init__(self, pkt_addr, action, args, msg):
        self.pkt_addr = pkt_addr
        self.action = action
        self.args = args
        self.msg = msg
        # what the packet's memory belongs to once it is abandoned: the
        # _PacketCall, or the packet struct of a packet nobody waits for
        self.owned = None
        self.replied = False
        self.abandoned = False
        self.res1 = 0
        self.res2 = 0

    def holds(self, addr):
        """does this packet name memory at addr (as an APTR or a BPTR)?"""
        return addr in self.args or (addr & 3 == 0 and addr >> 2 in self.args)


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

    # seconds a pumped wait runs before its packet is abandoned
    REPLY_TIMEOUT = 30.0

    def __init__(self, name, alloc=None, port=None, is_filesystem=True):
        super().__init__(name, alloc, is_filesystem=is_filesystem)
        self.handler_port, self.port_name = _parse_port(port)
        self.port_mgr = None
        self.reply_port = 0
        self._own_reply_port = False
        self._find_port = None
        self._pump = None
        self._put_msg = None
        self.timeout = self.REPLY_TIMEOUT
        # packet address -> _InFlight, for every packet not yet answered
        self._in_flight = {}
        # structs kept while an abandoned packet points to them
        self._deferred = []
        self._lock = threading.RLock()

    # ----- attaching the transport -----

    def attach_transport(
        self,
        alloc,
        port_mgr,
        mem,
        find_port=None,
        pump=None,
        timeout=None,
        put_msg=None,
    ):
        """bind the handler to the live machine

        ``find_port(name)`` resolves a configured port name (defaults to a
        direct address); ``pump()`` advances the emulation while waiting for a
        reply from a handler that runs as its own task, and returns ``False``
        once nothing can make progress any more. ``timeout`` (seconds) bounds
        a pumped wait; it defaults to ``REPLY_TIMEOUT``. ``put_msg(port_addr,
        msg_addr)`` delivers a packet to the handler port as ``PutMsg()``
        does: it queues the message, on a port the port manager knows or in
        the port's ``mp_MsgList``, and signals the port's task. Without one,
        the packet goes to the port manager's queue only, which is enough for
        a handler driven in-process.
        """
        self.alloc = alloc
        self.mem = mem
        self.port_mgr = port_mgr
        self._find_port = find_port
        self._pump = pump
        self._put_msg = put_msg
        if timeout is not None:
            self.timeout = timeout
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
        """release the reply port and the packets still out

        The handler is gone or about to be, so nothing answers them any more.
        """
        with self._lock:
            for entry in list(self._in_flight.values()):
                self._release(entry)
            for struct in self._deferred:
                struct.free()
            self._deferred = []
            if (
                self._own_reply_port
                and self.port_mgr is not None
                and self.reply_port != 0
                and self.port_mgr.has_port(self.reply_port)
            ):
                # free_port releases the struct but keeps it registered, so
                # drop it from the port table as well
                self.port_mgr.free_port(self.reply_port)
                self.port_mgr.unregister_port(self.reply_port)
            self._own_reply_port = False
            self.reply_port = 0

    # ----- raw packets -----

    def do_packet(self, action, *args):
        """send a packet with raw arguments; return ``(dp_Res1, dp_Res2)``

        Like ``DoPkt``: the arguments go into ``dp_Arg1``... as given (as
        unsigned or signed 32-bit values), and the results come back as they
        are, without turning a failure into a :class:`HandlerError`. A wait
        that ends without a reply raises as for any other call. Memory the
        arguments name belongs to the caller, who should not reuse it while
        :meth:`holds` says an unanswered packet points to it.
        """
        if len(args) > _NUM_ARGS:
            raise ValueError("a DosPacket has %d arguments" % _NUM_ARGS)
        with self._call(action) as call:
            for index, value in enumerate(args, 1):
                value &= 0xFFFFFFFF
                call.arg(index, value - 0x100000000 if value & 0x80000000 else value)
            self._dopkt(call.pkt)
            return call.pkt.res1.val, call.pkt.res2.val

    def holds(self, addr):
        """does an abandoned packet still name memory at ``addr``?

        A packet names a buffer by its start address or by its BPTR.
        """
        with self._lock:
            return self._is_held(addr)

    # ----- packets in flight -----

    def pending(self):
        """the actions of the abandoned packets still waiting for a reply"""
        with self._lock:
            return [e.action for e in self._in_flight.values() if e.abandoned]

    def poll(self):
        """take the replies queued so far without running the handler

        Late replies are released and what they grant is given back. Returns
        the number of replies taken.
        """
        with self._lock:
            if self.port_mgr is None or self.reply_port == 0:
                return 0
            return self._take_replies()

    def wait_pending(self, timeout=None):
        """run the handler until every abandoned packet has its reply

        Stops after ``timeout`` seconds (default: the handler's ``timeout``)
        or when the pump returns ``False``. Returns the actions still out.
        """
        with self._lock:
            if timeout is None:
                timeout = self.timeout
            deadline = None if timeout is None else time.monotonic() + timeout
            self.poll()
            while self._pump is not None and self.pending():
                if deadline is not None and time.monotonic() >= deadline:
                    break
                progress = self._pump()
                self._take_replies()
                if progress is False:
                    break
            return self.pending()

    # ----- transport hook -----

    def _call(self, action):
        # a detached handler has no allocator yet: fail with a DOS error
        # instead of an AttributeError while building the packet
        if self.alloc is None:
            raise HandlerError(ERROR_NOT_IMPLEMENTED, "packet transport not attached")
        return super()._call(action)

    def _end_call(self, call):
        with self._lock:
            pkt = call.pkt
            entry = None if pkt is None else self._in_flight.get(pkt.addr)
            if entry is not None and entry.abandoned:
                # the handler may still use the packet: keep it until the reply
                entry.owned = call
                return
            super()._end_call(call)

    def _free_struct(self, struct):
        with self._lock:
            if self._is_held(struct.addr):
                self._deferred.append(struct)
            else:
                struct.free()

    def _dopkt(self, pkt):
        with self._lock:
            entry = self._send(pkt.addr, pkt.type.val, self._packet_args(pkt))
            try:
                self._wait(entry)
            except BaseException:
                if not entry.replied:
                    entry.abandoned = True
                    log_dos.warning(
                        "%s: packet %06x (action %d) abandoned without a reply",
                        self.name,
                        entry.pkt_addr,
                        entry.action,
                    )
                raise
            pkt.res1.val = entry.res1
            pkt.res2.val = entry.res2

    def _send(self, pkt_addr, action, args):
        if self.port_mgr is None or self.alloc is None or self.handler_port == 0:
            raise HandlerError(ERROR_NOT_IMPLEMENTED, "packet transport not attached")
        if self._put_msg is None and not self.port_mgr.has_port(self.handler_port):
            raise HandlerError(
                ERROR_OBJECT_NOT_FOUND,
                "handler port %06x not found" % self.handler_port,
            )
        # a StandardPacket: the message's ln_Name names the DosPacket
        msg = self.alloc.alloc_astruct(MessageStruct, label="DosPkt")
        # as PutMsg() sets it: a handler that tells its I/O replies
        # (NT_REPLYMSG) from packets by the type would skip the packet
        msg.node.type.val = NodeType.NT_MESSAGE
        msg.node.name.aptr = pkt_addr
        # for a handler that answers with ReplyMsg()
        msg.reply_port.aptr = self.reply_port
        msg.length.val = MessageStruct.get_size() + DosPacketStruct.get_size()
        pkt = DosPacketStruct(self.mem, pkt_addr)
        pkt.link.aptr = msg.addr
        pkt.port.aptr = self.reply_port
        entry = _InFlight(pkt_addr, action, args, msg)
        self._in_flight[pkt_addr] = entry
        # a synchronous handler queues its reply while put_msg runs
        if self._put_msg is not None:
            self._put_msg(self.handler_port, msg.addr)
        else:
            self.port_mgr.put_msg(self.handler_port, msg.addr)
        return entry

    def _send_unwaited(self, action, arg1):
        """send a packet whose reply nobody waits for: it releases itself"""
        pkt = self.alloc.alloc_astruct(DosPacketStruct, label="DosPkt")
        pkt.type.val = int(action)
        pkt.arg1.val = arg1
        try:
            entry = self._send(pkt.addr, int(action), self._packet_args(pkt))
        except HandlerError:
            pkt.free()
            raise
        entry.owned = pkt
        entry.abandoned = True

    def _wait(self, entry):
        deadline = None
        if self.timeout is not None:
            deadline = time.monotonic() + self.timeout
        while True:
            self._take_replies()
            if entry.replied:
                return
            if self._pump is None:
                raise HandlerError(
                    ERROR_NOT_IMPLEMENTED,
                    "no packet reply on port %06x" % self.reply_port,
                )
            if deadline is not None and time.monotonic() >= deadline:
                raise PacketTimeout(
                    "no reply to packet %06x within %s s"
                    % (entry.pkt_addr, self.timeout)
                )
            if self._pump() is False:
                self._take_replies()
                if entry.replied:
                    return
                raise PacketTimeout(
                    "handler stopped without replying to packet %06x" % entry.pkt_addr
                )

    def _take_replies(self):
        """take every queued reply and match it to its packet"""
        port_mgr = self.port_mgr
        taken = 0
        while port_mgr.has_msg(self.reply_port):
            msg_addr = port_mgr.get_msg(self.reply_port)
            taken += 1
            if msg_addr == 0:
                continue
            # a handler replies with the StandardPacket it got, but read the
            # packet through the message in case it replied with another one
            pkt_addr = MessageStruct(self.mem, msg_addr).node.name.aptr
            entry = self._in_flight.get(pkt_addr)
            if entry is None:
                log_dos.warning(
                    "%s: reply %06x names no packet in flight (%06x)",
                    self.name,
                    msg_addr,
                    pkt_addr,
                )
                continue
            reply = DosPacketStruct(self.mem, pkt_addr)
            entry.res1 = reply.res1.val
            entry.res2 = reply.res2.val
            entry.replied = True
            if entry.abandoned:
                self._late_reply(entry)
            else:
                # its waiter, maybe an outer one, picks the result up
                self._release(entry)
        return taken

    def _late_reply(self, entry):
        """release an abandoned packet and give back what its reply grants"""
        log_dos.info(
            "%s: late reply to packet %06x (action %d): res1=%d res2=%d",
            self.name,
            entry.pkt_addr,
            entry.action,
            entry.res1,
            entry.res2,
        )
        fh_arg1 = 0
        if entry.action in _OPEN_ACTIONS and entry.res1 != 0:
            fh_addr = entry.args[0] << 2
            if fh_addr != 0:
                fh_arg1 = FileHandleStruct(self.mem, fh_addr).fh_Args.val
        self._release(entry)
        try:
            if entry.action in _LOCK_ACTIONS and entry.res1 != 0:
                self._send_unwaited(DosAction.ACTION_FREE_LOCK, entry.res1)
            elif fh_arg1 != 0:
                self._send_unwaited(DosAction.ACTION_END, fh_arg1)
        except HandlerError as exc:
            log_dos.warning("%s: can't give back a late reply: %s", self.name, exc)

    def _release(self, entry):
        """free an answered (or orphaned) packet and what it kept"""
        self._in_flight.pop(entry.pkt_addr, None)
        if entry.msg is not None:
            entry.msg.free()
            entry.msg = None
        owned, entry.owned = entry.owned, None
        if owned is not None:
            owned.free()
        if self._deferred:
            # structs this packet named may be free now
            kept = []
            for struct in self._deferred:
                if self._is_held(struct.addr):
                    kept.append(struct)
                else:
                    struct.free()
            self._deferred = kept

    def _is_held(self, addr):
        return any(e.abandoned and e.holds(addr) for e in self._in_flight.values())

    @staticmethod
    def _packet_args(pkt):
        return tuple(
            getattr(pkt, "arg%d" % index).val & 0xFFFFFFFF
            for index in range(1, _NUM_ARGS + 1)
        )


def packet_factory(name, path, cfg, file_system):
    """registry factory for the ``packet`` handler type

    Reads the handler port from the volume config (``?handler=packet&port=``).
    The returned handler is detached until
    :meth:`HandlerManager.attach_packet_transport` is called.
    """
    return DosPktHandler(name, port=cfg.get("port"))
