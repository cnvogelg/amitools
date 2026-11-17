from amitools.vamos.handler import HandlerError
from amitools.vamos.libstructs import FileHandleStruct


class FileHandle:
    """represent an AmigaOS file handle (FH) in vamos

    The handle is a thin DOS-level adapter. Every operation that maps to an
    AmigaDOS handler packet is delegated to the handler the handle was opened
    with; the raw stream (``obj``) is only used as a fallback for handler-less
    handles (bare test managers, the console fallback) and for the few
    operations that have no packet (``tell``, ``is_interactive``).
    """

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
        self.interactive = self.obj.isatty() if self.obj is not None else False

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
        """ACTION_END: close the file via the handler"""
        if self.handler is not None and self.handler_file is not None:
            try:
                self.handler.end(self.handler_file)
            except HandlerError:
                pass
            return
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
        """ACTION_SCREEN_MODE: set the console buffer mode

        Returns True on success, False if the handler/stream does not support
        mode switching.
        """
        if self.handler is not None and self.handler_file is not None:
            try:
                return self.handler.set_mode(self.handler_file, cooked)
            except HandlerError:
                return False
        # handler-less fallback: the stream may provide tty mode handling
        fn = getattr(self.obj, "set_mode", None)
        if fn is None:
            return False
        return fn(cooked)

    def wait_for_char(self, timeout):
        """ACTION_WAIT_CHAR: wait for input becoming available

        Returns True if a char is available, False on timeout, None if the
        handler/stream does not support waiting.
        """
        if self.handler is not None and self.handler_file is not None:
            try:
                return self.handler.wait_for_char(self.handler_file, timeout)
            except HandlerError:
                return None
        fn = getattr(self.obj, "wait_for_char", None)
        if fn is None:
            return False
        return fn(timeout)

    def write(self, data):
        """ACTION_WRITE: write data

        return -1 on error, 0=EOF, >0 written bytes"""
        assert isinstance(data, (bytes, bytearray))
        orig_len = len(data)

        if self.handler is not None and self.handler_file is not None:
            try:
                got = self.handler.write(self.handler_file, data)
            except HandlerError:
                return -1
        else:
            try:
                self.obj.write(data)
                got = orig_len
            except IOError:
                got = -1

        # do auto flush?
        if got > 0 and self.auto_flush:
            self.flush()

        # return got bytes
        return got

    def read(self, len):
        """ACTION_READ: return bytes, an empty byte string at EOF, or -1."""
        if self.handler is not None and self.handler_file is not None:
            try:
                return self.handler.read(self.handler_file, len)
            except HandlerError:
                return -1
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

            d = self.read(1)

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
        if self.obj is None:
            return -1
        try:
            return self.obj.tell()
        except IOError:
            return -1

    def seek(self, pos, whence):
        """ACTION_SEEK: set to position from whence

        return -1 on error, -2 on too far or new_pos
        """
        if self.handler is not None and self.handler_file is not None:
            try:
                return self.handler.seek(self.handler_file, pos, whence)
            except HandlerError:
                return -1
        try:
            return self.obj.seek(pos, whence)
        except IOError:
            return -1

    def set_file_size(self, size, mode):
        """ACTION_SET_FILE_SIZE: return the new size or -1 on error

        ``mode`` is the raw AmigaDOS mode: ``-1`` (OFFSET_BEGINNING),
        ``0`` (OFFSET_CURRENT) or ``1`` (OFFSET_END).
        """
        if self.handler is not None and self.handler_file is not None:
            try:
                return self.handler.set_file_size(self.handler_file, size, mode)
            except HandlerError:
                return -1
        # handler-less fallback: truncate the raw stream
        obj = self.obj
        if obj is None:
            return -1
        try:
            if mode == -1:
                new_size = size
            elif mode == 0:
                new_size = obj.tell() + size
            elif mode == 1:
                new_size = obj.seek(0, 2) + size
            else:
                return -1
            if new_size < 0:
                return -1
            obj.truncate(new_size)
            return new_size
        except (OSError, ValueError, AttributeError):
            return -1

    def flush(self):
        """ACTION_FLUSH: flush the handler's buffers"""
        if self.handler is not None and self.handler_file is not None:
            try:
                self.handler.flush(self.handler_file)
            except HandlerError:
                pass
            return
        self.obj.flush()

    def is_interactive(self):
        return self.interactive
