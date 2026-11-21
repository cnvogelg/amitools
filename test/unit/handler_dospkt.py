"""DosPktHandler (``handler/dospkt.py``) tests.

The transport under test is real: packets are put on a ``MsgPort`` and the
reply is taken off a reply port, both managed by the exec ``PortManager``. The
handler on the other end is a real :class:`HostFileSysHandler` driven by the
:class:`~handler_decode.DecoderHarness`, wrapped as a port callback, so the
whole shared :class:`handler_contract.HandlerContract` runs through the
packet/port boundary (``TestDosPktContract``).
"""

import threading
import time
from types import SimpleNamespace

import pytest
from handler_contract import (
    HandlerContract,
    expect_error,
)
from handler_decode import DecoderHarness

from amitools.vamos.handler import (
    DosPktHandler,
    HandlerManager,
    HostFileSysHandler,
    default_registry,
)
from amitools.vamos.handler.dospkt import PacketTimeout, packet_factory
from amitools.vamos.lib.dos.action import DosAction
from amitools.vamos.lib.lexec.PortManager import PortManager
from amitools.vamos.libstructs import (
    DosPacketStruct,
    FileHandleStruct,
    MessageStruct,
    NodeType,
)
from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc

# ERROR_ACTION_NOT_KNOWN
ERROR_ACTION_NOT_KNOWN = 209
# ERROR_OBJECT_NOT_FOUND
ERROR_OBJECT_NOT_FOUND = 205
# ERROR_NOT_IMPLEMENTED
ERROR_NOT_IMPLEMENTED = 236
# ERROR_OBJECT_IN_USE
ERROR_OBJECT_IN_USE = 202


def _make_server(mem, decode):
    """turn a packet decoder into a PortManager message callback

    Reads the DosPacket named by the message and replies on the packet's
    ``dp_Port``, exactly like a real handler's ``ReplyPkt``.
    """

    def server(port_mgr, msg_addr):
        msg = MessageStruct(mem, msg_addr)
        pkt = DosPacketStruct(mem, msg.node.name.aptr)
        decode(pkt)
        port_mgr.put_msg(pkt.port.aptr, msg_addr)

    return server


def _make_handler(name, alloc, mem, port_mgr, root_path, pump=None):
    server_handler = HostFileSysHandler(name, root_path)
    harness = DecoderHarness(server_handler, mem)
    port = port_mgr.create_port(name + "Handler", _make_server(mem, harness.decode))
    handler = DosPktHandler(name, alloc, port=port)
    handler.attach_transport(alloc, port_mgr, mem, pump=pump)
    return handler


@pytest.fixture
def env(tmp_path):
    mem = MockMemory(size_kib=256)
    alloc = MemoryAlloc(mem)
    port_mgr = PortManager(alloc)
    root = tmp_path / "work"
    root.mkdir()

    def make(name):
        return _make_handler(name, alloc, mem, port_mgr, str(root))

    return SimpleNamespace(kind="dospkt", h=make("work"), new_handler=make)


class TestDosPktContract(HandlerContract):
    pass


# --------------------------------------------------------------------------
# transport: attach, reply, pump, teardown
# --------------------------------------------------------------------------


def dospkt_detached_test():
    # a handler created before the machine exists has no transport yet
    handler = DosPktHandler("work")
    expect_error(ERROR_NOT_IMPLEMENTED, handler.locate_object, "x")


def dospkt_factory_parse_test():
    by_addr = packet_factory("work", None, {"port": "0x1234"}, None)
    assert by_addr.handler_port == 0x1234
    assert by_addr.port_name is None
    by_name = packet_factory("work", None, {"port": "MyHandler"}, None)
    assert by_name.handler_port == 0
    assert by_name.port_name == "MyHandler"
    # no port configured
    none = packet_factory("work", None, {}, None)
    assert none.handler_port == 0
    assert none.port_name is None


def dospkt_registry_test():
    reg = default_registry()
    assert "packet" in reg.get_all_types()
    handler = reg.create("packet", "work", None, {"port": "0x100"}, None)
    assert isinstance(handler, DosPktHandler)
    assert handler.handler_port == 0x100


def dospkt_attach_by_name_test(tmp_path):
    mem = MockMemory(size_kib=64)
    alloc = MemoryAlloc(mem)
    port_mgr = PortManager(alloc)
    server_handler = HostFileSysHandler("work", str(tmp_path))
    harness = DecoderHarness(server_handler, mem)
    port = port_mgr.create_port("MyHandler", _make_server(mem, harness.decode))

    handler = packet_factory("work", None, {"port": "MyHandler"}, None)
    handler.attach_transport(
        alloc,
        port_mgr,
        mem,
        find_port=lambda name: (
            SimpleNamespace(addr=port) if name == "MyHandler" else None
        ),
    )
    assert handler.handler_port == port
    lock = handler.locate_object("")
    assert lock.bptr != 0


def dospkt_missing_port_test():
    mem = MockMemory(size_kib=64)
    alloc = MemoryAlloc(mem)
    port_mgr = PortManager(alloc)
    handler = DosPktHandler("work", alloc, port=0x9999)
    handler.attach_transport(alloc, port_mgr, mem)
    expect_error(ERROR_OBJECT_NOT_FOUND, handler.locate_object, "x")


def dospkt_manager_attach_test(tmp_path):
    mem = MockMemory(size_kib=64)
    alloc = MemoryAlloc(mem)
    port_mgr = PortManager(alloc)
    server_handler = HostFileSysHandler("work", str(tmp_path))
    harness = DecoderHarness(server_handler, mem)
    port = port_mgr.create_port("H", _make_server(mem, harness.decode))

    mgr = HandlerManager(None)
    handler = DosPktHandler("work", port=port)
    mgr.register("work", handler)
    mgr.attach_packet_transport(alloc, port_mgr, mem)
    assert handler.port_mgr is port_mgr
    assert handler.reply_port != 0
    assert handler.locate_object("").bptr != 0


def dospkt_pump_test():
    # a handler that runs as its own task replies later; the pump advances it
    mem = MockMemory(size_kib=64)
    alloc = MemoryAlloc(mem)
    port_mgr = PortManager(alloc)
    pending = []

    def server(port_mgr, msg_addr):
        pending.append(msg_addr)

    port = port_mgr.create_port("deferred", server)

    def pump():
        msg_addr = pending.pop(0)
        msg = MessageStruct(mem, msg_addr)
        pkt = DosPacketStruct(mem, msg.node.name.aptr)
        pkt.res1.val = 0x42
        pkt.res2.val = 0
        port_mgr.put_msg(pkt.port.aptr, msg_addr)

    handler = DosPktHandler("work", alloc, port=port)
    handler.attach_transport(alloc, port_mgr, mem, pump=pump)
    lock = handler.locate_object("x")
    assert lock.bptr == 0x42
    assert lock.key == 0x42


def dospkt_shutdown_frees_reply_port_test(tmp_path):
    mem = MockMemory(size_kib=64)
    alloc = MemoryAlloc(mem)
    port_mgr = PortManager(alloc)
    handler = _make_handler("work", alloc, mem, port_mgr, str(tmp_path))
    reply_port = handler.reply_port
    assert port_mgr.has_port(reply_port)
    handler.shutdown()
    assert not port_mgr.has_port(reply_port)
    assert handler.reply_port == 0


def dospkt_no_reply_raises_test():
    # a handler port that never replies is a transport failure
    mem = MockMemory(size_kib=64)
    alloc = MemoryAlloc(mem)
    port_mgr = PortManager(alloc)
    port = port_mgr.create_port("silent", lambda pm, msg: None)
    handler = DosPktHandler("work", alloc, port=port)
    handler.attach_transport(alloc, port_mgr, mem)
    expect_error(ERROR_NOT_IMPLEMENTED, handler.locate_object, "x")


# --------------------------------------------------------------------------
# packets in flight: matching, bounded waits, late replies, nesting
# --------------------------------------------------------------------------


class _Server:
    """a handler port that answers when the test says so

    Packets are kept in arrival order. ``answer`` replies to one of them on
    its ``dp_Port``, like ``ReplyPkt``; ``fh_arg1`` fills the FileHandle an
    open packet names.
    """

    def __init__(self, mem, port_mgr):
        self.mem = mem
        self.port_mgr = port_mgr
        self.queue = []
        self.port = port_mgr.create_port("Server", self._receive)

    def _receive(self, port_mgr, msg_addr):
        self.queue.append(msg_addr)

    def packet(self, msg_addr):
        return DosPacketStruct(
            self.mem, MessageStruct(self.mem, msg_addr).node.name.aptr
        )

    def action(self, index=0):
        return self.packet(self.queue[index]).type.val

    def answer(self, index=0, res1=-1, res2=0, fh_arg1=None):
        msg_addr = self.queue.pop(index)
        pkt = self.packet(msg_addr)
        if fh_arg1 is not None:
            FileHandleStruct(self.mem, pkt.arg1.val << 2).fh_Args.val = fh_arg1
        pkt.res1.val = res1
        pkt.res2.val = res2
        self.port_mgr.put_msg(pkt.port.aptr, msg_addr)
        return pkt


def _inflight_env(pump=None, timeout=None):
    mem = MockMemory(size_kib=64)
    alloc = MemoryAlloc(mem)
    port_mgr = PortManager(alloc)
    server = _Server(mem, port_mgr)
    handler = DosPktHandler("work", alloc, port=server.port)
    handler.attach_transport(alloc, port_mgr, mem, pump=pump, timeout=timeout)
    baseline = alloc.available()
    return SimpleNamespace(
        mem=mem, alloc=alloc, server=server, h=handler, baseline=baseline
    )


def _abandon(env, func, *args):
    """call func with a pump that gives up at once: the packet is abandoned"""
    env.h._pump = lambda: False
    with pytest.raises(PacketTimeout):
        func(*args)
    env.h._pump = None


def dospkt_pump_false_abandons_test():
    env = _inflight_env(pump=lambda: False)
    err = expect_error(ERROR_OBJECT_IN_USE, env.h.locate_object, "x")
    assert isinstance(err, PacketTimeout)
    assert env.h.pending() == [DosAction.ACTION_LOCATE_OBJECT]


def dospkt_timeout_bounds_a_busy_pump_test():
    pumps = []
    env = _inflight_env(pump=lambda: pumps.append(1), timeout=0.05)
    started = time.monotonic()
    with pytest.raises(PacketTimeout):
        env.h.locate_object("x")
    assert time.monotonic() - started < 5
    assert pumps


def dospkt_abandoned_packet_memory_is_kept_test():
    env = _inflight_env()
    _abandon(env, env.h.locate_object, "some/long/path")
    # the packet, its message and the BSTR stay with the handler
    assert env.alloc.available() < env.baseline
    pkt = env.server.packet(env.server.queue[0])
    assert env.mem.r_bstr(pkt.arg2.val << 2) == "some/long/path"
    # the handler answers late: its writes land in memory still allocated
    env.server.answer(res1=0, res2=ERROR_OBJECT_NOT_FOUND)
    assert env.h.poll() == 1
    assert env.h.pending() == []
    assert env.alloc.available() == env.baseline


def dospkt_reply_is_matched_to_its_packet_test():
    env = _inflight_env()
    _abandon(env, env.h.locate_object, "first")
    server = env.server

    # answer the second packet first, then the abandoned one
    def pump():
        server.answer(index=1, res1=0x222)
        server.answer(index=0, res1=0x111)

    env.h._pump = pump
    lock = env.h.locate_object("second")
    assert lock.bptr == 0x222
    # the late lock 0x111 is given back with an unwaited FREE_LOCK
    assert server.action() == DosAction.ACTION_FREE_LOCK
    assert server.packet(server.queue[0]).arg1.val == 0x111
    server.answer()
    env.h.poll()
    assert env.h.pending() == []


def dospkt_late_reply_after_another_reply_test():
    # the late reply arrives after the current one: the wait must not take it
    env = _inflight_env()
    _abandon(env, env.h.locate_object, "first")
    server = env.server

    def pump():
        server.answer(index=1, res1=0x222)

    env.h._pump = pump
    assert env.h.locate_object("second").bptr == 0x222
    assert env.h.pending() == [DosAction.ACTION_LOCATE_OBJECT]
    server.answer(index=0, res1=0x111)
    env.h.poll()
    assert server.action() == DosAction.ACTION_FREE_LOCK


def dospkt_late_open_is_ended_test():
    env = _inflight_env()
    _abandon(env, env.h.find_input, "file")
    env.server.answer(res1=-1, fh_arg1=0x4711)
    env.h.poll()
    assert env.server.action() == DosAction.ACTION_END
    assert env.server.packet(env.server.queue[0]).arg1.val == 0x4711
    env.server.answer()
    env.h.poll()
    assert env.alloc.available() == env.baseline


def dospkt_late_failure_gives_nothing_back_test():
    env = _inflight_env()
    _abandon(env, env.h.locate_object, "missing")
    env.server.answer(res1=0, res2=ERROR_OBJECT_NOT_FOUND)
    env.h.poll()
    assert env.server.queue == []
    assert env.alloc.available() == env.baseline


def dospkt_fib_of_freed_lock_waits_for_reply_test():
    env = _inflight_env()
    env.h._pump = lambda: env.server.answer(res1=0x300)
    lock = env.h.locate_object("dir")
    _abandon(env, env.h.examine_object, lock)
    fib_addr = lock.fib.addr
    # FREE_LOCK is answered at once, but the FIB is still the handler's
    env.h._pump = lambda: env.server.answer(index=1)
    env.h.free_lock(lock)
    assert [s.addr for s in env.h._deferred] == [fib_addr]
    env.server.answer()  # the examine, at last
    env.h.poll()
    assert env.h._deferred == []
    assert env.alloc.available() == env.baseline


def dospkt_nested_wait_takes_outer_reply_test():
    # the pump runs guest code that calls the handler again; the handler
    # answers both packets while the inner wait runs
    env = _inflight_env()
    server = env.server
    inner = []

    def inner_pump():
        server.answer(index=0, res1=0x10)  # outer
        server.answer(index=0, res1=0x20)  # inner

    def outer_pump():
        env.h._pump = inner_pump
        inner.append(env.h.locate_object("inner").bptr)

    env.h._pump = outer_pump
    assert env.h.locate_object("outer").bptr == 0x10
    assert inner == [0x20]
    assert env.h.pending() == []


def dospkt_threads_are_serialized_test(tmp_path):
    mem = MockMemory(size_kib=256)
    alloc = MemoryAlloc(mem)
    port_mgr = PortManager(alloc)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    handler = _make_handler("work", alloc, mem, port_mgr, str(tmp_path))
    errors = []

    def worker(name):
        try:
            for _ in range(50):
                lock = handler.locate_object(name)
                assert handler.examine_object(lock).name == name
                handler.free_lock(lock)
        except BaseException as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []


def dospkt_wait_pending_test():
    env = _inflight_env()
    _abandon(env, env.h.locate_object, "x")
    env.h._pump = lambda: env.server.answer(res1=0)
    assert env.h.wait_pending(timeout=1) == []
    # a pump that gives up leaves the packet out
    _abandon(env, env.h.locate_object, "y")
    env.h._pump = lambda: False
    assert env.h.wait_pending(timeout=1) == [DosAction.ACTION_LOCATE_OBJECT]


def dospkt_shutdown_frees_abandoned_packets_test():
    env = _inflight_env()
    _abandon(env, env.h.locate_object, "x")
    reply_port_size = env.alloc.available()
    env.h.shutdown()
    assert env.h.pending() == []
    assert env.alloc.available() > reply_port_size


def dospkt_do_packet_returns_raw_results_test():
    env = _inflight_env()
    env.h._pump = lambda: env.server.answer(res1=0, res2=ERROR_OBJECT_NOT_FOUND)
    # no HandlerError: the caller gets dp_Res1/dp_Res2 as they are
    assert env.h.do_packet(DosAction.ACTION_LOCATE_OBJECT, 0, 0, -2) == (
        0,
        ERROR_OBJECT_NOT_FOUND,
    )
    after_first = env.alloc.available()
    env.h._pump = lambda: env.server.answer(res1=-1)
    assert env.h.do_packet(DosAction.ACTION_SEEK, 0x10, 0xFFFFFFFF, 0) == (-1, 0)
    # one StandardPacket carries packet after packet
    assert env.alloc.available() == after_first
    # and goes with the reply port at shutdown
    env.h.shutdown()
    assert env.alloc.available() > env.baseline


def dospkt_holds_names_abandoned_buffers_test():
    env = _inflight_env()
    buf = env.alloc.alloc_memory(64)
    _abandon(env, env.h.do_packet, DosAction.ACTION_READ, 0x10, buf.addr, 64)
    assert env.h.holds(buf.addr)
    other = env.alloc.alloc_memory(64)
    assert not env.h.holds(other.addr)
    env.server.answer(res1=64)
    env.h.poll()
    assert not env.h.holds(buf.addr)


def dospkt_put_msg_delivers_like_exec_test():
    # a handler that runs as its own task waits for its port's signal, so
    # the transport delivers through the put_msg it was given
    mem = MockMemory(size_kib=64)
    alloc = MemoryAlloc(mem)
    port_mgr = PortManager(alloc)
    server = _Server(mem, port_mgr)
    delivered = []

    def put_msg(port_addr, msg_addr):
        delivered.append(port_addr)
        port_mgr.put_msg(port_addr, msg_addr)

    handler = DosPktHandler("work", alloc, port=server.port)
    handler.attach_transport(
        alloc,
        port_mgr,
        mem,
        pump=lambda: server.answer(res1=0x40),
        put_msg=put_msg,
    )
    assert handler.locate_object("x").bptr == 0x40
    assert delivered == [server.port]


def dospkt_message_names_its_reply_port_test():
    # a handler that answers with ReplyMsg() replies to mn_ReplyPort
    env = _inflight_env()
    _abandon(env, env.h.locate_object, "x")
    msg = MessageStruct(env.mem, env.server.queue[0])
    assert msg.reply_port.aptr == env.h.reply_port
    # and is a message, as PutMsg() makes it, not a reply
    assert msg.node.type.val == NodeType.NT_MESSAGE
