from amitools.vamos.libstructs import (
    ResidentStruct,
    AutoInitStruct,
    LibraryStruct,
    NodeType,
)
from amitools.vamos.mem import MemoryCache
from amitools.vamos.astructs import AmigaClassDef


@AmigaClassDef
class Resident(ResidentStruct):

    RTC_MATCHWORD = 0x4AFC

    @classmethod
    def find(cls, mem, addr, size, only_first=True, mem_cache=True):
        """scan a memory region for resident structures and return the residents.
        if 'only_first' is set return a single instance or None.
        otherwise a list of Resident objects.
        """
        # use a memory cache to speed up search
        if mem_cache:
            memc = MemoryCache(addr, size)
            memc.read_cache(mem)
            mem = memc
        # start search
        end_addr = addr + size
        finds = []
        while addr < end_addr:
            # look for match word
            mw = mem.r16(addr)
            if mw == cls.RTC_MATCHWORD:
                # check pointer
                ptr = mem.r32(addr + 2)
                if ptr == addr:
                    # yes its a resident...
                    if only_first:
                        return cls(mem, addr)
                    finds.append(cls(mem, addr))
                    # read end skip
                    addr = mem.r32(addr + 6)
            addr += 2
        # nothing found for single match:
        if only_first:
            return None
        return finds

    def is_valid(self):
        if self.match_word.val != self.RTC_MATCHWORD:
            return False
        return self.match_tag.aptr == self.get_addr()

    def new_resident(
        self, flags=0, version=0, type=NodeType.NT_LIBRARY, pri=0, init=None
    ):
        self.match_word.val = self.RTC_MATCHWORD
        self.match_tag.aptr = self.addr
        self.end_skip.aptr = self.addr + self.get_size()
        self.flags.val = flags
        self.version.val = version
        self.type.val = type
        self.pri.val = pri
        self.init.setup(init)
