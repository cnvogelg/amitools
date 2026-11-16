"""Classic 32-bit BOOPSI ABI and reentrant native hook dispatch.

Classes and objects live in guest memory: native alib DoMethod/DoSuperMethod
can use them without going through a Python wrapper.
"""

import struct

from amitools.vamos.machine import REG_A0, REG_A1, REG_A2, REG_D0, Code


def call_hook(ctx, hook, obj, message, stack=None):
    entry = ctx.mem.r32(hook + 8)
    if not entry:
        return 0
    result = ctx.runner(
        Code(
            entry,
            sp=stack,
            set_regs={REG_A0: hook, REG_A2: obj, REG_A1: message},
            get_regs=[REG_D0],
        ),
        name="BOOPSI/Hook dispatcher",
    )
    if result.mach_error:
        raise result.mach_error
    return result.regs[REG_D0]


class Boopsi:
    CLASS_SIZE = 52
    OBJECT_HEADER = 12

    def __init__(self, ctx):
        self.ctx = ctx
        self.classes = {}
        self.public = {}
        self.objects = {}
        self.names = {}
        self.host_dispatchers = {}
        self.dispatcher = ctx.machine.setup_quick_trap(self._trap)
        self.root = self.make_class("rootclass", 0, 0)
        self.add_class(self.root)

    def make_class(self, name, super_class, size):
        mem, alloc = self.ctx.mem, self.ctx.alloc
        if name and name in self.public:
            return 0
        if super_class and super_class not in self.classes:
            return 0
        offset = 0
        if super_class:
            offset = mem.r16(super_class + 32) + mem.r16(super_class + 34)
        if size > 65535 or offset > 65535:
            return 0
        name_size = len(name) + 1 if name else 0
        block = alloc.alloc_memory(
            self.CLASS_SIZE + name_size, label="BOOPSI Class", except_on_failure=False
        )
        if block is None:
            return 0
        addr = block.addr
        self.classes[addr] = block
        mem.w32(addr + 8, self.dispatcher)
        mem.w32(addr + 24, super_class)
        if name:
            self.names[addr] = name
            mem.w_cstr(addr + self.CLASS_SIZE, name)
            mem.w32(addr + 28, addr + self.CLASS_SIZE)
        mem.w16(addr + 32, offset)
        mem.w16(addr + 34, size)
        if super_class:
            self._count(super_class + 40, 1)
        return addr

    def _count(self, addr, change):
        self.ctx.mem.w32(addr, self.ctx.mem.r32(addr) + change)

    def add_class(self, cls):
        if cls not in self.classes:
            return
        name = self.names.get(cls)
        if name:
            self.public[name] = cls
            self.ctx.mem.w32(cls + 48, self.ctx.mem.r32(cls + 48) | 1)

    def remove_class(self, cls):
        for name, addr in list(self.public.items()):
            if addr == cls:
                del self.public[name]
        if cls in self.classes:
            self.ctx.mem.w32(cls + 48, self.ctx.mem.r32(cls + 48) & ~1)

    def free_class(self, cls):
        if not cls:
            return 1
        mem = self.ctx.mem
        if cls not in self.classes:
            return 0
        self.remove_class(cls)
        if mem.r32(cls + 40) or mem.r32(cls + 44):
            return 0
        parent = mem.r32(cls + 24)
        if parent:
            self._count(parent + 40, -1)
        self.host_dispatchers.pop(cls, None)
        self.names.pop(cls, None)
        self.ctx.alloc.free_memory(self.classes.pop(cls))
        return 1

    def invoke(self, cls, obj, *words):
        # Put the small opSet/opGet packet on the guest stack. Disposal
        # must still work when there is no free heap memory, and recursive
        # dispatchers need independent packets.
        data = struct.pack(">" + "I" * len(words), *words)
        message = self.ctx.cpu.r_sp() - len(data)
        saved = self.ctx.mem.r_block(message, len(data))
        self.ctx.mem.w_block(message, data)
        try:
            return call_hook(self.ctx, cls, obj, message, stack=message - 4)
        finally:
            self.ctx.mem.w_block(message, saved)

    def new_object(self, cls, tags):
        if cls not in self.classes:
            return 0
        return self.invoke(cls, cls, 0x101, tags, 0)

    def method(self, obj, *words):
        if not obj:
            return 0
        return self.invoke(self.ctx.mem.r32(obj - 4), obj, *words)

    def _trap(self, opcode, address):
        cpu = self.ctx.cpu
        cls = cpu.r_reg(REG_A0)
        dispatch = self.host_dispatchers.get(cls, self.root_dispatch)
        result = dispatch(cls, cpu.r_reg(REG_A2), cpu.r_reg(REG_A1))
        cpu.w_reg(REG_D0, result)

    def root_dispatch(self, cls, obj, message):
        mem = self.ctx.mem
        method = mem.r32(message)
        # Unmodified subclass dispatchers forward to the superclass.
        parent = mem.r32(cls + 24)
        if parent:
            return call_hook(self.ctx, parent, obj, message)
        if method == 0x101:  # OM_NEW's object argument is the true class.
            if obj not in self.classes:
                return 0
            size = mem.r16(obj + 32) + mem.r16(obj + 34) + self.OBJECT_HEADER
            block = self.ctx.alloc.alloc_memory(
                size, label="BOOPSI Object", except_on_failure=False
            )
            if block is None:
                return 0
            handle = block.addr + self.OBJECT_HEADER
            mem.w32(handle - 4, obj)
            self.objects[handle] = block
            self._count(obj + 44, 1)
            return handle
        if method == 0x102:
            block = self.objects.pop(obj, None)
            if block:
                self._count(mem.r32(obj - 4) + 44, -1)
                self.ctx.alloc.free_memory(block)
        elif method == 0x105:  # OM_ADDTAIL: the hidden MinNode is the list node.
            lst = mem.r32(message + 4)
            node = obj - self.OBJECT_HEADER
            tail = mem.r32(lst + 8)
            mem.w32(node, lst + 4)
            mem.w32(node + 4, tail)
            mem.w32(tail, node)
            mem.w32(lst + 8, node)
            return 1
        elif method == 0x106:
            node = obj - self.OBJECT_HEADER
            succ, pred = mem.r32(node), mem.r32(node + 4)
            mem.w32(pred, succ)
            mem.w32(succ + 4, pred)
            return 1
        return 0

    def cleanup(self):
        # Teardown cannot call guest dispatchers after the process has exited.
        for block in self.objects.values():
            self.ctx.alloc.free_memory(block)
        self.objects.clear()
        for block in self.classes.values():
            self.ctx.alloc.free_memory(block)
        self.names.clear()
        self.classes.clear()
        self.public.clear()
        self.ctx.machine.free_quick_trap(self.dispatcher)
