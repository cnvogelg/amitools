"""Handler API: the boundary between dos.library and a file system.

A *handler* maps the AmigaDOS packets used to talk to a real file system
handler onto Python methods. The DOS layer only sees the opaque handle and
result types defined here; it never touches host paths.

Errors are raised as :class:`HandlerError` carrying a DOS-compatible error
code so the DOS layer can map them to ``IoErr``. A future ``PacketHandler``
can turn these back into real DOS packets.
"""

from amitools.vamos.lib.dos.action import DosAction

# --- DOS-compatible error codes -------------------------------------------
# The values match AmigaDOS so a future PacketHandler can map them directly
# to dp_Res2 without importing dos.library code.

ERROR_NO_FREE_STORE = 103
ERROR_BAD_NUMBER = 115
ERROR_OBJECT_IN_USE = 202
ERROR_OBJECT_EXISTS = 203
ERROR_OBJECT_NOT_FOUND = 205
ERROR_ACTION_NOT_KNOWN = 209
ERROR_INVALID_COMPONENT_NAME = 210
ERROR_INVALID_LOCK = 211
ERROR_OBJECT_WRONG_TYPE = 212
ERROR_RENAME_ACROSS_DEVICES = 215
ERROR_DIRECTORY_NOT_EMPTY = 216
ERROR_TOO_MANY_LEVELS = 217
ERROR_SEEK_ERROR = 219
ERROR_DISK_FULL = 221
ERROR_DELETE_PROTECTED = 222
ERROR_WRITE_PROTECTED = 223
ERROR_READ_PROTECTED = 224
ERROR_NO_MORE_ENTRIES = 232
ERROR_NOT_IMPLEMENTED = 236

# --- AmigaDOS open modes ---------------------------------------------------

MODE_OLDFILE = 1005
MODE_NEWFILE = 1006
MODE_READWRITE = 1004


class HandlerError(Exception):
    """Raised by a handler when an action fails.

    ``code`` is a DOS-compatible error code (see the constants above).
    """

    def __init__(self, code, msg=None):
        self.code = code
        self.msg = msg
        super().__init__(msg if msg is not None else "handler error %d" % code)

    def __str__(self):
        if self.msg:
            return "%s (%d)" % (self.msg, self.code)
        return "handler error %d" % self.code


class HandlerLock:
    """Opaque lock reference handed out by a handler.

    A handler subclasses this to store its own state. ``key`` is a hashable
    identity of the locked object within its handler; the DOS layer uses it
    to group locks on the same object (``fl_Key``). ``handler`` points back
    to the handler that created the lock.
    """

    def __init__(self, key=None):
        self.key = key
        self.handler = None


class DeviceLock(HandlerLock):
    """lock on the root of a device handler (``NIL:``, ``CONSOLE:``, ...)

    A device has no objects to lock, but AmigaDOS still hands out a lock on
    the device root (``GetDeviceProc``'s ``dvp_Lock``). This lock is just an
    identity: the handler is stored so the DOS layer can report the device's
    packet port.
    """

    def __init__(self, name):
        super().__init__(key=name.lower())


class HandlerFile:
    """Opaque open-file reference handed out by a handler.

    Subclasses expose the underlying stream as ``fobj``. The flags tell the
    DOS layer how to wrap the handle: ``is_nil`` marks the ``NIL:`` sink,
    ``need_close`` says whether closing the handle closes the stream, and
    ``auto_flush`` flushes after every write (used for consoles).
    """

    is_nil = False
    need_close = True
    auto_flush = False

    def __init__(self, key=None):
        self.key = key
        self.handler = None


class HandlerFileInfo:
    """Result of examining a file system object (``FileInfoBlock`` fields)."""

    DIR = 2
    FILE = -3

    def __init__(
        self,
        name,
        entry_type,
        protection=0,
        size=0,
        blocks=0,
        date=0,
        key=0,
        comment="",
        owner_uid=0,
        owner_gid=0,
    ):
        self.name = name
        self.entry_type = entry_type
        self.protection = protection
        self.size = size
        self.blocks = blocks
        # seconds since the Unix epoch; the DOS layer converts to an AmiTime
        self.date = date
        self.key = key
        self.comment = comment
        self.owner_uid = owner_uid
        self.owner_gid = owner_gid

    @property
    def is_dir(self):
        return self.entry_type == self.DIR


class HandlerInfoData:
    """Result of ACTION_INFO / ACTION_DISK_INFO."""

    DISK_STATE_WRITE_PROTECTED = 80
    DISK_STATE_VALIDATED = 82

    def __init__(
        self,
        num_blocks=0,
        num_blocks_used=0,
        bytes_per_block=512,
        disk_type=0,
        disk_state=None,
        num_soft_errors=0,
        unit_number=0,
    ):
        self.num_blocks = num_blocks
        self.num_blocks_used = num_blocks_used
        self.bytes_per_block = bytes_per_block
        self.disk_type = disk_type
        if disk_state is None:
            disk_state = self.DISK_STATE_VALIDATED
        self.disk_state = disk_state
        self.num_soft_errors = num_soft_errors
        self.unit_number = unit_number


# --- method -> AmigaDOS packet map ----------------------------------------
# Every public action method of :class:`Handler` models exactly one AmigaDOS
# handler packet (``ACTION_*``). The map keeps the API a 1:1 model of the
# packets so a future ``PacketHandler`` can translate a method call into the
# matching ``DosPacket``. Methods without a packet (``tell``, ``is_interactive``)
# are deliberately not part of the handler API; lifecycle methods such as
# ``shutdown`` are not actions and are exempt.
ACTION_METHODS = {
    # locks
    "locate_object": DosAction.ACTION_LOCATE_OBJECT,
    "free_lock": DosAction.ACTION_FREE_LOCK,
    "copy_dir": DosAction.ACTION_COPY_DIR,
    "parent": DosAction.ACTION_PARENT,
    "same_lock": DosAction.ACTION_SAME_LOCK,
    "examine_object": DosAction.ACTION_EXAMINE_OBJECT,
    "examine_next": DosAction.ACTION_EXAMINE_NEXT,
    "info": DosAction.ACTION_INFO,
    "disk_info": DosAction.ACTION_DISK_INFO,
    "fh_from_lock": DosAction.ACTION_FH_FROM_LOCK,
    "parent_fh": DosAction.ACTION_PARENT_FH,
    "copy_dir_fh": DosAction.ACTION_COPY_DIR_FH,
    # files
    "find_input": DosAction.ACTION_FINDINPUT,
    "find_output": DosAction.ACTION_FINDOUTPUT,
    "find_update": DosAction.ACTION_FINDUPDATE,
    "read": DosAction.ACTION_READ,
    "write": DosAction.ACTION_WRITE,
    "seek": DosAction.ACTION_SEEK,
    "set_file_size": DosAction.ACTION_SET_FILE_SIZE,
    "flush": DosAction.ACTION_FLUSH,
    "end": DosAction.ACTION_END,
    "set_mode": DosAction.ACTION_SCREEN_MODE,
    "wait_for_char": DosAction.ACTION_WAIT_CHAR,
    # names
    "delete_object": DosAction.ACTION_DELETE_OBJECT,
    "rename_object": DosAction.ACTION_RENAME_OBJECT,
    "set_protect": DosAction.ACTION_SET_PROTECT,
    "set_comment": DosAction.ACTION_SET_COMMENT,
    "set_date": DosAction.ACTION_SET_DATE,
    "create_dir": DosAction.ACTION_CREATE_DIR,
}


class Handler:
    """Base class for file system handlers.

    Subclasses override the actions they support. Every unsupported action
    raises :class:`HandlerError` with ``ERROR_ACTION_NOT_KNOWN`` so the DOS
    layer can report it like AmigaDOS does.
    """

    def __init__(self, name, is_filesystem=True):
        self.name = name
        self.is_filesystem = is_filesystem
        # the handler's own packet port, injected by
        # HandlerManager.attach_dispatchers() once the machine exists
        self.dispatcher = None

    def _unsupported(self, action):
        raise HandlerError(ERROR_ACTION_NOT_KNOWN, "unsupported: %s" % action)

    # --- locks ---

    def locate_object(self, ami_path, exclusive=False):
        self._unsupported("locate_object")

    def free_lock(self, lock):
        self._unsupported("free_lock")

    def copy_dir(self, lock):
        self._unsupported("copy_dir")

    def parent(self, lock):
        self._unsupported("parent")

    def same_lock(self, a, b):
        self._unsupported("same_lock")

    def examine_object(self, lock):
        self._unsupported("examine_object")

    def examine_next(self, lock, key):
        self._unsupported("examine_next")

    def info(self, lock):
        self._unsupported("info")

    def disk_info(self, lock):
        self._unsupported("disk_info")

    def fh_from_lock(self, lock, mode=MODE_OLDFILE):
        self._unsupported("fh_from_lock")

    def parent_fh(self, fh):
        self._unsupported("parent_fh")

    def copy_dir_fh(self, fh):
        self._unsupported("copy_dir_fh")

    # --- files ---

    def find_input(self, ami_path):
        self._unsupported("find_input")

    def find_output(self, ami_path, mode=MODE_NEWFILE):
        self._unsupported("find_output")

    def find_update(self, ami_path):
        self._unsupported("find_update")

    def read(self, fh, size):
        self._unsupported("read")

    def write(self, fh, data):
        self._unsupported("write")

    def seek(self, fh, offset, whence):
        self._unsupported("seek")

    def set_file_size(self, fh, size, mode):
        self._unsupported("set_file_size")

    def flush(self, fh):
        self._unsupported("flush")

    def end(self, fh):
        """close an open file (ACTION_END)

        The underlying stream is only closed when the handle owns it; console
        handles share the host stream and must not close it.
        """
        if not fh.need_close:
            return
        try:
            fh.fobj.close()
        except OSError:
            pass

    def set_mode(self, fh, cooked):
        """set the console buffer mode (ACTION_SCREEN_MODE)

        ``cooked`` is True for line-buffered (cooked) input and False for raw
        input. Only interactive handlers (consoles) implement this.
        """
        self._unsupported("set_mode")

    def wait_for_char(self, fh, timeout):
        """wait for input becoming available (ACTION_WAIT_CHAR)

        Returns True if a character is available, False on timeout and None if
        the handler does not support waiting. Only interactive handlers
        (consoles) implement this.
        """
        self._unsupported("wait_for_char")

    # --- names ---

    def delete_object(self, ami_path):
        self._unsupported("delete_object")

    def rename_object(self, old_path, new_path):
        self._unsupported("rename_object")

    def set_protect(self, ami_path, mask):
        self._unsupported("set_protect")

    def set_comment(self, ami_path, comment):
        self._unsupported("set_comment")

    def set_date(self, ami_path, date):
        self._unsupported("set_date")

    def create_dir(self, ami_path):
        self._unsupported("create_dir")
