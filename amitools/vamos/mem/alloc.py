from amitools.vamos.error import *
from amitools.vamos.log import log_mem_alloc
from amitools.vamos.label import LabelRange, LabelStruct, LabelLib
from amitools.vamos.astructs import AccessStruct


class Memory:
    def __init__(self, addr, size, label, access):
        self.addr = addr
        self.size = size
        self.label = label
        self.access = access

    def __str__(self):
        if self.label != None:
            return str(self.label)
        else:
            return "[@%06x +%06x %06x]" % (self.addr, self.size, self.addr + self.size)


class MemoryChunk:
    def __init__(self, addr, size):
        self.addr = addr
        self.size = size
        self.next = None
        self.prev = None

    def __str__(self):
        end = self.addr + self.size
        return "[@%06x +%06x %06x]" % (self.addr, self.size, end)

    def does_fit(self, size):
        """check if new size would fit into chunk
        return < 0 if it does not fit, 0 for exact fit, > 0 n wasted bytes
        """
        return self.size - size


class MemoryAlloc:
    def __init__(self, mem, addr=0, size=0, label_mgr=None):
        """mem is a interface.
        setup allocator starting at addr with size bytes.
        if label_mgr is set then labels are created for allocations.
        """
        # if no size is specified then take mem total
        if size == 0:
            size = mem.get_ram_size_kib() * 1024
            size -= addr
        # if addr == 0 skip 0 to never return NULL pointer!
        if addr == 0:
            addr = 4
            size -= 4

        self.mem = mem
        self.addr = addr
        self.size = size
        self.label_mgr = label_mgr
        # compat link
        self.access = mem

        self.addrs = {}
        self.mem_objs = {}

        # init free list
        self.free_bytes = size
        self.free_first = MemoryChunk(addr, self.free_bytes)
        self.free_entries = 1

    @classmethod
    def for_machine(cls, machine):
        return cls(
            machine.get_mem(),
            addr=machine.get_ram_begin(),
            label_mgr=machine.get_label_mgr(),
        )

    def get_mem(self):
        return self.mem

    def get_addr(self):
        return self.addr

    def get_size(self):
        return self.size

    def get_label_mgr(self):
        return self.label_mgr

    def get_free_bytes(self):
        return self.free_bytes

    def is_all_free(self):
        return self.size == self.free_bytes

    def _find_best_chunk(self, size):
        """find best chunk that could take the given alloc
        return: index of chunk in free list or -1 if none found + bytes left in chunk
        """
        chunk = self.free_first
        while chunk != None:
            left = chunk.does_fit(size)
            # exact match
            if left == 0:
                return (chunk, 0)
            # potential candidate: has some bytes left
            elif left > 0:
                # Don't make such a hassle. Return the first one that fits.
                # This function takes too much time.
                return (chunk, left)
            chunk = chunk.next
        # nothing found?
        return (None, -1)

    def _remove_chunk(self, chunk):
        next = chunk.next
        prev = chunk.prev
        if chunk == self.free_first:
            self.free_first = next
        if next != None:
            next.prev = prev
        if prev != None:
            prev.next = next
        self.free_entries -= 1

    def _replace_chunk(self, old_chunk, new_chunk):
        next = old_chunk.next
        prev = old_chunk.prev
        if old_chunk == self.free_first:
            self.free_first = new_chunk
        if next != None:
            next.prev = new_chunk
        if prev != None:
            prev.next = new_chunk
        new_chunk.next = next
        new_chunk.prev = prev

    def _insert_chunk(self, chunk):
        cur = self.free_first
        last = None
        addr = chunk.addr
        while cur != None:
            # fits right before
            if addr < cur.addr:
                break
            last = cur
            cur = cur.next
        # inster after last but before cur
        if last == None:
            self.free_first = chunk
        else:
            last.next = chunk
            chunk.prev = last
        if cur != None:
            chunk.next = cur
            cur.prev = chunk
        self.free_entries += 1

    def _merge_chunk(self, a, b):
        # can we merge?
        if a.addr + a.size == b.addr:
            chunk = MemoryChunk(a.addr, a.size + b.size)
            prev = a.prev
            if prev != None:
                prev.next = chunk
                chunk.prev = prev
            next = b.next
            if next != None:
                next.prev = chunk
                chunk.next = next
            if self.free_first == a:
                self.free_first = chunk
            self.free_entries -= 1
            return chunk
        else:
            return None

    def _stat_info(self):
        num_allocs = len(self.addrs)
        return "(free %06x #%d) (allocs #%d)" % (
            self.free_bytes,
            self.free_entries,
            num_allocs,
        )

    def alloc_mem(self, size, except_on_fail=True):
        """allocate memory and return addr or 0 if no more memory"""
        # align size to 4 bytes
        size = (size + 3) & ~3
        # find best free chunk
        chunk, left = self._find_best_chunk(size)
        # out of memory?
        if chunk == None:
            if except_on_fail:
                self.dump_orphans()
                log_mem_alloc.error("[alloc: NO MEMORY for %06x bytes]" % size)
                raise VamosInternalError("[alloc: NO MEMORY for %06x bytes]" % size)
            return 0
        # remove chunk from free list
        # is something left?
        addr = chunk.addr
        if left == 0:
            self._remove_chunk(chunk)
        else:
            left_chunk = MemoryChunk(addr + size, left)
            self._replace_chunk(chunk, left_chunk)
        # add to valid allocs map
        self.addrs[addr] = size
        self.free_bytes -= size
        # erase memory
        self.mem.clear_block(addr, size, 0)
        log_mem_alloc.info(
            "[alloc @%06x-%06x: %06x bytes] %s",
            addr,
            addr + size,
            size,
            self._stat_info(),
        )
        if addr % 4:
            raise VamosInternalError(
                "Memory pool is invalid, return address not aligned by a long word"
            )
        return addr

    def free_mem(self, addr, size):
        # first check if its a right alloc
        if addr not in self.addrs:
            raise VamosInternalError("Invalid Free'd Memory at %06x" % addr)
        # align size to 4 bytes
        size = (size + 3) & ~3
        real_size = self.addrs[addr]
        assert size == real_size
        # remove from valid allocs
        del self.addrs[addr]
        # create a new free chunk
        chunk = MemoryChunk(addr, real_size)
        self._insert_chunk(chunk)

        # try to merge with prev/next
        prev = chunk.prev
        if prev != None:
            new_chunk = self._merge_chunk(prev, chunk)
            if new_chunk != None:
                log_mem_alloc.debug(
                    "merged: %s + this=%s -> %s", prev, chunk, new_chunk
                )
                chunk = new_chunk
        next = chunk.next
        if next != None:
            new_chunk = self._merge_chunk(chunk, next)
            if new_chunk != None:
                log_mem_alloc.debug(
                    "merged: this=%s + %s -> %s", chunk, next, new_chunk
                )

        # correct free bytes
        self.free_bytes += size
        num_allocs = len(self.addrs)
        log_mem_alloc.info(
            "[free  @%06x-%06x: %06x bytes] %s",
            addr,
            addr + size,
            size,
            self._stat_info(),
        )

    def get_range_by_addr(self, addr):
        if addr in self.addrs:
            return self.addrs[addr]
        else:
            return None

    def dump_mem_state(self):
        chunk = self.free_first
        num = 0
        while chunk != None:
            log_mem_alloc.debug("dump #%02d: %s" % (num, chunk))
            num += 1
            chunk = chunk.next

    def _dump_orphan(self, addr, size):
        log_mem_alloc.warning("orphan: [@%06x +%06x %06x]" % (addr, size, addr + size))
        if self.label_mgr:
            labels = self.label_mgr.get_intersecting_labels(addr, size)
            for l in labels:
                log_mem_alloc.warning("-> %s", l)

    def dump_orphans(self):
        last = self.free_first
        # orphan at begin?
        if last.addr != self.addr:
            addr = self.addr
            size = last.addr - addr
            self._dump_orphan(addr, size)
        # walk along free list
        cur = last.next
        while cur != None:
            addr = last.addr + last.size
            size = cur.addr - addr
            self._dump_orphan(addr, size)
            last = cur
            cur = cur.next
        # orphan at end?
        addr = last.addr + last.size
        end = self.addr + self.size
        if addr != end:
            self._dump_orphan(addr, end - addr)

    # ----- convenience functions with label creation -----

    def get_memory(self, addr):
        if addr in self.mem_objs:
            return self.mem_objs[addr]
        else:
            return None

    # memory
    def alloc_memory(self, size, label=None, except_on_failure=True):
        addr = self.alloc_mem(size, except_on_failure)
        if addr == 0:
            return None
        if label and self.label_mgr:
            label_obj = LabelRange(label, addr, size)
            self.label_mgr.add_label(label_obj)
        else:
            label_obj = None
        mem = Memory(addr, size, label_obj, self.mem)
        log_mem_alloc.info("alloc memory: %s", mem)
        self.mem_objs[addr] = mem
        return mem

    def free_memory(self, mem):
        log_mem_alloc.info("free memory: %s", mem)
        if mem.label != None:
            self.label_mgr.remove_label(mem.label)
        self.free_mem(mem.addr, mem.size)
        del self.mem_objs[mem.addr]

    # struct
    def alloc_struct(self, struct, size=None, label=None):
        if size is None:
            size = struct.get_size()
        addr = self.alloc_mem(size)
        if label and self.label_mgr:
            label_obj = LabelStruct(label, addr, struct)
            self.label_mgr.add_label(label_obj)
        else:
            label_obj = None
        access = AccessStruct(self.mem, struct, addr)
        mem = Memory(addr, size, label_obj, access)
        log_mem_alloc.info("alloc struct: %s", mem)
        self.mem_objs[addr] = mem
        return mem

    def map_struct(self, addr, struct, label=None):
        size = struct.get_size()
        access = AccessStruct(self.mem, struct, addr)
        if label and self.label_mgr:
            label_obj = LabelStruct(label, addr, struct)
            self.label_mgr.add_label(label_obj)
        else:
            label_obj = None
        mem = Memory(addr, size, label_obj, access)
        log_mem_alloc.info("map struct: %s", mem)
        return mem

    def free_struct(self, mem):
        log_mem_alloc.info("free struct: %s", mem)
        if self.label_mgr:
            self.label_mgr.remove_label(mem.label)
        self.free_mem(mem.addr, mem.size)
        del self.mem_objs[mem.addr]

    # library
    def alloc_lib(self, lib_struct, pos_size=0, neg_size=0, fd=None, label=None):
        if pos_size == 0:
            pos_size = lib_struct.get_size()
        # round neg_size to multiple of four
        neg_size = (neg_size + 3) & ~3
        size = neg_size + pos_size
        # alloc full size
        addr = self.alloc_mem(size)
        base_addr = addr + neg_size
        if label and self.label_mgr:
            label_obj = LabelLib(label, base_addr, neg_size, pos_size, lib_struct, fd)
            self.label_mgr.add_label(label_obj)
        else:
            label_obj = None
        access = AccessStruct(self.mem, lib_struct, base_addr)
        mem = Memory(addr, size, label_obj, access)
        log_mem_alloc.info("alloc lib: %s", mem)
        self.mem_objs[addr] = mem
        return mem

    def free_lib(self, mem):
        log_mem_alloc.info("free lib: %s", mem)
        if self.label_mgr:
            self.label_mgr.remove_label(mem.label)
        self.free_mem(mem.addr, mem.size)
        del self.mem_objs[mem.addr]

    # cstr
    def alloc_cstr(self, cstr, label=None):
        size = len(cstr) + 1
        addr = self.alloc_mem(size)
        if label and self.label_mgr:
            label_obj = LabelRange(label, addr, size)
            self.label_mgr.add_label(label_obj)
        else:
            label_obj = None
        self.mem.w_cstr(addr, cstr)
        mem = Memory(addr, size, label_obj, self.mem)
        log_mem_alloc.info("alloc c_str: %s", mem)
        self.mem_objs[addr] = mem
        return mem

    def free_cstr(self, mem):
        log_mem_alloc.info("free c_str: %s", mem)
        if self.label_mgr:
            self.label_mgr.remove_label(mem.label)
        self.free_mem(mem.addr, mem.size)
        del self.mem_objs[mem.addr]

    # bstr
    def alloc_bstr(self, bstr, label=None):
        size = len(bstr) + 2  # front: count, end: extra zero for safety
        addr = self.alloc_mem(size)
        if label and self.label_mgr:
            label_obj = LabelRange(label, addr, size)
            self.label_mgr.add_label(label_obj)
        else:
            label_obj = None
        self.mem.w_bstr(addr, bstr)
        mem = Memory(addr, size, label_obj, self.mem)
        log_mem_alloc.info("alloc b_str: %s", mem)
        self.mem_objs[addr] = mem
        return mem

    def free_bstr(self, mem):
        log_mem_alloc.info("free b_str: %s", mem)
        if self.label_mgr:
            self.label_mgr.remove_label(mem.label)
        self.free_mem(mem.addr, mem.size)
        del self.mem_objs[mem.addr]

    def is_valid_address(self, addr):
        if addr >= self.addr and addr < self.addr + self.size:
            return True
        return False

    def total(self):
        return self.size

    def available(self):
        free = 0
        chunk = self.free_first
        while chunk != None:
            free += chunk.size
            chunk = chunk.next
        return free

    def largest_chunk(self):
        largest = 0
        chunk = self.free_first
        while chunk != None:
            if chunk.size > largest:
                largest = chunk.size
            chunk = chunk.next
        return largest
