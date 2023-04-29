from amitools.vamos.libstructs import MsgPortStruct
from amitools.vamos.error import *


class Port:
    def __init__(self, name, port_mgr, addr=None, mem=None, handler=None):
        # either use callback via handler or queue messages
        self.name = name
        self.port_mgr = port_mgr
        if mem is None:
            self.addr = addr
        else:
            self.addr = mem.addr
        self.mem = mem
        self.handler = handler
        if handler is None:
            self.queue = []
        else:
            self.queue = None

    def __str__(self):
        return "<Port:name=%s,addr=%06x>" % (self.name, self.addr)

    def put_msg(self, msg_addr):
        if self.handler:
            self.handler(self.port_mgr, msg_addr)
        else:
            self.queue.append(msg_addr)

    def has_msg(self):
        if self.queue is not None:
            return len(self.queue) > 0
        else:
            return False

    def get_msg(self):
        if self.queue is not None and len(self.queue) > 0:
            return self.queue.pop(0)
        else:
            return None


class PortManager:
    def __init__(self, alloc):
        self.alloc = alloc
        self.ports = {}

    def create_port(self, name, py_msg_handler):
        mem = self.alloc.alloc_struct(MsgPortStruct, label=name)
        port = Port(name, self, mem=mem, handler=py_msg_handler)
        addr = mem.addr
        self.ports[addr] = port
        return addr

    def free_port(self, addr):
        if addr in self.ports:
            port = self.ports[addr]
            mem = port.mem
            if mem is not None:
                self.alloc.free_struct(mem)
            else:
                raise VamosInternalError("Free non created port: %06x" % addr)
        else:
            raise VamosInternalError("Invalid Port free mem: %06x" % addr)

    def register_port(self, addr):
        name = "IntPort@%06x" % addr
        port = Port(name, self, addr=addr)
        self.ports[addr] = port

    def has_port(self, addr):
        return addr in self.ports

    def unregister_port(self, addr):
        if addr in self.ports:
            del self.ports[addr]
        else:
            raise VamosInternalError("Invalid Port remove: %06x" % addr)

    def put_msg(self, port_addr, msg_addr):
        port = self.ports[port_addr]
        port.put_msg(msg_addr)

    def has_msg(self, port_addr):
        port = self.ports[port_addr]
        return port.has_msg()

    def get_msg(self, port_addr):
        port = self.ports[port_addr]
        return port.get_msg()
