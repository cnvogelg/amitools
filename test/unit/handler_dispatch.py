"""Handler dispatcher (``handler/dispatch.py``) tests.

A dispatcher bundles a handler's message port with the decoder that serves it:
a packet put on the port is decoded onto that handler and the reply is posted
back to the packet's reply port. The manager injects one dispatcher per handler.
"""

from types import SimpleNamespace

from handler_decode import (
    _INFO_ADDR,
    _PATH_ADDR,
    _bstr,
    DecoderHarness,
    RecordingHandler,
)

from amitools.vamos.handler import (
    HandlerDispatcher,
    HandlerManager,
    default_registry,
)
from amitools.vamos.lib.dos.action import DosAction
from amitools.vamos.lib.lexec.PortManager import PortManager
from amitools.vamos.libstructs import DosPacketStruct, InfoDataStruct, MessageStruct
from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc

DOSFALSE = 0
DOSTRUE = -1
ERROR_INVALID_LOCK = 211

_MSG_ADDR = 0x100
_PKT_ADDR = 0x200
_REPLY_PORT = 0x300


def _make_msg(mem, reply_port=_REPLY_PORT):
    msg = MessageStruct(mem, _MSG_ADDR)
    msg.node.name.aptr = _PKT_ADDR
    pkt = DosPacketStruct(mem, _PKT_ADDR)
    pkt.port.aptr = reply_port
    return msg, pkt


def _make_dispatcher(mem, port_mgr, handler):
    harness = DecoderHarness(handler, mem)
    return HandlerDispatcher(port_mgr, mem, handler.name + " handler", harness.decoder)


def handler_dispatch_put_msg_test():
    mem = MockMemory(size_kib=64)
    alloc = MemoryAlloc(mem)
    port_mgr = PortManager(alloc)
    handler = RecordingHandler("work")
    dispatcher = _make_dispatcher(mem, port_mgr, handler)
    assert port_mgr.has_port(dispatcher.port)

    msg, pkt = _make_msg(mem)
    pkt.type.val = DosAction.ACTION_DISK_INFO
    pkt.arg1.val = _INFO_ADDR

    dispatcher.put_msg(port_mgr, msg.addr)

    # the packet was decoded onto the handler and answered
    assert handler.calls == [("disk_info", None)]
    assert pkt.res1.val == DOSTRUE
    assert pkt.res2.val == 0
    info = InfoDataStruct(mem, _INFO_ADDR)
    assert info.id_NumBlocks.val == 42
    # the reply message was posted to the reply port
    assert port_mgr.has_port(_REPLY_PORT)
    assert port_mgr.get_msg(_REPLY_PORT) == msg.addr

    dispatcher.free()
    assert not port_mgr.has_port(dispatcher.port)
    assert alloc.is_all_free()


def handler_dispatch_routes_to_own_handler_test():
    mem = MockMemory(size_kib=64)
    alloc = MemoryAlloc(mem)
    port_mgr = PortManager(alloc)
    work = RecordingHandler("work")
    ram = RecordingHandler("ram")
    work_disp = _make_dispatcher(mem, port_mgr, work)
    ram_disp = _make_dispatcher(mem, port_mgr, ram)
    # every handler gets its own port
    assert work_disp.port != ram_disp.port

    # a ZERO-lock path packet reaches the port's own handler
    msg, pkt = _make_msg(mem)
    pkt.type.val = DosAction.ACTION_DELETE_OBJECT
    pkt.arg2.val = _bstr(mem, "x", _PATH_ADDR)
    work_disp.put_msg(port_mgr, msg.addr)
    assert work.calls == [("delete_object", "x")]
    assert ram.calls == []

    # the same packet on the other port reaches the other handler
    pkt.res1.val = 0
    ram_disp.put_msg(port_mgr, msg.addr)
    assert ram.calls == [("delete_object", "x")]

    work_disp.free()
    ram_disp.free()
    assert alloc.is_all_free()


def handler_dispatch_foreign_handle_test():
    """a handle owned by another handler is rejected by the decoder"""
    mem = MockMemory(size_kib=64)
    alloc = MemoryAlloc(mem)
    port_mgr = PortManager(alloc)
    work = RecordingHandler("work")
    other = RecordingHandler("other")
    harness = DecoderHarness(work, mem)
    dispatcher = HandlerDispatcher(port_mgr, mem, "work handler", harness.decoder)

    # register a handle owned by 'other' in the (shared) handle table
    fh_id = harness._register_file(other, other.file, "other:f")

    msg, pkt = _make_msg(mem)
    pkt.type.val = DosAction.ACTION_READ
    pkt.arg1.val = fh_id
    pkt.arg2.val = 0x800
    pkt.arg3.val = 4

    dispatcher.put_msg(port_mgr, msg.addr)

    assert pkt.res1.val == DOSFALSE
    assert pkt.res2.val == ERROR_INVALID_LOCK
    assert other.calls == []

    dispatcher.free()
    assert alloc.is_all_free()


def handler_dispatch_manager_test():
    mem = MockMemory(size_kib=64)
    alloc = MemoryAlloc(mem)
    port_mgr = PortManager(alloc)
    mgr = HandlerManager(SimpleNamespace(), registry=default_registry())
    handler = RecordingHandler("work")
    mgr.register("work", handler)

    def make_decoder(h):
        return DecoderHarness(h, mem).decoder

    mgr.attach_dispatchers(port_mgr, mem, make_decoder)
    dispatcher = handler.dispatcher
    assert dispatcher is not None
    assert mgr.get_dispatcher("work") is dispatcher
    assert mgr.get_dispatcher("unknown") is None
    assert port_mgr.has_port(dispatcher.port)

    # attaching again is a no-op
    mgr.attach_dispatchers(port_mgr, mem, make_decoder)
    assert handler.dispatcher is dispatcher

    mgr.detach_dispatchers()
    assert handler.dispatcher is None
    assert not port_mgr.has_port(dispatcher.port)
    assert alloc.is_all_free()
