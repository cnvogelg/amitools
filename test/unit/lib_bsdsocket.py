import errno
import socket
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from amitools.vamos.label import LabelManager
from amitools.vamos.lib.BsdSocketLibrary import BsdSocketLibrary, SockAddrStruct
from amitools.vamos.machine import REG_A0, REG_A1, REG_A2, REG_A3, REG_D0, REG_D1, REG_D2, REG_D3
from amitools.vamos.machine.mock import MockMemory, MockCPU
from amitools.vamos.mem import MemoryAlloc


@pytest.fixture(params=[False, True], ids=['unlabelled', 'labelled'])
def ctx(request):
    ctx = SimpleNamespace(mem=MockMemory(), cpu=MockCPU())
    ctx.labels = LabelManager() if request.param else None
    ctx.alloc = MemoryAlloc(ctx.mem, label_mgr=ctx.labels)
    ctx.lib = BsdSocketLibrary()
    ctx.lib.setup_lib(ctx, 0)
    ctx.socket = Mock()
    ctx.lib.socks[0] = ctx.socket
    ctx.buffer = ctx.alloc.alloc_memory(64)
    ctx.address = SockAddrStruct.alloc(ctx.alloc)
    ctx.address.sin_family.val = 2
    ctx.address.sin_port.val = 0
    ctx.address.sin_addr.val = 0x7f000001
    ctx.cpu.w_reg(REG_A0, ctx.address.get_addr())
    ctx.cpu.w_reg(REG_D0, 0)
    ctx.cpu.w_reg(REG_D1, 16)
    yield ctx
    ctx.lib.finish_lib(ctx)
    ctx.alloc.free_memory(ctx.buffer)
    ctx.address.free()
    assert ctx.alloc.is_all_free()
    assert not ctx.alloc.mem_objs
    if ctx.labels:
        assert not ctx.labels.get_all_labels()


@pytest.mark.parametrize('operation', ['bind', 'connect'])
def bsdsocket_address_success_test(ctx, operation):
    getattr(ctx.socket, operation).return_value = None
    assert getattr(ctx.lib, operation)(ctx) == 0
    getattr(ctx.socket, operation).assert_called_once_with(('127.0.0.1', 0))


@pytest.mark.parametrize('operation', ['bind', 'connect'])
@pytest.mark.parametrize('failure,expected', [('fd',9),('size',22),('family',47),('null',14),('host',48)])
def bsdsocket_address_error_test(ctx, operation, failure, expected):
    if failure == 'fd':
        ctx.cpu.w_reg(REG_D0, 42)
    elif failure == 'size':
        ctx.cpu.w_reg(REG_D1, 7)
    elif failure == 'family':
        ctx.address.sin_family.val = 10
    elif failure == 'null':
        ctx.cpu.w_reg(REG_A0, 0)
    else:
        getattr(ctx.socket, operation).side_effect = OSError(errno.EADDRINUSE, 'used')
    assert getattr(ctx.lib, operation)(ctx) == -1
    assert ctx.lib.Errno(ctx) == expected


@pytest.mark.parametrize('kind,host', [(1,socket.SOCK_STREAM),(2,socket.SOCK_DGRAM),(3,socket.SOCK_RAW)])
def bsdsocket_create_type_and_protocol_test(ctx, monkeypatch, kind, host):
    create = Mock(return_value=Mock())
    monkeypatch.setattr(socket, 'socket', create)
    ctx.cpu.w_reg(REG_D0, 2)
    ctx.cpu.w_reg(REG_D1, kind)
    ctx.cpu.w_reg(REG_D2, 17)
    assert ctx.lib.socket(ctx) == 1
    create.assert_called_once_with(socket.AF_INET, host, 17)


@pytest.mark.parametrize('failure,expected', [('family',47),('type',44),('host',13)])
def bsdsocket_create_errors_test(ctx, monkeypatch, failure, expected):
    create = Mock(side_effect=PermissionError(errno.EACCES, 'denied'))
    monkeypatch.setattr(socket, 'socket', create)
    ctx.cpu.w_reg(REG_D0, 5 if failure == 'family' else 2)
    ctx.cpu.w_reg(REG_D1, 99 if failure == 'type' else 1)
    assert ctx.lib.socket(ctx) == -1
    assert ctx.lib.Errno(ctx) == expected


@pytest.mark.parametrize('size', [1, 2, 4])
def bsdsocket_errno_pointer_test(ctx, size):
    ctx.cpu.w_reg(REG_A0, ctx.buffer.addr)
    ctx.cpu.w_reg(REG_D0, size)
    assert ctx.lib.SetErrnoPtr(ctx) == 0
    ctx.cpu.w_reg(REG_D0, 999)
    assert ctx.lib.CloseSocket(ctx) == -1
    assert bytes(ctx.mem.r_block(ctx.buffer.addr, size)) == (9).to_bytes(size, 'big')


def bsdsocket_close_success_and_descriptor_reuse_test(ctx):
    assert ctx.lib.CloseSocket(ctx) == 0
    ctx.socket.close.assert_called_once()
    assert not ctx.lib.socks
    assert ctx.lib.putSock(Mock()) == 0


def bsdsocket_close_only_final_reference_test(ctx):
    ctx.lib.close_lib(ctx, 1)
    ctx.socket.close.assert_not_called()
    ctx.lib.close_lib(ctx, 0)
    ctx.lib.finish_lib(ctx)
    ctx.socket.close.assert_called_once()
    assert not ctx.lib.socks


@pytest.mark.parametrize('operation', ['send', 'recv'])
def bsdsocket_io_flags_and_count_test(ctx, monkeypatch, operation):
    monkeypatch.setattr(socket, 'MSG_DONTWAIT', 0x4000, raising=False)
    ctx.cpu.w_reg(REG_A0, ctx.buffer.addr)
    ctx.cpu.w_reg(REG_D1, 4)
    ctx.cpu.w_reg(REG_D2, 128)
    ctx.mem.w_block(ctx.buffer.addr, b'DATAguard')
    ctx.socket.send.return_value = 3
    ctx.socket.recv.return_value = b'OK'
    assert getattr(ctx.lib, operation)(ctx) == (3 if operation == 'send' else 2)
    if operation == 'send':
        ctx.socket.send.assert_called_once_with(b'DATA', 0x4000)
    else:
        ctx.socket.recv.assert_called_once_with(4, 0x4000)
        assert ctx.mem.r_block(ctx.buffer.addr, 9) == b'OKTAguard'


@pytest.mark.parametrize('operation', ['send', 'recv'])
def bsdsocket_io_errno_test(ctx, operation):
    ctx.cpu.w_reg(REG_A0, ctx.buffer.addr)
    ctx.cpu.w_reg(REG_D1, 4)
    getattr(ctx.socket, operation).side_effect = BlockingIOError(errno.EAGAIN, 'again')
    assert getattr(ctx.lib, operation)(ctx) == -1
    assert ctx.lib.Errno(ctx) == 35


@pytest.mark.parametrize('how', [0, 1, 2, 3])
def bsdsocket_shutdown_test(ctx, how):
    ctx.cpu.w_reg(REG_D1, how)
    assert ctx.lib.shutdown(ctx) == (0 if how < 3 else -1)
    if how < 3:
        ctx.socket.shutdown.assert_called_once_with((socket.SHUT_RD, socket.SHUT_WR, socket.SHUT_RDWR)[how])
    else:
        assert ctx.lib.Errno(ctx) == 22
