"""DosPktHandler (``handler/dospkt.py``) tests.

The transport under test is real: packets are put on a ``MsgPort`` and the
reply is taken off a reply port, both managed by the exec ``PortManager``. The
handler on the other end is a :class:`~handler_packet.LoopbackTransport`
wrapped as a port callback, so the whole shared
:class:`handler_contract.HandlerContract` runs through the packet/port
boundary (``TestDosPktContract``).
"""

from types import SimpleNamespace

import pytest
from handler_contract import (
    HandlerContract,
    expect_error,
    make_dir,
    make_file,
)
from handler_packet import LoopbackTransport

from amitools.vamos.handler import (
    DosPktHandler,
    HandlerManager,
    HostFileSysHandler,
    default_registry,
)
from amitools.vamos.handler.dospkt import packet_factory
from amitools.vamos.lib.lexec.PortManager import PortManager
from amitools.vamos.libstructs import DosPacketStruct, MessageStruct
from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc

# ERROR_ACTION_NOT_KNOWN
ERROR_ACTION_NOT_KNOWN = 209
# ERROR_OBJECT_NOT_FOUND
ERROR_OBJECT_NOT_FOUND = 205
# ERROR_NOT_IMPLEMENTED
ERROR_NOT_IMPLEMENTED = 236


def _make_server(mem, transport):
    """turn a LoopbackTransport into a PortManager message callback

    Reads the DosPacket named by the message and replies on the packet's
    ``dp_Port``, exactly like a real handler's ``ReplyPkt``.
    """

    def server(port_mgr, msg_addr):
        msg = MessageStruct(mem, msg_addr)
        pkt = DosPacketStruct(mem, msg.node.name.aptr)
        transport(pkt)
        port_mgr.put_msg(pkt.port.aptr, msg_addr)

    return server


def _make_handler(name, alloc, mem, port_mgr, root_path, pump=None):
    server_handler = HostFileSysHandler(name, root_path)
    transport = LoopbackTransport(server_handler, mem)
    port = port_mgr.create_port(name + "Handler", _make_server(mem, transport))
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
    def parent_copy_fh_test(self, env):
        # the shared contract passes a *lock* to ``copy_dir_fh`` (a step-12
        # fix); a real DOS packet can only carry an open file handle, so only
        # ``parent_fh`` is checked here
        h = env.h
        make_dir(h, "d")
        make_file(h, "d/x", b"q")
        fh = h.find_input("d/x")
        assert h.same_lock(h.parent_fh(fh), h.locate_object("d"))
        h.end(fh)


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
    transport = LoopbackTransport(server_handler, mem)
    port = port_mgr.create_port("MyHandler", _make_server(mem, transport))

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
    transport = LoopbackTransport(server_handler, mem)
    port = port_mgr.create_port("H", _make_server(mem, transport))

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
