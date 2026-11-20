"""Packet decoder: map incoming AmigaDOS packets onto handler actions.

The handler API is a 1:1 model of the AmigaDOS ``ACTION_*`` packets (see
:data:`~amitools.vamos.handler.base.ACTION_METHODS`).
:mod:`amitools.vamos.handler.packet` is the *client* side: it turns a handler
method call into a :class:`~amitools.vamos.libtypes.DosPacket`.
:class:`PacketDecoder` is the *server* side: it reads a received
``DosPacket``, resolves the packet's target, calls the matching handler method
and writes ``dp_Res1``/``dp_Res2``. It is the counterpart of the client and
lets a handler port behave like a real AmigaDOS handler.

The module is free of dos.library imports. The DOS layer injects small
resolver callbacks that translate the opaque handles carried in a packet
(lock BPTRs, file-handle ids) into handler objects and register the result of
an action back as a DOS handle:

* ``resolve_fh(fh_id)`` -> ``(handler, handler_file, ami_path)``
* ``resolve_lock(lock_id)`` -> ``(handler, handler_lock, ami_path)``
* ``volume_handler()`` -> the handler this decoder serves (its port's handler)
* ``register_lock(handler, handler_lock, ami_path)`` -> ``lock_id``
* ``register_file(handler, handler_file, ami_path)`` -> ``fh_id``
* ``release_lock(lock_id)`` / ``release_file(fh_id)`` (optional) release a DOS
  handle when the packet does (``FREE_LOCK`` / ``END``)

A decoder is scoped to one handler: an fh/lock packet whose handle is owned by
a *different* handler is rejected with ``ERROR_INVALID_LOCK``, so only the
handler's own port can resolve its handles (like a real handler process).

The marshalling is the server direction of the table in ``HANDLER.md``:
path packets use the ZERO lock and a BSTR path, fh/lock packets carry the DOS
handle id, and ``dp_Res2`` reports the :class:`HandlerError` code.
"""

from amitools.vamos.lib.dos.AmiTime import AmiTime, ami_to_sys_time, sys_to_ami_time
from amitools.vamos.lib.dos.action import DosAction
from amitools.vamos.libstructs import (
    DateStampStruct,
    FileHandleStruct,
    FileInfoBlockStruct,
    InfoDataStruct,
)
from amitools.vamos.log import log_handler
from amitools.vamos.path.amipath import AmiPath

from .base import (
    ERROR_ACTION_NOT_KNOWN,
    ERROR_INVALID_LOCK,
    ERROR_LINE_TOO_LONG,
    MODE_NEWFILE,
    HandlerError,
)

DOSFALSE = 0
# DOSTRUE is 0xFFFFFFFF in AmigaDOS; dp_Res1 is a signed LONG so write -1
DOSTRUE = -1

# AmigaDOS lock modes (ACTION_LOCATE_OBJECT dp_Arg3)
EXCLUSIVE_LOCK = -1

# ACTION_CHANGE_MODE object type (dos/dos.h)
CHANGE_LOCK = 0
CHANGE_FH = 1

# ACTION_MAKE_LINK link type (dos/dos.h)
LINK_HARD = 0
LINK_SOFT = 1

# the FIND* packets that open a file: the handler fills in the caller's FH
_FIND_ACTIONS = (
    DosAction.ACTION_FINDINPUT,
    DosAction.ACTION_FINDOUTPUT,
    DosAction.ACTION_FINDUPDATE,
)


class PacketDecoder:
    """dispatch an incoming ``DosPacket`` to the matching handler method

    ``mem`` is the machine memory used to read/write the packet's buffers and
    result structures. The resolvers are injected by the DOS layer (see the
    module docstring) so the decoder never imports the DOS layer.
    """

    def __init__(
        self,
        mem,
        resolve_fh,
        resolve_lock,
        volume_handler,
        register_lock,
        register_file,
        release_lock=None,
        release_file=None,
    ):
        self.mem = mem
        self.resolve_fh = resolve_fh
        self.resolve_lock = resolve_lock
        self.volume_handler = volume_handler
        self.register_lock = register_lock
        self.register_file = register_file
        self.release_lock = release_lock
        self.release_file = release_file

    # ----- entry point -----

    def decode(self, pkt):
        """dispatch ``pkt`` and write ``dp_Res1``/``dp_Res2``

        Returns ``dp_Res1``. A :class:`HandlerError` becomes ``res1=DOSFALSE``
        and ``res2=code``; an unknown action becomes
        ``ERROR_ACTION_NOT_KNOWN``.
        """
        try:
            action = DosAction(pkt.type.val)
        except ValueError:
            log_handler.warning("unknown dos packet type %d", pkt.type.val)
            pkt.res1.val = DOSFALSE
            pkt.res2.val = ERROR_ACTION_NOT_KNOWN
            return DOSFALSE
        try:
            res1 = self._dispatch(action, pkt)
            res2 = 0
        except HandlerError as e:
            log_handler.info("dos packet %s failed: %s", action.name, e)
            res1 = DOSFALSE
            res2 = e.code
        if res1 is None:
            res1 = DOSFALSE
        pkt.res1.val = res1
        pkt.res2.val = res2
        return res1

    # ----- resolvers -----

    def _handler(self):
        handler = self.volume_handler()
        if handler is None:
            raise HandlerError(ERROR_ACTION_NOT_KNOWN)
        return handler

    def _owned(self, result):
        """check that a resolved handle belongs to this decoder's handler

        A dispatcher only serves the handler whose port it owns, so a packet
        that carries a handle owned by another handler is rejected like a real
        handler would (``ERROR_INVALID_LOCK``).
        """
        if result is None:
            raise HandlerError(ERROR_INVALID_LOCK)
        handler = self.volume_handler()
        if handler is None or result[0] is not handler:
            raise HandlerError(ERROR_INVALID_LOCK)
        return result

    def _fh(self, fh_id):
        return self._owned(self.resolve_fh(fh_id))

    def _lock(self, lock_id):
        return self._owned(self.resolve_lock(lock_id))

    def _register_lock(self, handler, handler_lock, ami_path):
        return self.register_lock(handler, handler_lock, ami_path)

    def _register_file(self, handler, handler_file, ami_path):
        return self.register_file(handler, handler_file, ami_path)

    def _register_file_in_struct(self, handler, handler_file, ami_path, fh_bptr):
        """register a handler file and store its id in the caller's FH struct"""
        fh_id = self._register_file(handler, handler_file, ami_path)
        fh = FileHandleStruct(self.mem, fh_bptr << 2)
        fh.fh_Args.val = fh_id
        return DOSTRUE

    # ----- helpers -----

    def _abs_path(self, handler, rel_path):
        return "%s:%s" % (handler.name, rel_path)

    def _parent_path(self, ami_path):
        parent = AmiPath(ami_path).parent()
        return str(parent) if parent is not None else ami_path

    def _read_date(self, addr):
        ds = DateStampStruct(self.mem, addr)
        return ami_to_sys_time(
            AmiTime(ds.ds_Days.val, ds.ds_Minute.val, ds.ds_Tick.val)
        )

    def _fill_fib(self, fib, info):
        """write a :class:`HandlerFileInfo` into a FileInfoBlock"""
        mem = self.mem
        # the handler writes fib_FileName/fib_Comment as BSTRs; dos.library
        # converts them to C strings (fixfib) before a program sees them
        name_addr = fib.fib_FileName.addr
        mem.clear_block(name_addr, 108, 0)
        mem.w_bstr(name_addr, info.name)
        comment_addr = fib.fib_Comment.addr
        mem.clear_block(comment_addr, 80, 0)
        if info.comment:
            mem.w_bstr(comment_addr, info.comment)
        fib.fib_DiskKey.val = info.key
        fib.fib_DirEntryType.val = info.entry_type
        fib.fib_EntryType.val = info.entry_type
        fib.fib_Protection.val = info.protection
        fib.fib_Size.val = info.size
        fib.fib_NumBlocks.val = info.blocks
        at = sys_to_ami_time(info.date)
        fib.fib_Date.ds_Days.val = at.tday
        fib.fib_Date.ds_Minute.val = at.tmin
        fib.fib_Date.ds_Tick.val = at.tick
        fib.fib_OwnerUID.val = info.owner_uid
        fib.fib_OwnerGID.val = info.owner_gid

    def _fill_info(self, info, data):
        info.id_NumSoftErrors.val = data.num_soft_errors
        info.id_UnitNumber.val = data.unit_number
        info.id_DiskState.val = data.disk_state
        info.id_NumBlocks.val = data.num_blocks
        info.id_NumBlocksUsed.val = data.num_blocks_used
        info.id_BytesPerBlock.val = data.bytes_per_block
        info.id_DiskType.val = data.disk_type

    # ----- dispatch -----

    def _dispatch(self, action, pkt):
        mem = self.mem
        a1 = pkt.arg1.val
        a2 = pkt.arg2.val
        a3 = pkt.arg3.val
        a4 = pkt.arg4.val
        a5 = pkt.arg5.val

        # --- locks ---

        if action == DosAction.ACTION_LOCATE_OBJECT:
            handler = self._handler()
            rel = mem.r_bstr(a2 << 2)
            lock = handler.locate_object(rel, a3 == EXCLUSIVE_LOCK)
            return self._register_lock(handler, lock, self._abs_path(handler, rel))

        if action == DosAction.ACTION_FREE_LOCK:
            self._release_lock(a1)
            return 0

        if action == DosAction.ACTION_COPY_DIR:
            handler, lock, ami_path = self._lock(a1)
            return self._register_lock(handler, handler.copy_dir(lock), ami_path)

        if action == DosAction.ACTION_PARENT:
            handler, lock, ami_path = self._lock(a1)
            try:
                new_lock = handler.parent(lock)
            except HandlerError:
                # the volume root has no parent: res1=0, res2=0
                return 0
            return self._register_lock(handler, new_lock, self._parent_path(ami_path))

        if action == DosAction.ACTION_SAME_LOCK:
            h1, l1, _ = self._lock(a1)
            h2, l2, _ = self._lock(a2)
            if h1 is not h2:
                return DOSFALSE
            return DOSTRUE if h1.same_lock(l1, l2) else DOSFALSE

        if action == DosAction.ACTION_EXAMINE_OBJECT:
            handler, lock, _ = self._lock(a1)
            self._fill_fib(
                FileInfoBlockStruct(mem, a2 << 2), handler.examine_object(lock)
            )
            return DOSTRUE

        if action == DosAction.ACTION_EXAMINE_NEXT:
            handler, lock, _ = self._lock(a1)
            fib = FileInfoBlockStruct(mem, a2 << 2)
            info = handler.examine_next(lock, fib.fib_DiskKey.val)
            self._fill_fib(fib, info)
            return DOSTRUE

        if action == DosAction.ACTION_INFO:
            handler, lock, _ = self._lock(a1)
            self._fill_info(InfoDataStruct(mem, a2 << 2), handler.info(lock))
            return DOSTRUE

        if action == DosAction.ACTION_DISK_INFO:
            handler = self._handler()
            self._fill_info(InfoDataStruct(mem, a1 << 2), handler.disk_info(None))
            return DOSTRUE

        if action == DosAction.ACTION_FH_FROM_LOCK:
            handler, lock, ami_path = self._lock(a2)
            handler_file = handler.fh_from_lock(lock)
            return self._register_file_in_struct(handler, handler_file, ami_path, a1)

        if action == DosAction.ACTION_PARENT_FH:
            handler, handler_file, ami_path = self._fh(a1)
            new_lock = handler.parent_fh(handler_file)
            return self._register_lock(handler, new_lock, self._parent_path(ami_path))

        if action == DosAction.ACTION_COPY_DIR_FH:
            handler, handler_file, ami_path = self._fh(a1)
            return self._register_lock(
                handler, handler.copy_dir_fh(handler_file), ami_path
            )

        # --- files ---

        if action in _FIND_ACTIONS:
            handler = self._handler()
            rel = mem.r_bstr(a3 << 2)
            if action == DosAction.ACTION_FINDINPUT:
                handler_file = handler.find_input(rel)
            elif action == DosAction.ACTION_FINDOUTPUT:
                handler_file = handler.find_output(rel, MODE_NEWFILE)
            else:
                handler_file = handler.find_update(rel)
            return self._register_file_in_struct(
                handler, handler_file, self._abs_path(handler, rel), a1
            )

        if action == DosAction.ACTION_READ:
            handler, handler_file, _ = self._fh(a1)
            data = handler.read(handler_file, a3)
            mem.w_block(a2, data)
            return len(data)

        if action == DosAction.ACTION_WRITE:
            handler, handler_file, _ = self._fh(a1)
            data = mem.r_block(a2, a3)
            return handler.write(handler_file, data)

        if action == DosAction.ACTION_SEEK:
            handler, handler_file, _ = self._fh(a1)
            return handler.seek(handler_file, a2, a3)

        if action == DosAction.ACTION_SET_FILE_SIZE:
            handler, handler_file, _ = self._fh(a1)
            return handler.set_file_size(handler_file, a2, a3)

        if action == DosAction.ACTION_FLUSH:
            handler, handler_file, _ = self._fh(a1)
            handler.flush(handler_file)
            return 0

        if action == DosAction.ACTION_END:
            self._release_file(a1)
            return 0

        if action == DosAction.ACTION_SCREEN_MODE:
            handler = self._handler()
            cooked = a1 == 0
            return DOSTRUE if handler.set_mode(None, cooked) else DOSFALSE

        if action == DosAction.ACTION_WAIT_CHAR:
            handler = self._handler()
            return DOSTRUE if handler.wait_for_char(None, a1) else DOSFALSE

        # --- names ---

        if action == DosAction.ACTION_DELETE_OBJECT:
            self._handler().delete_object(mem.r_bstr(a2 << 2))
            return 0

        if action == DosAction.ACTION_RENAME_OBJECT:
            self._handler().rename_object(mem.r_bstr(a2 << 2), mem.r_bstr(a4 << 2))
            return 0

        if action == DosAction.ACTION_SET_PROTECT:
            self._handler().set_protect(mem.r_bstr(a3 << 2), a4)
            return 0

        if action == DosAction.ACTION_SET_COMMENT:
            self._handler().set_comment(mem.r_bstr(a3 << 2), mem.r_bstr(a4 << 2))
            return 0

        if action == DosAction.ACTION_SET_DATE:
            self._handler().set_date(mem.r_bstr(a3 << 2), self._read_date(a4))
            return 0

        if action == DosAction.ACTION_CREATE_DIR:
            handler = self._handler()
            rel = mem.r_bstr(a2 << 2)
            handler.create_dir(rel)
            lock = handler.locate_object(rel)
            return self._register_lock(handler, lock, self._abs_path(handler, rel))

        # --- volume maintenance ---

        if action == DosAction.ACTION_RENAME_DISK:
            self._handler().rename_disk(mem.r_bstr(a1 << 2))
            return DOSTRUE

        if action == DosAction.ACTION_MORE_CACHE:
            return self._handler().more_cache(a1)

        if action == DosAction.ACTION_INHIBIT:
            self._handler().inhibit(a1 != 0)
            return DOSTRUE

        if action == DosAction.ACTION_FORMAT:
            self._handler().format(mem.r_bstr(a1 << 2), a2)
            return DOSTRUE

        if action == DosAction.ACTION_WRITE_PROTECT:
            self._handler().write_protect(a1 != 0)
            return DOSTRUE

        if action == DosAction.ACTION_IS_FILESYSTEM:
            return DOSTRUE if self._handler().is_filesystem() else DOSFALSE

        # --- links ---

        if action == DosAction.ACTION_MAKE_LINK:
            handler, lock, _ = self._lock(a1)
            name = mem.r_bstr(a2 << 2)
            if a4 == LINK_SOFT:
                dest = mem.r_cstr(a3)
            else:
                _h, dest, _ = self._lock(a3)
            handler.make_link(lock, name, dest, a4 == LINK_SOFT)
            return DOSTRUE

        if action == DosAction.ACTION_READ_LINK:
            handler, lock, _ = self._lock(a1)
            target = handler.read_link(lock, mem.r_cstr(a2), a4)
            if len(target) >= a4:
                raise HandlerError(ERROR_LINE_TOO_LONG)
            mem.w_cstr(a3, target)
            return len(target)

        # --- objects / metadata ---

        if action == DosAction.ACTION_CHANGE_MODE:
            if a1 == CHANGE_FH:
                handler, obj, _ = self._fh(a2)
            else:
                handler, obj, _ = self._lock(a2)
            handler.change_mode(obj, a3)
            return DOSTRUE

        if action == DosAction.ACTION_EXAMINE_FH:
            handler, fh, _ = self._fh(a1)
            self._fill_fib(FileInfoBlockStruct(mem, a2 << 2), handler.examine_fh(fh))
            return DOSTRUE

        if action == DosAction.ACTION_SET_OWNER:
            handler, lock, _ = self._lock(a2)
            handler.set_owner(lock, mem.r_bstr(a3 << 2), a4)
            return DOSTRUE

        # --- record locks ---

        if action == DosAction.ACTION_LOCK_RECORD:
            handler, fh, _ = self._fh(a1)
            handler.lock_record(fh, a2, a3, a4, a5)
            return DOSTRUE

        if action == DosAction.ACTION_FREE_RECORD:
            handler, fh, _ = self._fh(a1)
            handler.free_record(fh, a2, a3)
            return DOSTRUE

        # --- notification ---

        if action == DosAction.ACTION_ADD_NOTIFY:
            self._handler().add_notify(a1)
            return DOSTRUE

        if action == DosAction.ACTION_REMOVE_NOTIFY:
            self._handler().remove_notify(a1)
            return DOSTRUE

        raise HandlerError(ERROR_ACTION_NOT_KNOWN, "unsupported: %s" % action.name)

    # ----- release hooks -----

    def _release_lock(self, lock_id):
        # resolve first: the handle must belong to this handler's port
        handler, handler_lock, _ = self._lock(lock_id)
        if self.release_lock is not None:
            self.release_lock(lock_id)
            return
        handler.free_lock(handler_lock)

    def _release_file(self, fh_id):
        handler, handler_file, _ = self._fh(fh_id)
        if self.release_file is not None:
            self.release_file(fh_id)
            return
        handler.end(handler_file)
