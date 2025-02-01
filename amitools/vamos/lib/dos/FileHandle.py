import os
import sys

from amitools.vamos.libstructs import FileHandleStruct
from .terminal import Terminal


class FileHandle:
    """represent an AmigaOS file handle (FH) in vamos"""

    def __init__(
        self, obj, ami_path, sys_path, need_close=True, is_nil=False, auto_flush=False
    ):
        self.obj = obj
        self.name = os.path.basename(sys_path)
        self.ami_path = ami_path
        self.sys_path = sys_path
        self.b_addr = 0
        self.need_close = need_close
        self.auto_flush = auto_flush
        # buffering
        self.unch = bytearray()
        self.ch = -1
        self.is_nil = is_nil
        self.interactive = self.obj.isatty()
        # tty stuff
        if self.interactive:
            self.terminal = Terminal(obj)
        else:
            self.terminal = None

    def __repr__(self):
        return "[FH:'%s'(ami='%s',sys='%s',nc=%s,af=%s,int=%s)@%06x=B@%06x]" % (
            self.name,
            self.ami_path,
            self.sys_path,
            self.need_close,
            self.auto_flush,
            self.interactive,
            self.mem.addr,
            self.b_addr,
        )

    def __str__(self):
        return "[FH:'%s'@%06x=B@%06x]" % (self.name, self.mem.addr, self.b_addr)

    def close(self):
        if self.need_close:
            self.obj.close()
        # restore tty
        if self.terminal:
            self.terminal.close()

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

    def set_mode(self, cooked):
        # no tty support on this platform
        if not self.terminal:
            return False
        # set mode
        return self.terminal.set_mode(cooked)

    def wait_for_char(self, timeout):
        if not self.terminal:
            return False
        return self.terminal.wait_for_char(timeout)

    def write(self, data):
        """write data

        return -1 on error, 0=EOF, >0 written bytes"""
        assert isinstance(data, (bytes, bytearray))

        # read from terminal or direct
        if self.terminal:
            got = self.terminal.write(data)
        else:
            try:
                got = self.obj.write(data)
            except IOError:
                got = -1

        # do auto flush?
        if got > 0 and self.auto_flush:
            self.obj.flush()

        # return got bytes
        return got

    def read(self, len):
        """read data

        return -1 on error, 0=EOF, >0 written bytes"""
        if self.terminal:
            return self.terminal.read(len)
        try:
            return self.obj.read(len)
        except IOError:
            return -1

    def getc(self):
        """read character

        return char 0-255 or -1 on Error and -2 on EOF
        """
        if len(self.unch) > 0:
            # first unget char
            self.ch = self.unch.pop(0)
        else:
            # handle NIL:
            if self.is_nil:
                return -1

            # read from terminal or direct
            if self.terminal:
                d = self.terminal.read(1)
            else:
                d = self.obj.read(1)

            # -1 on Error
            if d == -1:
                return -1
            # -2 on EOF
            elif d == b"":
                return -2
            self.ch = d[0]
        return self.ch

    def gets(self, len):
        """read up to len bytes or line ending with newline

        return <string>, error=True/False
        """
        res = bytearray()
        error = False
        for a in range(len):
            ch = self.getc()
            if ch == -1:
                error = True
                break
            elif ch == -2:
                break
            res.append(ch)
            if ch == 10:
                break
        return res.decode("latin-1"), error

    def ungetc(self, var):
        if var == 0xFFFFFFFF:
            var = -1
        # var == -1 -> unget last char
        if var < 0 and self.ch >= 0:
            var = self.ch
            self.ch = -1
        elif var >= 0:
            self.unch.insert(0, var)
        return var

    def setbuf(self, s):
        if isinstance(s, str):
            s = s.encode("latin-1")
        self.unch = bytearray(s)

    def tell(self):
        return self.obj.tell()

    def seek(self, pos, whence):
        """set to position from whence

        return -1 on error or new_pos
        """
        try:
            return self.obj.seek(pos, whence)
        except IOError:
            return -1

    def flush(self):
        self.obj.flush()

    def is_interactive(self):
        return self.interactive
