from amitools.vamos.astructs import CSTR, LONG
from amitools.vamos.error import VamosInternalError
from amitools.vamos.libstructs import (
    InterruptStruct,
    MemEntryStruct,
    MemHeaderStruct,
    MemListStruct,
    NodeType,
)
from amitools.vamos.libtypes import Node
from amitools.vamos.log import log_exec
from amitools.vamos.machine.regs import REG_A0, REG_A1, REG_D0, REG_D1

from . import Alloc
from .funcbase import FuncBaseMixin
from .memheader import AllocatorMemHeader

# a MemList holds its MemEntry[] right after the header
_MEMLIST_ENTRY_OFF = MemListStruct.get_size()
_MEMENTRY_SIZE = MemEntryStruct.get_size()
_MEMHEADER_SIZE = MemHeaderStruct.get_size()
# AllocEntry() reports a failed allocation by setting the top bit of the
# returned pointer and storing the failed memory requirements below it
_ALLOCENTRY_FAILED = 0x80000000


class MemoryMixin(FuncBaseMixin):
    """exec.library memory LVOs (fd banners: memory allocation / misc)."""

    def AllocMem(self, ctx):
        size = ctx.cpu.r_reg(REG_D0)
        flags = ctx.cpu.r_reg(REG_D1)
        # label alloc
        pc = self.get_callee_pc(ctx)
        name = "AllocMem(%06x)" % pc
        mb = self.alloc.alloc_memory(size, label=name, except_on_failure=False)
        if mb is None:
            log_exec.info("AllocMem FAILED: %s size=%d flags=%08x", name, size, flags)
            return 0
        log_exec.info("AllocMem: %s -> 0x%06x %d bytes" % (mb, mb.addr, size))
        return mb.addr

    def FreeMem(self, ctx):
        size = ctx.cpu.r_reg(REG_D0)
        addr = ctx.cpu.r_reg(REG_A1)
        if addr == 0 or size == 0:
            log_exec.info("FreeMem: freeing NULL")
            return
        mb = self.alloc.get_memory(addr)
        if mb is not None:
            log_exec.info("FreeMem: 0x%06x %d bytes -> %s" % (addr, size, mb))
            self.alloc.free_memory(mb)
        else:
            raise VamosInternalError(
                "FreeMem: Unknown memory to free: ptr=%06x size=%06x" % (addr, size)
            )

    def AllocVec(self, ctx):
        size = ctx.cpu.r_reg(REG_D0)
        flags = ctx.cpu.r_reg(REG_D1)
        name = "AllocVec(@%06x)" % self.get_callee_pc(ctx)
        mb = self.alloc.alloc_memory(size, label=name, except_on_failure=False)
        if mb is None:
            log_exec.info("AllocVec FAILED: %s size=%d flags=%08x", name, size, flags)
            return 0
        log_exec.info("AllocVec: %s, flags=%08x", name, flags)
        return mb.addr

    def FreeVec(self, ctx):
        addr = ctx.cpu.r_reg(REG_A1)
        if addr == 0:
            log_exec.info("FreeVec: freeing NULL")
            return
        mb = self.alloc.get_memory(addr)
        if mb is not None:
            log_exec.info("FreeVec: %s" % mb)
            self.alloc.free_memory(mb)
        else:
            raise VamosInternalError(
                "FreeVec: Unknown memory to free: ptr=%06x" % (addr)
            )

    def AvailMem(self, ctx):
        reqments = ctx.cpu.r_reg(REG_D1)
        if reqments & 2:
            return 0  # no chip memory
        if reqments & (1 << 17):
            return self.alloc.largest_chunk()
        elif reqments & (1 << 19):
            return self.alloc.total()
        else:
            return self.alloc.available()

    # ----- memory ops -----

    def CopyMem(self, ctx):
        source = ctx.cpu.r_reg(REG_A0)
        dest = ctx.cpu.r_reg(REG_A1)
        length = ctx.cpu.r_reg(REG_D0)
        log_exec.info(
            "CopyMem: source=%06x dest=%06x len=%06x" % (source, dest, length)
        )
        ctx.mem.copy_block(source, dest, length)

    def CopyMemQuick(self, ctx):
        source = ctx.cpu.r_reg(REG_A0)
        dest = ctx.cpu.r_reg(REG_A1)
        length = ctx.cpu.r_reg(REG_D0)
        log_exec.info(
            "CopyMemQuick: source=%06x dest=%06x len=%06x" % (source, dest, length)
        )
        ctx.mem.copy_block(source, dest, length)

    def TypeOfMem(self, ctx):
        addr = ctx.cpu.r_reg(REG_A1)
        log_exec.info(
            "TypeOfMem: source=%06x -> %s" % (addr, self.alloc.is_valid_address(addr))
        )
        if self.alloc.is_valid_address(addr):
            return AllocatorMemHeader.ATTRIBUTES
        return 0

    def CacheClearU(self, ctx):
        return 0

    # ----- Allocate/Deallocate -----

    def Allocate(self, ctx):
        mh_addr = ctx.cpu.r_reg(REG_A0)
        num_bytes = ctx.cpu.r_reg(REG_D0)
        blk_addr = Alloc.allocate(ctx, mh_addr, num_bytes)
        log_exec.info("Allocate(%06x, %06x) -> %06x" % (mh_addr, num_bytes, blk_addr))
        return blk_addr

    def Deallocate(self, ctx):
        mh_addr = ctx.cpu.r_reg(REG_A0)
        blk_addr = ctx.cpu.r_reg(REG_A1)
        num_bytes = ctx.cpu.r_reg(REG_D0)
        Alloc.deallocate(ctx, mh_addr, blk_addr, num_bytes)
        log_exec.info("Deallocate(%06x, %06x, %06x)" % (mh_addr, blk_addr, num_bytes))

    # ----- fixed/entry allocations -----

    def AllocAbs(self, ctx, byteSize, location):
        # the host allocator cannot place a block at a fixed address
        log_exec.info(
            "AllocAbs(size=%d, location=%06x) -> 0: no absolute alloc",
            byteSize,
            location,
        )
        return 0

    def AllocEntry(self, ctx, entry: MemListStruct):
        num = entry.num_entries.val
        size = _MEMLIST_ENTRY_OFF + num * _MEMENTRY_SIZE
        pc = self.get_callee_pc(ctx)
        mb = self.alloc.alloc_memory(
            size, label="AllocEntry(%06x)" % pc, except_on_failure=False
        )
        if mb is None:
            return _ALLOCENTRY_FAILED | 1  # MEMF_PUBLIC
        result = MemListStruct(ctx.mem, mb.addr)
        result.num_entries.val = num
        for i in range(num):
            src = MemEntryStruct(
                ctx.mem, entry.addr + _MEMLIST_ENTRY_OFF + i * _MEMENTRY_SIZE
            )
            reqs = src.me_Un.val
            length = src.me_Length.val
            blk = self.alloc.alloc_memory(
                length, label="AllocEntry block", except_on_failure=False
            )
            if blk is None:
                # roll back the blocks we already handed out
                self._free_entries(ctx, mb.addr, i)
                self.alloc.free_memory(mb)
                return _ALLOCENTRY_FAILED | (reqs & 0x7FFFFFFF)
            dst = MemEntryStruct(
                ctx.mem, mb.addr + _MEMLIST_ENTRY_OFF + i * _MEMENTRY_SIZE
            )
            dst.me_Un.val = blk.addr
            dst.me_Length.val = length
        log_exec.info("AllocEntry(%06x, %d entries) -> %06x", entry.addr, num, mb.addr)
        return mb.addr

    def FreeEntry(self, ctx, entry: MemListStruct):
        num = entry.num_entries.val
        self._free_entries(ctx, entry.addr, num)
        mb = self.alloc.get_memory(entry.addr)
        if mb is not None:
            self.alloc.free_memory(mb)
        log_exec.info("FreeEntry(%06x, %d entries)", entry.addr, num)

    def _free_entries(self, ctx, list_addr, num):
        for i in range(num):
            me = MemEntryStruct(
                ctx.mem, list_addr + _MEMLIST_ENTRY_OFF + i * _MEMENTRY_SIZE
            )
            addr = me.me_Un.val
            if addr == 0:
                continue
            mb = self.alloc.get_memory(addr)
            if mb is not None:
                self.alloc.free_memory(mb)

    # ----- memory lists/handlers -----

    def AddMemList(self, ctx, size, attributes, pri: LONG, base, name: CSTR):
        """register an extra MemHeader in the memory list (bookkeeping only)."""
        if base == 0 or size <= _MEMHEADER_SIZE:
            log_exec.warning(
                "AddMemList(size=%d, base=%06x): invalid block", size, base
            )
            return
        mh = MemHeaderStruct(ctx.mem, base)
        mh.mh_Node.ln_Type.val = NodeType.NT_MEMORY
        mh.mh_Node.ln_Pri.val = int(pri)
        # the name is passed as a raw C string pointer (a register-bound
        # CSTR), so take its pointer value, not its (unbound) field address
        mh.mh_Node.ln_Name.aptr = name.aptr if name else 0
        mh.mh_Attributes.val = attributes
        mh.mh_Lower.aptr = base
        mh.mh_Upper.aptr = base + size
        # one free MemChunk covers the block after the header
        chunk_addr = base + _MEMHEADER_SIZE
        free = size - _MEMHEADER_SIZE
        ctx.mem.w32(chunk_addr, 0)
        ctx.mem.w32(chunk_addr + 4, free)
        mh.mh_First.aptr = chunk_addr
        mh.mh_Free.val = free
        self.exec_lib.mem_list.enqueue(Node(ctx.mem, base))
        log_exec.info(
            "AddMemList(size=%d, base=%06x, pri=%d, attrs=%08x)",
            size,
            base,
            int(pri),
            attributes,
        )

    def AddMemHandler(self, ctx, memhand: InterruptStruct):
        self.exec_lib.mem_handlers.add_tail(Node(ctx.mem, memhand.addr))
        log_exec.info("AddMemHandler(%06x)", memhand.addr)

    def RemMemHandler(self, ctx, memhand: InterruptStruct):
        Node(ctx.mem, memhand.addr).remove()
        log_exec.info("RemMemHandler(%06x)", memhand.addr)

    # ----- cache control (no-ops: the host caches are coherent) -----

    def CacheClearE(self, ctx, address, length, caches):
        log_exec.info(
            "CacheClearE(address=%06x, length=%d, caches=%08x) ignored",
            address,
            length,
            caches,
        )

    def CacheControl(self, ctx, cacheBits, cacheMask):
        old = self.exec_lib.cache_control.val
        self.exec_lib.cache_control.val = (old & ~cacheMask) | (cacheBits & cacheMask)
        log_exec.info(
            "CacheControl(bits=%08x, mask=%08x) -> old=%08x",
            cacheBits,
            cacheMask,
            old,
        )
        return old

    def CachePreDMA(self, ctx, address, length, flags):
        log_exec.info(
            "CachePreDMA(address=%06x, length=%d, flags=%08x) ignored",
            address,
            length,
            flags,
        )
        return address

    def CachePostDMA(self, ctx, address, length, flags):
        log_exec.info(
            "CachePostDMA(address=%06x, length=%d, flags=%08x) ignored",
            address,
            length,
            flags,
        )
        return address
