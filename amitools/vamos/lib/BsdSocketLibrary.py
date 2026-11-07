from amitools.vamos.libcore.impl import LibImpl
from amitools.vamos.machine.regs import REG_D0, REG_D1, REG_D2, REG_D3, REG_D4, REG_A0, REG_A1, REG_A2, REG_A3

import errno
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
    "EPERM": 1, "EINTR": 4, "EIO": 5, "EBADF": 9, "ENOMEM": 12,
    "EACCES": 13, "EFAULT": 14, "EINVAL": 22, "EMFILE": 24, "EPIPE": 32,
    "EAGAIN": 35, "EWOULDBLOCK": 35, "EINPROGRESS": 36, "EALREADY": 37,
    "ENOTSOCK": 38, "EDESTADDRREQ": 39, "EMSGSIZE": 40, "EPROTOTYPE": 41,
    "ENOPROTOOPT": 42, "EPROTONOSUPPORT": 43, "ESOCKTNOSUPPORT": 44,
    "EOPNOTSUPP": 45, "ENOTSUP": 45, "EAFNOSUPPORT": 47,
    "EADDRINUSE": 48, "EADDRNOTAVAIL": 49, "ENETDOWN": 50,
    "ENETUNREACH": 51, "ENETRESET": 52, "ECONNABORTED": 53,
    "ECONNRESET": 54, "ENOBUFS": 55, "EISCONN": 56, "ENOTCONN": 57,
    "ESHUTDOWN": 58, "ETIMEDOUT": 60, "ECONNREFUSED": 61,
    "EHOSTDOWN": 64, "EHOSTUNREACH": 65,
}
FD_SETSIZE = 256

class BsdSocketLibrary(LibImpl):

    def setup_lib(self, ctx, base_addr):
        self.alloc = ctx.alloc
        self.cnt = 0
        self.socks = {}
        self.hostByName = None
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
        if self.hostByName is not None:
            self.hostByName.free()
            self.hostByName = None

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
        name_ptr = ctx.cpu.r_reg(REG_A0)
        name = ctx.mem.r_cstr(name_ptr)
        try:
            h = s.gethostbyname(name)
            if h != None:
                ip = 0
                for x in h.split("."):
                    ip = ip << 8
                    ip += int(x)
                # print(name, h, ip)
    
                if self.hostByName == None:
                    self.hostByName = HostEntClass.alloc(self.alloc)
                            
                self.hostByName.h_name.set(name_ptr)            
                self.hostByName.h_aliases.set(0)
                self.hostByName.h_addrtype.set(0)
                self.hostByName.h_length.set(1)
                self.hostByName.h_addr_list.set(self.hostByName._addr + 20)
                self.hostByName.h_addr.set(self.hostByName._addr + 24)
                self.hostByName.h_addr_val.set(ip)
                return self.hostByName._addr
        except Exception:
            pass
        
        return 0

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
        mapping = {1: "MSG_OOB", 2: "MSG_PEEK", 4: "MSG_DONTROUTE",
                   8: "MSG_EOR", 16: "MSG_TRUNC", 32: "MSG_CTRUNC",
                   64: "MSG_WAITALL", 128: "MSG_DONTWAIT"}
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
        if size > 0x7fffffff:
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
        if size > 0x7fffffff:
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

    def listFromFdSet(self, mem, addr, sz):
        fdset = ULongULongClass(mem, addr)
        l = fdset.l0.get() + (fdset.l1.get() << 32)
        r = [] 
        for i in range (0, sz):
            if l & (1 << i) != 0 and i in self.socks:
                r.append(self.socks[i])
        return r

    def markFdSet(self, mem, lst, addr, sz):
        if addr != 0:
            s = set(lst)
            fdset = ULongULongClass(mem, addr)
            l = 0
            for i in range (0, sz):
                if i in self.socks and self.socks[i] in s:
                    l = l | (1 << i)
            #print("set ULongULong", l)
            fdset.l0.set(l)
            fdset.l1.set(l >> 32)

    def WaitSelect(self, ctx):
        sz = ctx.cpu.r_reg(REG_D0)
        rfds = ctx.cpu.r_reg(REG_A0)
        wfds = ctx.cpu.r_reg(REG_A1)
        xfds = ctx.cpu.r_reg(REG_A2)
        timevalp = ctx.cpu.r_reg(REG_A3)
        signals = ctx.cpu.r_reg(REG_D1)
        
        # clear signals
        if signals != 0:
            sig = ULongULongStruct(ctx.mem, signals)
            sig.l0.set(0)
        
        rlist, wlist, xlist = [], [], []
        if rfds != 0:
            rlist = self.listFromFdSet(ctx.mem, rfds, sz)
        if wfds != 0:
            wlist = self.listFromFdSet(ctx.mem, wfds, sz)
        if xfds != 0:
            xlist = self.listFromFdSet(ctx.mem, xfds, sz)

        r, w, x = None, None, None        
        if timevalp != 0:
            timeval = ULongULongClass(ctx.mem, timevalp)
            timeout = timeval.l0.get() + timeval.l1.get() * 1e-6
            #print("WaitSelect timeout", timeout, rlist, wlist, xlist)
            r,w,x = select.select(rlist, wlist, xlist, timeout)
        else:
            #print("WaitSelect no timeout", rlist, wlist, xlist)
            r,w,x = select.select(rlist, wlist, xlist)
        
        self.markFdSet(ctx.mem, r, rfds, sz)
        self.markFdSet(ctx.mem, w, wfds, sz)
        self.markFdSet(ctx.mem, x, xfds, sz)

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
        fd = ctx.cpu.r_reg(REG_D0)
        level = ctx.cpu.r_reg(REG_D1)
        optname = ctx.cpu.r_reg(REG_D2)
        optval_ptr = ctx.cpu.r_reg(REG_D3)
        optlen = ctx.cpu.r_reg(REG_D4)

        # Validate socket descriptor
        if fd not in self.socks:
            return -1

        sock = self.socks[fd]

        # Read option value from Amiga memory
        try:
            optval_bytes = ctx.mem.r_block(optval_ptr, optlen)
        except Exception:
            return -1

        # Convert bytes to appropriate Python type
        if optlen == 4:
            optval = int.from_bytes(optval_bytes, byteorder='big')  # Amiga is big-endian
        else:
            optval = optval_bytes  # For raw byte options

        try:
            sock.setsockopt(level, optname, optval)
            return 0
        except OSError as e:
            return -1

@AmigaStructDef
class ULongULongStruct(AmigaStruct):
    _format = [
        (ULONG, "l0"),
        (UBYTE, "l1"),
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
        (ULONG, "h_addr_val"),
    ]

@AmigaClassDef
class HostEntClass(HostEntStruct):
    pass
    