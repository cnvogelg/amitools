from amitools.vamos.libstructs import CSourceStruct


class CSource:
    """Simulate the AmigaDOS csource interface"""

    def __init__(self, buf=None):
        assert buf is None or isinstance(buf, bytes)
        self.buf = buf
        if buf is not None:
            self.len = len(buf)
        else:
            self.len = 0
        self.pos = 0

    def __repr__(self):
        return "%s(%d:%s)" % (self.__class__.__name__, self.len, repr(self.buf))

    def reset(self):
        self.pos = 0

    def next_line(self):
        while True:
            c = self.getc()
            if c is None or c == "\n":
                break

    def getc(self):
        """return a character or None if EOF"""
        if self.buf is None:
            return None
        if self.pos < self.len:
            c = self.buf[self.pos]
            self.pos += 1
            return chr(c)
        else:
            return None

    def ungetc(self):
        """stuff back last character"""
        if self.pos > 0:
            self.pos -= 1

    def read_s(self, alloc, ptr):
        """read structure from Amiga memory"""
        c = alloc.map_struct(ptr, CSourceStruct, label="CSource")
        buf_ptr = c.access.r_s("CS_Buffer")
        self.len = c.access.r_s("CS_Length")
        self.buf = bytes(alloc.mem.r_block(buf_ptr, self.len))
        self.pos = c.access.r_s("CS_CurChr")

    def update_s(self, alloc, ptr):
        """update current pointer only"""
        c = alloc.map_struct(ptr, CSourceStruct, label="CSource")
        c.access.w_s("CS_CurChr", self.pos)

    def append_line(self):
        pass

    def rewind(self, num):
        if self.pos >= num:
            self.pos -= num


class FileLineCSource(CSource):
    def __init__(self, fh):
        CSource.__init__(self)
        self.fh = fh

    def append_line(self):
        res = []
        if self.fh is not None:
            while True:
                ch = self.fh.getc()
                if ch == -1:
                    break
                res.append(ch)
                if ch == 10:
                    break
        line = bytes(res)
        if self.buf is None:
            self.buf = line
        else:
            self.buf += line
        self.len = len(self.buf)


class FileCSource:
    """wrap a file handle"""

    def __init__(self, fh):
        self.fh = fh
        self.last_ch = None

    def getc(self):
        if self.fh is None:
            return None
        ch = self.fh.getc()
        if ch == -1:
            self.last_ch = None
            return None
        else:
            self.last_ch = ch
            return ch

    def ungetc(self):
        if self.last_ch is not None:
            self.fh.ungetc(self.last_ch)
