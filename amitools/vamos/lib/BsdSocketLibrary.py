from amitools.vamos.libcore.impl import LibImpl
from amitools.vamos.machine.regs import REG_D0, REG_D1, REG_D2, REG_A0, REG_A1, REG_A2, REG_A3

import select
import socket as s
from amitools.vamos.astructs.astructdef import AmigaStructDef, AmigaClassDef
from amitools.vamos.astructs.astruct import AmigaStruct
from amitools.vamos.astructs.string import CSTR
from amitools.vamos.astructs.pointer import APTR_VOID
from amitools.vamos.astructs.scalar import LONG, UBYTE, UWORD, ULONG

class BsdSocketLibrary(LibImpl):

    def setup_lib(self, ctx, base_addr):
        self.alloc = ctx.alloc
        self.cnt = 0
        # track opened sockets
        self.socks = {}
        # get host by name
        self.hostByName = None

    def finish_lib(self, ctx):
        self.cnt = None

    def open_lib(self, ctx, open_cnt):
        self.cnt = open_cnt

    def close_lib(self, ctx, open_cnt):
        if self.hostByName != None:
            self.hostByName.free()
            self.hostByName = None
        self.cnt = open_cnt

    def get_version(self):
        return 4

    def get_cnt(self):
        return self.cnt

    def putSock(self, sock):
        n = 0
        while True:
            if not n in self.socks:
                self.socks[n] = sock
                return n
            n = n + 1

    def socket(self, ctx):
        # domain = ctx.cpu.r_reg(REG_D0)
        t = ctx.cpu.r_reg(REG_D1)
        if t == 1:
            t = s.SOCK_STREAM
        elif t == 2:
            t = s.SOCK_DGRAM
        else:
            t = s.SOCK_RAW
        # protocol = ctx.cpu.r_reg(REG_D2)
        sock = s.socket(s.AF_INET, t)
        if sock != None:
            return self.putSock(sock)
        return 0
    
    def CloseSocket(self, ctx):
        n = ctx.cpu.r_reg(REG_D0)
        if n in self.socks:
            sock = self.socks[n]
            sock.close()
            del self.socks[n]
                
    def gethostbyname(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_A0)
        name = ctx.mem.r_cstr(name_ptr)
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
        
        return 0

    def bind(self, ctx):
        sockn = ctx.cpu.r_reg(REG_D0)
        if not sockn in self.socks:
            return -1
        
        soalen = ctx.cpu.r_reg(REG_D1)
        if soalen < 8:
            return -2;
        
        soar = ctx.cpu.r_reg(REG_A0)
        soa = SockAddrClass(ctx.mem, soar)
        
        # no bind necessary
        if soa.sin_port.get() == 0:
            return 0
        
        sock = self.socks[sockn]
        ip = soa.sin_addr.get()
        s = self.ip2s(ip) 
        if sock.bind((s, soa.sin_port.get())) == None:
            return -3
        
        return 0

    def connect(self, ctx):
        n = ctx.cpu.r_reg(REG_D0)
        if not n in self.socks:
            return -1
        
        soalen = ctx.cpu.r_reg(REG_D1)
        if soalen < 8:
            return -2;
        
        soar = ctx.cpu.r_reg(REG_A0)
        soa = SockAddrClass(ctx.mem, soar)
        
        # port necessary
        if soa.sin_port.get() == 0:
            return -3
        
        sock = self.socks[n]
        ip = soa.sin_addr.get()
        s = self.ip2s(ip) 
        # print("connect to:", ip, s, soa.sin_port.get())
        sock.connect((s, soa.sin_port.get()))
        return 0
    
    def ip2s(self, ip):
        return str((ip >> 24) & 0xff) + "." + str((ip >> 16) & 0xff) + "." + str((ip >> 8) & 0xff) + "." + str(ip & 0xff)

    def send(self, ctx):
        n = ctx.cpu.r_reg(REG_D0)
        if not n in self.socks:
            return -1

        buf_ptr = ctx.cpu.r_reg(REG_A0)
        size = ctx.cpu.r_reg(REG_D1)
        flags = ctx.cpu.r_reg(REG_D2)
        data = ctx.mem.r_block(buf_ptr, size)
                
        sock = self.socks[n]
        return sock.send(data, flags)

    def recv(self, ctx):
        n = ctx.cpu.r_reg(REG_D0)
        if not n in self.socks:
            return -1

        buf_ptr = ctx.cpu.r_reg(REG_A0)
        size = ctx.cpu.r_reg(REG_D1)
        flags = ctx.cpu.r_reg(REG_D2)

        sock = self.socks[n]
        read = sock.recv(size, flags)
        sz = len(read)
        ctx.mem.w_block(buf_ptr, read)
        return sz

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
        (LONG, "h_addrtype"),
        (LONG, "h_length"),
        (APTR_VOID, "h_addr_list"),
        # internal
        (LONG, "h_addr"),
        (LONG, "h_addr_val"),
    ]

@AmigaClassDef
class HostEntClass(HostEntStruct):
    pass
    