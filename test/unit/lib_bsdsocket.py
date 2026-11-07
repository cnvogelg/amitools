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


def bsdsocket_hostent_layout_and_ownership_test(ctx, monkeypatch):
    monkeypatch.setattr(socket, 'gethostbyname', lambda name: '192.0.2.7')
    name = ctx.alloc.alloc_cstr('example.invalid')
    try:
        ctx.cpu.w_reg(REG_A0, name.addr)
        addr = ctx.lib.gethostbyname(ctx)
        assert addr
        # Inspect ABI offsets independently of the structure definition.
        assert ctx.mem.r32(addr + 8) == 2
        assert ctx.mem.r32(addr + 12) == 4
        assert ctx.mem.r_cstr(ctx.mem.r32(addr)) == 'example.invalid'
        aliases = ctx.mem.r32(addr + 4)
        assert aliases and ctx.mem.r32(aliases) == 0
        addresses = ctx.mem.r32(addr + 16)
        assert ctx.mem.r_block(ctx.mem.r32(addresses), 4) == b'\xc0\0\2\7'
        assert ctx.mem.r32(addresses + 4) == 0
        ctx.mem.w_cstr(name.addr, 'overwritten')
        assert ctx.mem.r_cstr(ctx.mem.r32(addr)) == 'example.invalid'
        ctx.mem.w_cstr(name.addr, 'next.invalid')
        assert ctx.lib.gethostbyname(ctx)
        assert ctx.alloc.get_memory(addr) is None
    finally:
        ctx.alloc.free_memory(name)


@pytest.mark.parametrize('failure', ['dns', 'allocation'])
def bsdsocket_hostent_failure_keeps_previous_test(ctx, monkeypatch, failure):
    monkeypatch.setattr(socket, 'gethostbyname', lambda name: '192.0.2.7')
    ctx.mem.w_cstr(ctx.buffer.addr, 'example.invalid')
    ctx.cpu.w_reg(REG_A0, ctx.buffer.addr)
    previous = ctx.lib.gethostbyname(ctx)
    before = ctx.alloc.get_free_bytes(), set(ctx.alloc.mem_objs)
    if failure == 'dns':
        monkeypatch.setattr(socket, 'gethostbyname', Mock(side_effect=socket.gaierror('dns')))
    else:
        monkeypatch.setattr(ctx.alloc, 'alloc_memory', lambda *args, **kwargs: None)
    assert ctx.lib.gethostbyname(ctx) == 0
    assert ctx.lib.hostByName.get_addr() == previous
    assert (ctx.alloc.get_free_bytes(), set(ctx.alloc.mem_objs)) == before


@pytest.mark.parametrize('kind', ['int', 'linger', 'timeval', 'ip', 'tcp', 'byte'])
def bsdsocket_option_registers_and_translation_test(ctx, monkeypatch, kind):
    import os
    import struct
    options = {
        'int': (0xffff, 4, 'SOL_SOCKET', 'SO_REUSEADDR', (1).to_bytes(4, 'big'), 1),
        'linger': (0xffff, 128, 'SOL_SOCKET', 'SO_LINGER', struct.pack('>ii', 1, 9), struct.pack('HH' if os.name == 'nt' else 'ii', 1, 9)),
        'timeval': (0xffff, 0x1006, 'SOL_SOCKET', 'SO_RCVTIMEO', struct.pack('>ii', 2, 500123), 2501 if os.name == 'nt' else struct.pack('ll', 2, 500123)),
        'ip': (0, 4, 'IPPROTO_IP', 'IP_TTL', struct.pack('>i', 20), 20),
        'tcp': (6, 1, 'IPPROTO_TCP', 'TCP_NODELAY', struct.pack('>i', 1), 1),
        'byte': (0, 10, 'IPPROTO_IP', 'IP_MULTICAST_TTL', b'\x02', 2),
    }
    level, option, level_name, option_name, data, value = options[kind]
    # Deliberately differ from Amiga constants, including BSD-like hosts.
    monkeypatch.setattr(socket, level_name, 123)
    monkeypatch.setattr(socket, option_name, 456, raising=False)
    ctx.mem.w_block(ctx.buffer.addr, data)
    ctx.cpu.w_reg(REG_D0, 0)
    ctx.cpu.w_reg(REG_D1, level)
    ctx.cpu.w_reg(REG_D2, option)
    ctx.cpu.w_reg(REG_A0, ctx.buffer.addr)
    ctx.cpu.w_reg(REG_D3, len(data))
    assert ctx.lib.setsockopt(ctx) == 0
    ctx.socket.setsockopt.assert_called_once_with(123, 456, value)


@pytest.mark.parametrize('failure,expected', [('fd',9), ('option',42),('level',42),('size',22),('null',14),('host',13)])
def bsdsocket_option_error_test(ctx, failure, expected):
    ctx.mem.w32(ctx.buffer.addr, 1)
    ctx.cpu.w_reg(REG_D0, 99 if failure == 'fd' else 0)
    ctx.cpu.w_reg(REG_D1, 99 if failure == 'level' else 0xffff)
    ctx.cpu.w_reg(REG_D2, 0x2001 if failure == 'option' else 4)
    ctx.cpu.w_reg(REG_A0, 0 if failure == 'null' else ctx.buffer.addr)
    ctx.cpu.w_reg(REG_D3, 1 if failure == 'size' else 4)
    if failure == 'host':
        ctx.socket.setsockopt.side_effect = OSError(errno.EACCES, 'denied')
    assert ctx.lib.setsockopt(ctx) == -1
    assert ctx.lib.Errno(ctx) == expected
