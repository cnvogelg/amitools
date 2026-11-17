"""Packet handler: implement the handler API by talking AmigaDOS packets.

The handler API (see :mod:`amitools.vamos.handler.base`) is a 1:1 model of
the AmigaDOS ``ACTION_*`` packets, so a handler can also be implemented as a
*client* of a real file system handler: every action method builds a
memory-backed :class:`~amitools.vamos.libtypes.DosPacket`, submits it through
the overridable :meth:`PacketHandler._dopkt` transport hook, and translates the
reply back into the Python handler types.

The marshalling is the reverse of the table in ``HANDLER.md``:

* path packets use the ZERO lock (``dp_Arg1 = 0``) and a BPTR to a BSTR;
* lock/file packets carry the lock BPTR / ``fh_Arg1``;
* ``dp_Res2 != 0`` becomes :class:`HandlerError`; ``dp_Res1`` is the result.

Step 10 ships the adapter and tests it with a mock/loopback transport. Step 11
implements :meth:`_dopkt` with real ``SendPkt``/``WaitPkt`` calls against a
native handler port.
"""

from amitools.vamos.lib.dos.AmiTime import AmiTime, ami_to_sys_time, sys_to_ami_time
from amitools.vamos.lib.dos.action import DosAction
from amitools.vamos.libstructs import (
    DateStampStruct,
    FileHandleStruct,
    FileInfoBlockStruct,
    InfoDataStruct,
)
from amitools.vamos.libtypes import DosPacket

from .base import (
    ERROR_ACTION_NOT_KNOWN,
    ERROR_BAD_NUMBER,
    ERROR_OBJECT_NOT_FOUND,
    MODE_NEWFILE,
    MODE_OLDFILE,
    MODE_READWRITE,
    Handler,
    HandlerError,
    HandlerFile,
    HandlerFileInfo,
    HandlerInfoData,
    HandlerLock,
)

# AmigaDOS lock modes (ACTION_LOCATE_OBJECT dp_Arg3)
EXCLUSIVE_LOCK = -1
SHARED_LOCK = -2

# the three open modes are the matching FIND* packet numbers, so a
# ``find_output(mode)`` maps directly onto the packet to send
_FIND_ACTIONS = {
    MODE_OLDFILE: DosAction.ACTION_FINDINPUT,
    MODE_NEWFILE: DosAction.ACTION_FINDOUTPUT,
    MODE_READWRITE: DosAction.ACTION_FINDUPDATE,
}

# chunk size used to emulate a "read everything" request (size < 0)
_READ_ALL_CHUNK = 512


class PacketLock(HandlerLock):
    """lock reference backed by a DOS lock BPTR

    The per-lock ``FileInfoBlock`` is allocated lazily the first time the lock
    is examined; ``examine_object``/``examine_next`` operate on that same FIB so
    the handler can keep its directory cursor there.
    """

    def __init__(self, bptr, fib=None):
        super().__init__(key=bptr)
        self.bptr = bptr
        self.fib = fib


class PacketFile(HandlerFile):
    """open-file reference backed by a handler ``fh_Arg1``

    There is no host stream behind it: the DOS layer reaches the data through
    :meth:`PacketHandler.read`/:meth:`PacketHandler.write`, not through
    ``fobj``.
    """

    def __init__(self, fh_arg1, ami_path=""):
        super().__init__(key=fh_arg1)
        self.fh_arg1 = fh_arg1
        self.ami_path = ami_path
        self.fobj = None


class _PacketCall:
    """one in-flight packet plus its transient allocations

    Used as a context manager. All buffers, BSTRs, file handles and structs
    allocated while building the call are released when the block exits, so a
    call never leaks memory (even if ``_dopkt`` raises).
    """

    def __init__(self, handler, action):
        self.handler = handler
        self.action = action
        self.pkt = None
        self._mems = []
        self._structs = []

    def __enter__(self):
        handler = self.handler
        self.pkt = handler.alloc.alloc_astruct(DosPacket, label="DosPacket")
        self.pkt.type.val = int(self.action)
        return self

    def __exit__(self, exc_type, exc, tb):
        for struct in self._structs:
            struct.free()
        for mem in self._mems:
            self.handler.alloc.free_memory(mem)
        self.pkt.free()
        return False

    def arg(self, index, value):
        getattr(self.pkt, "arg%d" % index).val = value

    def bstr(self, text):
        """allocate a BSTR and return its BPTR (AmigaDOS path argument)"""
        handler = self.handler
        data = str(text).encode("latin-1")
        mem = handler.alloc.alloc_memory(len(data) + 1, label="BSTR")
        handler.mem.w_bstr(mem.addr, str(text))
        self._mems.append(mem)
        return mem.addr >> 2

    def buffer(self, size):
        """allocate a byte buffer and return its address"""
        handler = self.handler
        mem = handler.alloc.alloc_memory(max(int(size), 1), label="Buffer")
        self._mems.append(mem)
        return mem.addr

    def fh(self):
        """allocate a FileHandleStruct the handler can fill in"""
        fh = self.handler.alloc.alloc_astruct(FileHandleStruct, label="FileHandle")
        self._structs.append(fh)
        return fh

    def date(self, value):
        """allocate a DateStampStruct for ``set_date`` and return its BPTR"""
        ds = self.handler.alloc.alloc_astruct(DateStampStruct, label="DateStamp")
        at = sys_to_ami_time(value)
        ds.ds_Days.val = at.tday
        ds.ds_Minute.val = at.tmin
        ds.ds_Tick.val = at.tick
        self._structs.append(ds)
        return ds.addr >> 2

    def send(self):
        """run the transport and translate the reply

        ``dp_Res2 != 0`` raises :class:`HandlerError`; otherwise ``dp_Res1`` is
        returned.
        """
        self.handler._dopkt(self.pkt)
        res1 = self.pkt.res1.val
        res2 = self.pkt.res2.val
        if res2 != 0:
            raise HandlerError(res2)
        return res1


class PacketHandler(Handler):
    """handler implemented by sending AmigaDOS packets through ``_dopkt``

    Subclasses (or callers) provide the transport by overriding ``_dopkt`` or
    by assigning a callable to the instance. The method receives the filled
    :class:`~amitools.vamos.libtypes.DosPacket`, sends it, and fills
    ``dp_Res1``/``dp_Res2``; it may also raise :class:`HandlerError` directly.
    """

    def __init__(self, name, alloc, is_filesystem=True):
        super().__init__(name, is_filesystem=is_filesystem)
        self.alloc = alloc
        self.mem = alloc.mem

    # ----- transport hook -----

    def _dopkt(self, pkt):
        raise NotImplementedError(
            "PacketHandler needs a packet transport: override _dopkt()"
        )

    # ----- packet helpers -----

    def _call(self, action):
        return _PacketCall(self, action)

    def _make_lock(self, bptr):
        lock = PacketLock(bptr)
        lock.handler = self
        return lock

    def _make_file(self, fh_arg1, ami_path=""):
        fh = PacketFile(fh_arg1, ami_path)
        fh.handler = self
        return fh

    def _fib_for(self, lock):
        if lock.fib is None:
            lock.fib = self.alloc.alloc_astruct(FileInfoBlockStruct, label="FIB")
        return lock.fib

    def _parse_fib(self, fib):
        mem = self.mem
        date = AmiTime(
            fib.fib_Date.ds_Days.val,
            fib.fib_Date.ds_Minute.val,
            fib.fib_Date.ds_Tick.val,
        )
        return HandlerFileInfo(
            name=mem.r_cstr(fib.fib_FileName.addr),
            entry_type=fib.fib_DirEntryType.val,
            protection=fib.fib_Protection.val,
            size=fib.fib_Size.val,
            blocks=fib.fib_NumBlocks.val,
            date=ami_to_sys_time(date),
            key=fib.fib_DiskKey.val,
            comment=mem.r_cstr(fib.fib_Comment.addr),
            owner_uid=fib.fib_OwnerUID.val,
            owner_gid=fib.fib_OwnerGID.val,
        )

    def _parse_info(self, info):
        return HandlerInfoData(
            num_blocks=info.id_NumBlocks.val,
            num_blocks_used=info.id_NumBlocksUsed.val,
            bytes_per_block=info.id_BytesPerBlock.val,
            disk_type=info.id_DiskType.val,
            disk_state=info.id_DiskState.val,
            num_soft_errors=info.id_NumSoftErrors.val,
            unit_number=info.id_UnitNumber.val,
        )

    def _open_file(self, action, ami_path):
        """send a FIND* packet and read the handler's ``fh_Arg1`` back"""
        with self._call(action) as call:
            fh_struct = call.fh()
            call.arg(1, fh_struct.addr >> 2)
            call.arg(2, 0)
            call.arg(3, call.bstr(ami_path))
            res1 = call.send()
            fh_arg1 = fh_struct.args.val
        if res1 == 0 or fh_arg1 == 0:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        return self._make_file(fh_arg1, ami_path)

    # ----- locks -----

    def locate_object(self, ami_path, exclusive=False):
        with self._call(DosAction.ACTION_LOCATE_OBJECT) as call:
            call.arg(1, 0)
            call.arg(2, call.bstr(ami_path))
            call.arg(3, EXCLUSIVE_LOCK if exclusive else SHARED_LOCK)
            bptr = call.send()
        return self._make_lock(bptr)

    def free_lock(self, lock):
        if lock.fib is not None:
            lock.fib.free()
            lock.fib = None
        with self._call(DosAction.ACTION_FREE_LOCK) as call:
            call.arg(1, lock.bptr)
            call.send()

    def copy_dir(self, lock):
        with self._call(DosAction.ACTION_COPY_DIR) as call:
            call.arg(1, lock.bptr)
            bptr = call.send()
        return self._make_lock(bptr)

    def parent(self, lock):
        with self._call(DosAction.ACTION_PARENT) as call:
            call.arg(1, lock.bptr)
            bptr = call.send()
        # the volume root has no parent: the packet reports res1=0, res2=0
        if bptr == 0:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        return self._make_lock(bptr)

    def same_lock(self, a, b):
        if a is b:
            return True
        # locks of different handlers can never be the same object
        if getattr(a, "handler", None) is not getattr(b, "handler", None):
            return False
        with self._call(DosAction.ACTION_SAME_LOCK) as call:
            call.arg(1, a.bptr)
            call.arg(2, b.bptr)
            return bool(call.send())

    def examine_object(self, lock):
        fib = self._fib_for(lock)
        with self._call(DosAction.ACTION_EXAMINE_OBJECT) as call:
            call.arg(1, lock.bptr)
            call.arg(2, fib.addr)
            call.send()
        return self._parse_fib(fib)

    def examine_next(self, lock, key):
        fib = self._fib_for(lock)
        # the packet resumes from the lock's FIB cursor; ``key`` is a
        # consistency/restart hint, so re-examine when it is reset to 0
        if key == 0:
            self.examine_object(lock)
        with self._call(DosAction.ACTION_EXAMINE_NEXT) as call:
            call.arg(1, lock.bptr)
            call.arg(2, fib.addr)
            call.send()
        return self._parse_fib(fib)

    def info(self, lock):
        with self._call(DosAction.ACTION_INFO) as call:
            info_data = self.alloc.alloc_astruct(InfoDataStruct, label="InfoData")
            try:
                call.arg(1, lock.bptr)
                call.arg(2, info_data.addr)
                call.send()
                return self._parse_info(info_data)
            finally:
                info_data.free()

    def disk_info(self, lock):
        with self._call(DosAction.ACTION_DISK_INFO) as call:
            info_data = self.alloc.alloc_astruct(InfoDataStruct, label="InfoData")
            try:
                call.arg(1, info_data.addr)
                call.send()
                return self._parse_info(info_data)
            finally:
                info_data.free()

    def fh_from_lock(self, lock, mode=MODE_OLDFILE):
        with self._call(DosAction.ACTION_FH_FROM_LOCK) as call:
            fh_struct = call.fh()
            call.arg(1, fh_struct.addr >> 2)
            call.arg(2, lock.bptr)
            res1 = call.send()
            fh_arg1 = fh_struct.args.val
        if res1 == 0 or fh_arg1 == 0:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        return self._make_file(fh_arg1)

    def parent_fh(self, fh):
        with self._call(DosAction.ACTION_PARENT_FH) as call:
            call.arg(1, fh.fh_arg1)
            bptr = call.send()
        if bptr == 0:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        return self._make_lock(bptr)

    def copy_dir_fh(self, fh):
        with self._call(DosAction.ACTION_COPY_DIR_FH) as call:
            call.arg(1, fh.fh_arg1)
            bptr = call.send()
        return self._make_lock(bptr)

    # ----- files -----

    def find_input(self, ami_path):
        return self._open_file(DosAction.ACTION_FINDINPUT, ami_path)

    def find_output(self, ami_path, mode=MODE_NEWFILE):
        action = _FIND_ACTIONS.get(mode)
        if action is None:
            raise HandlerError(ERROR_BAD_NUMBER)
        return self._open_file(action, ami_path)

    def find_update(self, ami_path):
        return self._open_file(DosAction.ACTION_FINDUPDATE, ami_path)

    def read(self, fh, size):
        if size is None or size < 0:
            return self._read_all(fh)
        with self._call(DosAction.ACTION_READ) as call:
            buf = call.buffer(size)
            call.arg(1, fh.fh_arg1)
            call.arg(2, buf)
            call.arg(3, size)
            got = call.send()
            if got <= 0:
                return b""
            return self.mem.r_block(buf, got)

    def _read_all(self, fh):
        chunks = []
        while True:
            chunk = self.read(fh, _READ_ALL_CHUNK)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)

    def write(self, fh, data):
        data = bytes(data)
        with self._call(DosAction.ACTION_WRITE) as call:
            buf = call.buffer(len(data))
            self.mem.w_block(buf, data)
            call.arg(1, fh.fh_arg1)
            call.arg(2, buf)
            call.arg(3, len(data))
            return call.send()

    def seek(self, fh, offset, whence):
        with self._call(DosAction.ACTION_SEEK) as call:
            call.arg(1, fh.fh_arg1)
            call.arg(2, offset)
            call.arg(3, whence)
            return call.send()

    def set_file_size(self, fh, size, mode):
        with self._call(DosAction.ACTION_SET_FILE_SIZE) as call:
            call.arg(1, fh.fh_arg1)
            call.arg(2, size)
            call.arg(3, mode)
            return call.send()

    def flush(self, fh):
        with self._call(DosAction.ACTION_FLUSH) as call:
            call.arg(1, fh.fh_arg1)
            call.send()

    def end(self, fh):
        with self._call(DosAction.ACTION_END) as call:
            call.arg(1, fh.fh_arg1)
            call.send()

    def set_mode(self, fh, cooked):
        with self._call(DosAction.ACTION_SCREEN_MODE) as call:
            call.arg(1, 0 if cooked else 1)
            return bool(call.send())

    def wait_for_char(self, fh, timeout):
        with self._call(DosAction.ACTION_WAIT_CHAR) as call:
            call.arg(1, timeout)
            return bool(call.send())

    # ----- names -----

    def delete_object(self, ami_path):
        with self._call(DosAction.ACTION_DELETE_OBJECT) as call:
            call.arg(1, 0)
            call.arg(2, call.bstr(ami_path))
            call.send()

    def rename_object(self, old_path, new_path):
        with self._call(DosAction.ACTION_RENAME_OBJECT) as call:
            call.arg(1, 0)
            call.arg(2, call.bstr(old_path))
            call.arg(3, 0)
            call.arg(4, call.bstr(new_path))
            call.send()

    def set_protect(self, ami_path, mask):
        with self._call(DosAction.ACTION_SET_PROTECT) as call:
            call.arg(1, 0)
            call.arg(2, call.bstr(ami_path))
            call.arg(3, mask)
            call.send()

    def set_comment(self, ami_path, comment):
        with self._call(DosAction.ACTION_SET_COMMENT) as call:
            call.arg(1, 0)
            call.arg(2, call.bstr(ami_path))
            call.arg(3, call.bstr(comment))
            call.send()

    def set_date(self, ami_path, date):
        with self._call(DosAction.ACTION_SET_DATE) as call:
            call.arg(1, 0)
            call.arg(2, call.bstr(ami_path))
            call.arg(3, call.date(date))
            call.send()

    def create_dir(self, ami_path):
        with self._call(DosAction.ACTION_CREATE_DIR) as call:
            call.arg(1, 0)
            call.arg(2, call.bstr(ami_path))
            bptr = call.send()
        if bptr == 0:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        return self._make_lock(bptr)
