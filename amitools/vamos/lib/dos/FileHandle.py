import os
import sys
from amitools.vamos.libstructs import FileHandleStruct


class FileHandle:
    """represent an AmigaOS file handle (FH) in vamos"""

    def __init__(self, obj, ami_path, sys_path, need_close=True, is_nil=False):
        self.obj = obj
        self.name = os.path.basename(sys_path)
        self.ami_path = ami_path
        self.sys_path = sys_path
        self.b_addr = 0
        self.need_close = need_close
        # buffering
        self.unch = bytearray()
        self.ch = -1
        self.is_nil = is_nil

    def __str__(self):
        return "[FH:'%s'(ami='%s',sys='%s',nc=%s)@%06x=B@%06x]" % (
            self.name,
            self.ami_path,
            self.sys_path,
            self.need_close,
            self.mem.addr,
            self.b_addr,
        )

    def close(self):
        if self.need_close:
            self.obj.close()

    def alloc_fh(self, alloc, fs_handler_port):
        name = "File:" + self.name
        self.mem = alloc.alloc_struct(FileHandleStruct, label=name)
        self.b_addr = self.mem.addr >> 2
        # -- fill filehandle
        # use baddr of FH itself as identifier
        self.mem.access.w_s("fh_Args", self.b_addr)
        # set port
        self.mem.access.w_s("fh_Type", fs_handler_port)
        # buffer handling: set fh_End != 0 (to prepare for EOF hack in FGetS)
        self.mem.access.w_s("fh_End", 1)
        return self.b_addr

    def free_fh(self, alloc):
        alloc.free_struct(self.mem)

    # --- file ops ---

    def write(self, data):
        assert isinstance(data, (bytes, bytearray))
        try:
            self.obj.write(data)
            return len(data)
        except IOError:
            return -1

    def read(self, len):
        try:
            d = self.obj.read(len)
            return d
        except IOError:
            return -1

    def getc(self):
        if len(self.unch) > 0:
            self.ch = self.unch[0]
            del self.unch[0]
        else:
            if self.is_nil:
                return -1
            try:
                d = self.obj.read(1)
                if d == b"":
                    return -1
                self.ch = d[0]
            except IOError:
                return -1
        return self.ch

    def gets(self, len):
        res = bytearray()
        ch = -1
        # print "fgets from %s" % self
        while len > 0:
            len -= 1
            ch = self.getc()
            if ch < 0:
                return res.decode("latin-1")
            res.append(ch)
            if ch == 10:
                return res.decode("latin-1")
        # apparently, python-I/O does not keep the unread
        # part of a line in a buffer, so we have to (bummer!)
        # Do that now so that the next read gets the rest
        # of the line.
        remains = bytearray()
        while ch != 10:
            ch = self.getc()
            if ch == -1:
                break
            remains.append(ch)
        self.unch = remains + self.unch
        return res.decode("latin-1")

    def ungetc(self, var):
        if var == 0xFFFFFFFF:
            var = -1
        if var < 0 and self.ch >= 0:
            var = self.ch
            self.ch = -1
        if var >= 0:
            self.unch.insert(0, var)
        return var

    def ungets(self, s):
        if isinstance(s, str):
            s = s.encode("latin-1")
        self.unch = self.unch + bytearray(s)

    def setbuf(self, s):
        if isinstance(s, str):
            s = s.encode("latin-1")
        self.unch = bytearray(s)

    def getbuf(self):
        return self.unch

    def tell(self):
        return self.obj.tell()

    def seek(self, pos, whence):
        try:
            self.obj.seek(pos, whence)
        except IOError:
            return -1

    def flush(self):
        self.obj.flush()

    def is_interactive(self):
        fd = self.obj.fileno()
        if hasattr(os, "ttyname"):
            try:
                os.ttyname(fd)
                return True
            except OSError:
                return False
        else:
            # Not perfect, but best you can do on non-posix to detect a terminal.
            return sys.stdin.isatty() or sys.stdout.isatty()
