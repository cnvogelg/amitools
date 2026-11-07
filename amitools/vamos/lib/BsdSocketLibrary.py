from amitools.vamos.libcore.impl import LibImpl
from amitools.vamos.machine.regs import (
    REG_D0,
    REG_D1,
    REG_D2,
    REG_D3,
    REG_D4,
    REG_A0,
    REG_A1,
    REG_A2,
    REG_A3,
)

import errno
import os
import select
import struct
import time
import socket as s
from amitools.vamos.astructs.astructdef import AmigaStructDef, AmigaClassDef
from amitools.vamos.astructs.astruct import AmigaStruct
from amitools.vamos.astructs.string import CSTR
from amitools.vamos.astructs.pointer import APTR_VOID
from amitools.vamos.astructs.scalar import UBYTE, UWORD, ULONG

# BSD errno numbers used by the Amiga socket ABI, independent of host OS.
AMIGA_ERRNO = {
    "EPERM": 1,
    "EINTR": 4,
    "EIO": 5,
    "EBADF": 9,
    "ENOMEM": 12,
    "EACCES": 13,
    "EFAULT": 14,
    "EINVAL": 22,
    "EMFILE": 24,
    "EPIPE": 32,
    "EAGAIN": 35,
    "EWOULDBLOCK": 35,
    "EINPROGRESS": 36,
    "EALREADY": 37,
    "ENOTSOCK": 38,
    "EDESTADDRREQ": 39,
    "EMSGSIZE": 40,
    "EPROTOTYPE": 41,
    "ENOPROTOOPT": 42,
    "EPROTONOSUPPORT": 43,
    "ESOCKTNOSUPPORT": 44,
    "EOPNOTSUPP": 45,
    "ENOTSUP": 45,
    "EAFNOSUPPORT": 47,
    "EADDRINUSE": 48,
    "EADDRNOTAVAIL": 49,
    "ENETDOWN": 50,
    "ENETUNREACH": 51,
    "ENETRESET": 52,
    "ECONNABORTED": 53,
    "ECONNRESET": 54,
    "ENOBUFS": 55,
    "EISCONN": 56,
    "ENOTCONN": 57,
    "ESHUTDOWN": 58,
    "ETIMEDOUT": 60,
    "ECONNREFUSED": 61,
    "EHOSTDOWN": 64,
    "EHOSTUNREACH": 65,
}
FD_SETSIZE = 256


class BsdSocketLibrary(LibImpl):

    def setup_lib(self, ctx, base_addr):
        self.alloc = ctx.alloc
        self.cnt = 0
        self.socks = {}
        self.hostByName = None
        self._hostent_memory = None
        self.errno = 0
        self.errno_ptr = 0
        self.errno_size = 4
        self.int_mask = 1 << 12  # SIGBREAKF_CTRL_C

    def _fail(self, ctx, error):
        if isinstance(error, OSError):
            name = errno.errorcode.get(error.errno, "EIO")
            value = AMIGA_ERRNO.get(name, 5)
        else:
            value = AMIGA_ERRNO[error]
        self.errno = value
        if self.errno_ptr:
            ctx.mem.w_block(self.errno_ptr, value.to_bytes(self.errno_size, "big"))
        return -1

    def Errno(self, ctx):
        return self.errno

    def SetErrnoPtr(self, ctx):
        addr, size = ctx.cpu.r_reg(REG_A0), ctx.cpu.r_reg(REG_D0)
        if size not in (1, 2, 4):
            return self._fail(ctx, "EINVAL")
        self.errno_ptr, self.errno_size = addr, size
        return 0

    def SetSocketSignals(self, ctx):
        self.int_mask = ctx.cpu.r_reg(REG_D0)

    def getdtablesize(self, ctx):
        return FD_SETSIZE

    def _close_sockets(self):
        sockets, self.socks = self.socks, {}
        for sock in sockets.values():
            try:
                sock.close()
            except OSError:
                pass

    def finish_lib(self, ctx):
        self._close_sockets()
        self._free_hostent(ctx)
        self.cnt = 0

    def open_lib(self, ctx, open_cnt):
        self.cnt = open_cnt

    def close_lib(self, ctx, open_cnt):
        self.cnt = open_cnt
        if open_cnt == 0:
            self._close_sockets()
            self._free_hostent(ctx)

    def _free_hostent(self, ctx):
        memory, self._hostent_memory = self._hostent_memory, None
        self.hostByName = None
        if memory is not None:
            self.alloc.free_memory(memory)

    def get_version(self):
        return 4

    def get_cnt(self):
        return self.cnt

    def putSock(self, sock):
        for number in range(FD_SETSIZE):
            if number not in self.socks:
                self.socks[number] = sock
                return number
        sock.close()
        return -1

    def socket(self, ctx):
        domain = ctx.cpu.r_reg(REG_D0)
        kind = ctx.cpu.r_reg(REG_D1)
        protocol = ctx.cpu.r_reg(REG_D2)
        if domain != 2:
            return self._fail(ctx, "EAFNOSUPPORT")
        kinds = {1: s.SOCK_STREAM, 2: s.SOCK_DGRAM, 3: s.SOCK_RAW}
        if kind not in kinds:
            return self._fail(ctx, "ESOCKTNOSUPPORT")
        try:
            number = self.putSock(s.socket(s.AF_INET, kinds[kind], protocol))
            return number if number >= 0 else self._fail(ctx, "EMFILE")
        except OSError as error:
            return self._fail(ctx, error)

    def CloseSocket(self, ctx):
        number = ctx.cpu.r_reg(REG_D0)
        sock = self.socks.pop(number, None)
        if sock is None:
            return self._fail(ctx, "EBADF")
        try:
            sock.close()
        except OSError as error:
            return self._fail(ctx, error)
        return 0

    def gethostbyname(self, ctx):
        name_addr = ctx.cpu.r_reg(REG_A0)
        if not name_addr:
            self._fail(ctx, "EFAULT")
            return 0
        name = ctx.mem.r_cstr(name_addr)
        try:
            address = s.inet_aton(s.gethostbyname(name))
        except OSError:
            return 0
        # Keep the canonical public hostent prefix followed by owned,
        # NULL-terminated address and alias lists and a copied name.
        encoded_name = name.encode("latin-1") + b"\0"
        size = HostEntStruct.get_size() + 4 + len(encoded_name)
        memory = self.alloc.alloc_memory(
            size, label="bsdsocket hostent", except_on_failure=False
        )
        if memory is None:
            self._fail(ctx, "ENOMEM")
            return 0
        try:
            ctx.mem.clear_block(memory.addr, memory.size, 0)
            host = HostEntClass(ctx.mem, memory.addr)
            aliases_addr = memory.addr + HostEntStruct.get_size()
            copy_addr = aliases_addr + 4
            ctx.mem.w_block(copy_addr, encoded_name)
            host.h_name.set(copy_addr)
            host.h_aliases.set(aliases_addr)
            host.h_addrtype.val = 2  # AF_INET in the guest ABI
            host.h_length.val = 4
            host.h_addr_list.set(host.h_addr.get_addr())
            host.h_addr.val = host.h_addr_val.get_addr()
            ctx.mem.w_block(host.h_addr_val.get_addr(), address)
        except Exception:
            self.alloc.free_memory(memory)
            raise
        self._free_hostent(ctx)
        self._hostent_memory = memory
        self.hostByName = host
        return memory.addr

    def _address(self, ctx):
        if ctx.cpu.r_reg(REG_D1) < SockAddrStruct.get_size():
            self._fail(ctx, "EINVAL")
            return None
        addr = ctx.cpu.r_reg(REG_A0)
        if not addr:
            self._fail(ctx, "EFAULT")
            return None
        sockaddr = SockAddrClass(ctx.mem, addr)
        if sockaddr.sin_family.val != 2:
            self._fail(ctx, "EAFNOSUPPORT")
            return None
        return self.ip2s(sockaddr.sin_addr.val), sockaddr.sin_port.val

    def _address_operation(self, ctx, operation):
        sock = self.socks.get(ctx.cpu.r_reg(REG_D0))
        if sock is None:
            return self._fail(ctx, "EBADF")
        address = self._address(ctx)
        if address is None:
            return -1
        try:
            getattr(sock, operation)(address)
        except OSError as error:
            return self._fail(ctx, error)
        return 0

    def bind(self, ctx):
        return self._address_operation(ctx, "bind")

    def connect(self, ctx):
        return self._address_operation(ctx, "connect")

    @staticmethod
    def ip2s(ip):
        return ".".join(str((ip >> shift) & 255) for shift in (24, 16, 8, 0))

    def _flags(self, ctx, flags):
        mapping = {
            1: "MSG_OOB",
            2: "MSG_PEEK",
            4: "MSG_DONTROUTE",
            8: "MSG_EOR",
            16: "MSG_TRUNC",
            32: "MSG_CTRUNC",
            64: "MSG_WAITALL",
            128: "MSG_DONTWAIT",
        }
        if flags & ~255:
            self._fail(ctx, "EOPNOTSUPP")
            return None
        result = 0
        for bit, name in mapping.items():
            if flags & bit:
                value = getattr(s, name, None)
                if value is None:
                    self._fail(ctx, "EOPNOTSUPP")
                    return None
                result |= value
        return result

    def send(self, ctx):
        sock = self.socks.get(ctx.cpu.r_reg(REG_D0))
        if sock is None:
            return self._fail(ctx, "EBADF")
        ptr, size = ctx.cpu.r_reg(REG_A0), ctx.cpu.r_reg(REG_D1)
        if size > 0x7FFFFFFF:
            return self._fail(ctx, "EINVAL")
        if size and not ptr:
            return self._fail(ctx, "EFAULT")
        flags = self._flags(ctx, ctx.cpu.r_reg(REG_D2))
        if flags is None:
            return -1
        data = bytes(ctx.mem.r_block(ptr, size)) if size else b""
        try:
            return sock.send(data, flags)
        except OSError as error:
            return self._fail(ctx, error)

    def recv(self, ctx):
        sock = self.socks.get(ctx.cpu.r_reg(REG_D0))
        if sock is None:
            return self._fail(ctx, "EBADF")
        ptr, size = ctx.cpu.r_reg(REG_A0), ctx.cpu.r_reg(REG_D1)
        if size > 0x7FFFFFFF:
            return self._fail(ctx, "EINVAL")
        if size and not ptr:
            return self._fail(ctx, "EFAULT")
        flags = self._flags(ctx, ctx.cpu.r_reg(REG_D2))
        if flags is None:
            return -1
        try:
            data = sock.recv(size, flags)
        except OSError as error:
            return self._fail(ctx, error)
        if data:
            ctx.mem.w_block(ptr, data)
        return len(data)

    def listFromFdSet(self, mem, addr, count):
        result = []
        for base in range(0, count, 32):
            word = mem.r32(addr + (base // 32) * 4)
            for bit in range(min(32, count - base)):
                if word & (1 << bit):
                    number = base + bit
                    if number not in self.socks:
                        raise OSError(errno.EBADF, "unallocated guest socket")
                    result.append(self.socks[number])
        return result

    def markFdSet(self, mem, ready, addr, count):
        if not addr:
            return
        ready = set(ready)
        for base in range(0, count, 32):
            requested = mem.r32(addr + (base // 32) * 4)
            word = 0
            for bit in range(min(32, count - base)):
                if requested & (1 << bit) and self.socks.get(base + bit) in ready:
                    word |= 1 << bit
            mem.w32(addr + (base // 32) * 4, word)

    def WaitSelect(self, ctx):
        count = ctx.cpu.r_reg(REG_D0)
        pointers = [ctx.cpu.r_reg(reg) for reg in (REG_A0, REG_A1, REG_A2)]
        timeout_addr, signal_addr = ctx.cpu.r_reg(REG_A3), ctx.cpu.r_reg(REG_D1)
        if count > FD_SETSIZE:
            return self._fail(ctx, "EINVAL")
        timeout = None
        if timeout_addr:
            seconds, micros = ctx.mem.r32(timeout_addr), ctx.mem.r32(timeout_addr + 4)
            if seconds > 0x7FFFFFFF or micros >= 1000000:
                return self._fail(ctx, "EINVAL")
            timeout = seconds + micros / 1000000.0
        signal_mask = ctx.mem.r32(signal_addr) if signal_addr else 0
        if signal_addr:
            ctx.mem.w32(signal_addr, 0)
        try:
            lists = [
                self.listFromFdSet(ctx.mem, ptr, count) if ptr else []
                for ptr in pointers
            ]
        except OSError as error:
            return self._fail(ctx, error)
        executive = getattr(ctx, "exec_lib", None)
        if executive is None and getattr(ctx, "lib_mgr", None) is not None:
            vlib = ctx.lib_mgr.get_vlib_by_name("exec.library")
            executive = vlib.get_impl() if vlib is not None else None
        signal_func = getattr(executive, "signal_func", None)
        task = signal_func.get_my_sched_task() if signal_func else None
        deadline = time.monotonic() + timeout if timeout is not None else None
        ready = ([], [], [])
        while True:
            # Only consume signals requested by this call or the configured
            # interrupt mask. Other pending signals belong to their callers.
            got = (
                signal_func.set_signal(0, signal_mask | self.int_mask)
                if signal_func
                else 0
            )
            got &= signal_mask | self.int_mask
            if got:
                if signal_addr:
                    ctx.mem.w32(signal_addr, got & signal_mask)
                for ptr in pointers:
                    self.markFdSet(ctx.mem, [], ptr, count)
                if got & self.int_mask:
                    return self._fail(ctx, "EINTR")
                return 0
            remaining = (
                max(0.0, deadline - time.monotonic()) if deadline is not None else None
            )
            # A bounded host wait lets other guest tasks and signals run.
            delay = min(remaining, 0.01) if remaining is not None else 0.01
            try:
                if any(lists):
                    ready = select.select(*lists, delay)
                elif delay:
                    time.sleep(delay)
            except OSError as error:
                return self._fail(ctx, error)
            except ValueError:
                return self._fail(ctx, "EBADF")
            if any(ready) or (deadline is not None and time.monotonic() >= deadline):
                break
            if task is not None:
                task.reschedule()
        for ptr, values in zip(pointers, ready):
            self.markFdSet(ctx.mem, values, ptr, count)
        return sum(map(len, ready))

    def shutdown(self, ctx):
        sock = self.socks.get(ctx.cpu.r_reg(REG_D0))
        if sock is None:
            return self._fail(ctx, "EBADF")
        how = ctx.cpu.r_reg(REG_D1)
        if how not in (0, 1, 2):
            return self._fail(ctx, "EINVAL")
        try:
            sock.shutdown((s.SHUT_RD, s.SHUT_WR, s.SHUT_RDWR)[how])
        except OSError as error:
            return self._fail(ctx, error)
        return 0

    def setsockopt(self, ctx):
        sock = self.socks.get(ctx.cpu.r_reg(REG_D0))
        if sock is None:
            return self._fail(ctx, "EBADF")
        level, option = ctx.cpu.r_reg(REG_D1), ctx.cpu.r_reg(REG_D2)
        address, size = ctx.cpu.r_reg(REG_A0), ctx.cpu.r_reg(REG_D3)
        socket_options = {
            0x0001: ("SO_DEBUG", "int"),
            0x0004: ("SO_REUSEADDR", "int"),
            0x0008: ("SO_KEEPALIVE", "int"),
            0x0010: ("SO_DONTROUTE", "int"),
            0x0020: ("SO_BROADCAST", "int"),
            0x0040: ("SO_USELOOPBACK", "int"),
            0x0080: ("SO_LINGER", "linger"),
            0x0100: ("SO_OOBINLINE", "int"),
            0x0200: ("SO_REUSEPORT", "int"),
            0x1001: ("SO_SNDBUF", "int"),
            0x1002: ("SO_RCVBUF", "int"),
            0x1003: ("SO_SNDLOWAT", "int"),
            0x1004: ("SO_RCVLOWAT", "int"),
            0x1005: ("SO_SNDTIMEO", "timeval"),
            0x1006: ("SO_RCVTIMEO", "timeval"),
        }
        ip_options = {
            1: ("IP_OPTIONS", "raw"),
            2: ("IP_HDRINCL", "int"),
            3: ("IP_TOS", "int"),
            4: ("IP_TTL", "int"),
            5: ("IP_RECVOPTS", "int"),
            6: ("IP_RECVRETOPTS", "int"),
            7: ("IP_RECVDSTADDR", "int"),
            8: ("IP_RETOPTS", "raw"),
            9: ("IP_MULTICAST_IF", "address"),
            10: ("IP_MULTICAST_TTL", "byte"),
            11: ("IP_MULTICAST_LOOP", "byte"),
            12: ("IP_ADD_MEMBERSHIP", "membership"),
            13: ("IP_DROP_MEMBERSHIP", "membership"),
        }
        if level == 0xFFFF:
            host_level, table = s.SOL_SOCKET, socket_options
        elif level == 6:
            host_level, table = s.IPPROTO_TCP, {
                1: ("TCP_NODELAY", "int"),
                2: ("TCP_MAXSEG", "int"),
            }
        elif level == 0:
            host_level, table = s.IPPROTO_IP, ip_options
        else:
            return self._fail(ctx, "ENOPROTOOPT")
        name, kind = table.get(option, (None, None))
        host_option = getattr(s, name, None) if name else None
        if host_option is None:
            return self._fail(ctx, "ENOPROTOOPT")
        expected = {
            "int": (4,),
            "linger": (8,),
            "timeval": (8,),
            "address": (4,),
            "membership": (8,),
            "byte": (1, 4),
        }
        if size > 0x7FFFFFFF or (kind in expected and size not in expected[kind]):
            return self._fail(ctx, "EINVAL")
        if size and not address:
            return self._fail(ctx, "EFAULT")
        data = bytes(ctx.mem.r_block(address, size)) if size else b""
        value = data
        if kind in ("int", "byte"):
            value = int.from_bytes(data, "big", signed=kind == "int")
        elif kind == "linger":
            enabled, seconds = struct.unpack(">ii", data)
            if (
                enabled < 0
                or seconds < 0
                or (os.name == "nt" and max(enabled, seconds) > 65535)
            ):
                return self._fail(ctx, "EINVAL")
            value = struct.pack("HH" if os.name == "nt" else "ii", enabled, seconds)
        elif kind == "timeval":
            seconds, micros = struct.unpack(">ii", data)
            if seconds < 0 or not 0 <= micros < 1000000:
                return self._fail(ctx, "EINVAL")
            value = (
                (seconds * 1000 + (micros + 999) // 1000)
                if os.name == "nt"
                else struct.pack("ll", seconds, micros)
            )
        try:
            sock.setsockopt(host_level, host_option, value)
        except OSError as error:
            return self._fail(ctx, error)
        return 0


@AmigaStructDef
class ULongULongStruct(AmigaStruct):
    _format = [
        (ULONG, "l0"),
        (ULONG, "l1"),
    ]


@AmigaClassDef
class ULongULongClass(ULongULongStruct):
    pass


@AmigaStructDef
class SockAddrStruct(AmigaStruct):
    _format = [
        (UBYTE, "sin_len"),
        (UBYTE, "sin_family"),
        (UWORD, "sin_port"),
        (ULONG, "sin_addr"),
        (ULONG, "sin_zero0"),
        (ULONG, "sin_zero1"),
    ]


@AmigaClassDef
class SockAddrClass(SockAddrStruct):
    pass


@AmigaStructDef
class HostEntStruct(AmigaStruct):
    _format = [
        (CSTR, "h_name"),
        (APTR_VOID, "h_aliases"),
        (ULONG, "h_addrtype"),
        (ULONG, "h_length"),
        (APTR_VOID, "h_addr_list"),
        # internal
        (ULONG, "h_addr"),
        (ULONG, "h_addr_end"),
        (ULONG, "h_addr_val"),
    ]


@AmigaClassDef
class HostEntClass(HostEntStruct):
    pass
