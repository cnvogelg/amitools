class InitStruct(object):
    def __init__(self, mem):
        self.mem = mem

    def init_struct(self, init_table_ptr, memory_ptr, size):
        """Exec's InitStruct() call"""
        if size > 0:
            self.mem.clear_block(memory_ptr, size, 0)
        # eval codes
        ptr = init_table_ptr
        mem = memory_ptr
        offset = 0
        while True:
            cmd = self.mem.r8(ptr)
            if cmd == 0:
                break
            # decode cmd
            typ = (cmd >> 6) & 3
            siz = (cmd >> 4) & 3
            cnt = cmd & 15
            # read offset and skip cmd
            if typ == 0 or typ == 1:
                ptr += 1
            elif typ == 2:
                offset = self.mem.r8(ptr + 1)
                ptr += 2
            else:
                offset = self.mem.r32(ptr) & 0xFFFFFF
                ptr += 4
            # align data to word if not byte
            if siz == 0 or siz == 1:
                ptr = (ptr + 1) & ~1
                mem = (mem + 1) & ~1
            elif size == 3:  # invalid
                raise ValueError("invalid size field in init_struct @%06x" % ptr)
            # apply offset
            if typ == 2 or typ == 3:
                mem = memory_ptr + offset
            rng = range(cnt + 1)
            # op: repeat cnt+1 times
            if typ == 1:
                if siz == 0:  # LONG
                    val = self.mem.r32(ptr)
                    ptr += 4
                    for i in rng:
                        self.mem.w32(mem, val)
                        mem += 4
                elif siz == 1:  # WORD
                    val = self.mem.r16(ptr)
                    ptr += 2
                    for i in rng:
                        self.mem.w16(mem, val)
                        mem += 2
                else:  # BYTE
                    val = self.mem.r8(ptr)
                    ptr += 1
                    for i in rng:
                        self.mem.w8(mem, val)
                        mem += 1
            # op: copy cnt+1 elements
            else:
                if siz == 0:  # LONG
                    for i in rng:
                        val = self.mem.r32(ptr)
                        self.mem.w32(mem, val)
                        ptr += 4
                        mem += 4
                elif siz == 1:  # WORD
                    for i in rng:
                        val = self.mem.r16(ptr)
                        self.mem.w16(mem, val)
                        ptr += 2
                        mem += 2
                else:
                    for i in rng:
                        val = self.mem.r8(ptr)
                        self.mem.w8(mem, val)
                        ptr += 1
                        mem += 1
            # align next cmd to word
            ptr = (ptr + 1) & ~1


class InitStructBuilder(object):

    SIZE_LONG = 0
    SIZE_WORD = 1
    SIZE_BYTE = 2

    def __init__(self, mem, ptr):
        self.mem = mem
        self.ptr = ptr

    def init_byte(self, offset, val):
        if offset < 256:
            self.mem.w8(self.ptr, 0xA0)
            self.mem.w8(self.ptr + 1, offset)
            self.mem.w8(self.ptr + 2, val)
            self.ptr += 4
        else:
            ul = (0xE0 << 24) | offset
            self.mem.w32(self.ptr, ul)
            self.mem.w8(self.ptr + 4, val)
            self.ptr += 6

    def init_word(self, offset, val):
        if offset < 256:
            self.mem.w8(self.ptr, 0x90)
            self.mem.w8(self.ptr + 1, offset)
            self.mem.w16(self.ptr + 2, val)
            self.ptr += 4
        else:
            ul = (0xD0 << 24) | offset
            self.mem.w32(self.ptr, ul)
            self.mem.w16(self.ptr + 4, val)
            self.ptr += 6

    def init_long(self, offset, val):
        if offset < 256:
            self.mem.w8(self.ptr, 0x80)
            self.mem.w8(self.ptr + 1, offset)
            self.mem.w32(self.ptr + 2, val)
            self.ptr += 6
        else:
            ul = (0xC0 << 24) | offset
            self.mem.w32(self.ptr, ul)
            self.mem.w32(self.ptr + 4, val)
            self.ptr += 8

    def init_struct(self, size, offset, data):
        cnt = len(data) - 1
        cmd = size << 4 | cnt
        if offset < 256:
            cmd |= 0x80
            self.mem.w8(self.ptr, cmd)
            self.mem.w8(self.ptr + 1, offset)
            self.ptr += 2
        else:
            cmd |= 0xC0
            ul = (cmd << 24) | offset
            self.mem.w32(self.ptr, ul)
            self.ptr += 4
        # copy data
        for d in data:
            if size == self.SIZE_LONG:
                self.mem.w32(self.ptr, d)
                self.ptr += 4
            elif size == self.SIZE_WORD:
                self.mem.w16(self.ptr, d)
                self.ptr += 2
            elif size == self.SIZE_BYTE:
                self.mem.w8(self.ptr, d)
                self.ptr += 1
            else:
                raise ValueError("invalid size: " + size)
        # allign ptr
        if self.ptr % 2 == 1:
            self.ptr += 1

    def end(self):
        self.mem.w16(self.ptr, 0)
