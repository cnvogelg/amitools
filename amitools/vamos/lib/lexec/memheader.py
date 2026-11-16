"""Publish the host allocator as an Exec MemHeader and guest free list."""

from amitools.vamos.libstructs import MemHeaderStruct, NodeType
from amitools.vamos.libtypes import Node


class AllocatorMemHeader:
    ATTRIBUTES = 1 | 4  # MEMF_PUBLIC | MEMF_FAST; no chipset DMA memory

    def __init__(self, alloc, mem_list):
        self.alloc = alloc
        self.name = alloc.alloc_cstr("vamos RAM", label="Exec memory name")
        try:
            self.header = alloc.alloc_astruct(MemHeaderStruct, label="Exec MemHeader")
        except Exception:
            alloc.free_cstr(self.name)
            raise
        header = self.header
        header.mh_Node.ln_Type.val = NodeType.NT_MEMORY
        header.mh_Node.ln_Name.aptr = self.name.addr
        header.mh_Attributes.val = self.ATTRIBUTES
        header.mh_Lower.aptr = alloc.addr
        header.mh_Upper.aptr = alloc.addr + alloc.size
        mem_list.add_tail(Node(alloc.mem, header.addr))
        alloc.change_callback = self.update
        self.update()

    def update(self):
        # Production RAM allocations are eight-byte rounded, like Exec.
        # Legacy four-byte allocators can have fragments too small for an
        # eight-byte MemChunk; never overwrite an adjacent live allocation.
        chunks = []
        chunk = self.alloc.free_first
        while chunk is not None:
            if chunk.size >= 8:
                chunks.append(chunk)
            chunk = chunk.next
        self.header.mh_Free.val = sum(chunk.size for chunk in chunks)
        self.header.mh_First.aptr = chunks[0].addr if chunks else 0
        for index, chunk in enumerate(chunks):
            next_addr = chunks[index + 1].addr if index + 1 < len(chunks) else 0
            self.alloc.mem.w32(chunk.addr, next_addr)
            self.alloc.mem.w32(chunk.addr + 4, chunk.size)

    def free(self):
        self.alloc.change_callback = None
        Node(self.alloc.mem, self.header.addr).remove()
        self.header.free()
        self.alloc.free_cstr(self.name)
