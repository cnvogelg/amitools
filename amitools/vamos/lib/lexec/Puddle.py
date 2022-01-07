from amitools.vamos.log import log_exec
from amitools.vamos.error import *
from amitools.vamos.mem import MemoryAlloc


class Puddle:
    def __init__(self, mem, alloc, label_mgr, name, size):
        self.alloc = alloc
        self.chunks = None
        self.label_mgr = label_mgr
        self.mem = mem
        self.size = size
        self.mem_obj = self.alloc.alloc_memory(size, label=name)
        self.chunks = MemoryAlloc(self.mem, self.mem_obj.addr, size, label_mgr)

    def __del__(self):
        if self.mem_obj != None:
            if self.label_mgr:
                self.label_mgr.delete_labels_within(self.mem_obj.addr, self.size)
            self.chunks = None
            self.alloc.free_memory(self.mem_obj)
            self.mem_obj = None

    def AllocPooled(self, name, size):
        return self.chunks.alloc_memory(size, label=name)

    def FreePooled(self, addr, size):
        mem = self.chunks.get_memory(addr)
        if mem != None:
            if mem.size == size:
                self.chunks.free_memory(mem)
            else:
                raise VamosInternalError(
                    "release size %d for memory chunk %s != reserved size %s"
                    % (size, mem, mem.size)
                )
        else:
            raise VamosInternalError("memory at 0x%0x not recorded in puddle" % addr)

    def contains(self, addr, size):
        if self.chunks.is_valid_address(addr):
            return True
        return False
