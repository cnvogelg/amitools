import os

from amitools.vamos.libstructs import FileHandleStruct


class FileHandle:
    """represent an AmigaOS file handle (FH) in vamos"""

    def __init__(
        self,
        obj,
        ami_path,
        name,
        handler=None,
        handler_file=None,
        need_close=True,
        is_nil=False,
        auto_flush=False,
    ):
        self.obj = obj
        self.name = name
        self.ami_path = ami_path
        self.handler = handler
        self.handler_file = handler_file
        self.b_addr = 0
        self.need_close = need_close
        self.auto_flush = auto_flush
        # buffering
        self.unch = bytearray()
        self.ch = -1
        self.is_nil = is_nil
        # console conversions (tty, latin1->utf8) live in the handler's
        # stream; the DOS layer only sees a plain byte stream
        self.interactive = self.obj.isatty()

    def __repr__(self):
        return "[FH:'%s'(ami='%s',nc=%s,af=%s,int=%s)@%06x=B@%06x]" % (
            self.name,
            self.ami_path,
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

    def alloc_fh(self, alloc, fs_handler_port):
        name = "File:" + self.name
        self.mem = self.struct = alloc.alloc_astruct(FileHandleStruct, label=name)
        fh = self.struct
        self.b_addr = self.mem.addr >> 2
        # -- fill filehandle
        # use baddr of FH itself as identifier
        fh.fh_Args.val = self.b_addr
        # set port
        fh.fh_Type.aptr = fs_handler_port
        # buffer handling: set fh_End != 0 (to prepare for EOF hack in FGetS)
        fh.fh_End.val = 1
        return self.b_addr

    def free_fh(self, alloc):
        self.struct.free()
        self.mem = None
        self.struct = None

    # --- file ops ---

    def set_mode(self, cooked):
        # console streams provide tty mode handling; plain files do not
        fn = getattr(self.obj, "set_mode", None)
        if fn is None:
            return False
        return fn(cooked)

    def wait_for_char(self, timeout):
        fn = getattr(self.obj, "wait_for_char", None)
        if fn is None:
            return False
        return fn(timeout)

    def write(self, data):
        """write data

        return -1 on error, 0=EOF, >0 written bytes"""
        assert isinstance(data, (bytes, bytearray))
        orig_len = len(data)

        try:
            self.obj.write(data)
            got = orig_len
        except IOError:
            got = -1

        # do auto flush?
        if got > 0 and self.auto_flush:
            self.obj.flush()

        # return got bytes
        return got

    def read(self, len):
        """Return bytes, an empty byte string at EOF, or -1 on error."""
        try:
            read = getattr(self.obj, "read1", None)
            if read is None:
                read = self.obj.read
            return read(len)
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

    def setvbuf(self, buf, buf_type, size):
        self.buf = buf
        self.buf_type = buf_type
        self.buf_size = size
        if hasattr(self, "struct") and self.struct is not None:
            self.struct.fh_Buf.val = buf
        self.auto_flush = buf_type == 1

    def tell(self):
        try:
            return self.obj.tell()
        except IOError:
            return -1

    def seek(self, pos, whence):
        """set to position from whence

        return -1 on error, -2 on too far or new_pos
        """
        try:
            new_pos = self.obj.seek(pos, whence)

            # we have to limit seek to file size
            stat = os.stat(self.obj.fileno())
            file_size = stat.st_size

            # if seek to far then limit to file size
            if new_pos > file_size:
                # seek to end
                self.obj.seek(file_size, 0)
                return -2

            return new_pos

        except IOError:
            return -1

    def flush(self):
        self.obj.flush()

    def is_interactive(self):
        return self.interactive
