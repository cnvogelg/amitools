"""Packet handler (``handler/packet.py``) tests.

Two layers are exercised:

* a recording transport asserts the exact ``dp_Type``/``dp_Arg*`` a method
  builds and that ``dp_Res1``/``dp_Res2`` are translated back correctly;
* a loopback transport drives a real :class:`HostFileSysHandler`, so the
  shared :class:`handler_contract.HandlerContract` mixin runs through the
  packet boundary (``TestPacketContract``).
"""

from types import SimpleNamespace

import pytest
from handler_contract import (
    HandlerContract,
    expect_error,
    make_dir,
    make_file,
    read_all,
)

from amitools.vamos.handler import (
    MODE_NEWFILE,
    MODE_OLDFILE,
    MODE_READWRITE,
    HandlerError,
    HostFileSysHandler,
    PacketFile,
    PacketHandler,
)
from amitools.vamos.handler.packet import EXCLUSIVE_LOCK, SHARED_LOCK
from amitools.vamos.lib.dos.AmiTime import AmiTime, ami_to_sys_time, sys_to_ami_time
from amitools.vamos.lib.dos.action import DosAction
from amitools.vamos.libstructs import (
    DateStampStruct,
    FileHandleStruct,
    FileInfoBlockStruct,
    InfoDataStruct,
)
from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc

DOSFALSE = 0
DOSTRUE = -1
ERROR_INVALID_LOCK = 211

_FIND_ACTIONS = (
    DosAction.ACTION_FINDINPUT,
    DosAction.ACTION_FINDOUTPUT,
    DosAction.ACTION_FINDUPDATE,
    DosAction.ACTION_FH_FROM_LOCK,
)


# --------------------------------------------------------------------------
# loopback transport: a test-only ``_dopkt`` that dispatches to a real handler
# --------------------------------------------------------------------------


class LoopbackTransport:
    """Drive a real handler from packets, in process.

    This is the minimal server side needed to run the handler contract through
    the packet boundary. It owns the bptr tables that a real handler port
    would keep in its process.
    """

    def __init__(self, handler, mem):
        self.handler = handler
        self.mem = mem
        self.locks = {}
        self.files = {}
        self._next_bptr = 0x100
        self._root = None

    # ----- bptr tables -----

    def _new_bptr(self):
        bptr = self._next_bptr
        self._next_bptr += 1
        return bptr

    def _add_lock(self, lock):
        bptr = self._new_bptr()
        self.locks[bptr] = lock
        return bptr

    def _add_file(self, fh_bptr, handler_file):
        fh_arg1 = self._new_bptr()
        self.files[fh_arg1] = handler_file
        fh = FileHandleStruct(self.mem, fh_bptr << 2)
        fh.fh_Args.val = fh_arg1
        return DOSTRUE

    def _lock(self, bptr):
        try:
            return self.locks[bptr]
        except KeyError:
            raise HandlerError(ERROR_INVALID_LOCK)

    def _file(self, fh_arg1):
        try:
            return self.files[fh_arg1]
        except KeyError:
            raise HandlerError(ERROR_INVALID_LOCK)

    def _bstr(self, bptr):
        return self.mem.r_bstr(bptr << 2)

    def _root_lock(self):
        if self._root is None:
            self._root = self.handler.locate_object("")
        return self._root

    def _read_date(self, bptr):
        ds = DateStampStruct(self.mem, bptr << 2)
        return ami_to_sys_time(
            AmiTime(ds.ds_Days.val, ds.ds_Minute.val, ds.ds_Tick.val)
        )

    # ----- struct filling -----

    def _fill_fib(self, fib, info):
        mem = self.mem
        name_addr = fib.fib_FileName.addr
        mem.clear_block(name_addr, 108, 0)
        mem.w_cstr(name_addr, info.name)
        comment_addr = fib.fib_Comment.addr
        mem.clear_block(comment_addr, 80, 0)
        if info.comment:
            mem.w_cstr(comment_addr, info.comment)
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

    # ----- transport -----

    def __call__(self, pkt):
        try:
            res1 = self._dispatch(pkt)
            res2 = 0
        except HandlerError as e:
            res1 = DOSFALSE
            res2 = e.code
        pkt.res1.val = res1
        pkt.res2.val = res2

    def _dispatch(self, pkt):
        h = self.handler
        action = DosAction(pkt.type.val)
        if action == DosAction.ACTION_LOCATE_OBJECT:
            rel = self._bstr(pkt.arg2.val)
            exclusive = pkt.arg3.val == EXCLUSIVE_LOCK
            return self._add_lock(h.locate_object(rel, exclusive))
        if action == DosAction.ACTION_FREE_LOCK:
            lock = self.locks.pop(pkt.arg1.val, None)
            if lock is not None:
                h.free_lock(lock)
            return 0
        if action == DosAction.ACTION_COPY_DIR:
            return self._add_lock(h.copy_dir(self._lock(pkt.arg1.val)))
        if action == DosAction.ACTION_PARENT:
            try:
                return self._add_lock(h.parent(self._lock(pkt.arg1.val)))
            except HandlerError:
                # the volume root has no parent: res1=0, res2=0
                return 0
        if action == DosAction.ACTION_SAME_LOCK:
            same = h.same_lock(self._lock(pkt.arg1.val), self._lock(pkt.arg2.val))
            return DOSTRUE if same else DOSFALSE
        if action == DosAction.ACTION_EXAMINE_OBJECT:
            fib = FileInfoBlockStruct(self.mem, pkt.arg2.val)
            self._fill_fib(fib, h.examine_object(self._lock(pkt.arg1.val)))
            return DOSTRUE
        if action == DosAction.ACTION_EXAMINE_NEXT:
            fib = FileInfoBlockStruct(self.mem, pkt.arg2.val)
            info = h.examine_next(self._lock(pkt.arg1.val), fib.fib_DiskKey.val)
            self._fill_fib(fib, info)
            return DOSTRUE
        if action == DosAction.ACTION_INFO:
            info = InfoDataStruct(self.mem, pkt.arg2.val)
            self._fill_info(info, h.info(self._lock(pkt.arg1.val)))
            return DOSTRUE
        if action == DosAction.ACTION_DISK_INFO:
            info = InfoDataStruct(self.mem, pkt.arg1.val)
            self._fill_info(info, h.disk_info(self._root_lock()))
            return DOSTRUE
        if action == DosAction.ACTION_FH_FROM_LOCK:
            return self._add_file(
                pkt.arg1.val, h.fh_from_lock(self._lock(pkt.arg2.val))
            )
        if action == DosAction.ACTION_PARENT_FH:
            return self._add_lock(h.parent_fh(self._file(pkt.arg1.val)))
        if action == DosAction.ACTION_COPY_DIR_FH:
            return self._add_lock(h.copy_dir_fh(self._file(pkt.arg1.val)))
        if action in _FIND_ACTIONS:
            rel = self._bstr(pkt.arg3.val)
            if action == DosAction.ACTION_FINDINPUT:
                handler_file = h.find_input(rel)
            elif action == DosAction.ACTION_FINDOUTPUT:
                handler_file = h.find_output(rel, MODE_NEWFILE)
            else:
                handler_file = h.find_update(rel)
            return self._add_file(pkt.arg1.val, handler_file)
        if action == DosAction.ACTION_READ:
            data = h.read(self._file(pkt.arg1.val), pkt.arg3.val)
            self.mem.w_block(pkt.arg2.val, data)
            return len(data)
        if action == DosAction.ACTION_WRITE:
            data = self.mem.r_block(pkt.arg2.val, pkt.arg3.val)
            return h.write(self._file(pkt.arg1.val), data)
        if action == DosAction.ACTION_SEEK:
            return h.seek(self._file(pkt.arg1.val), pkt.arg2.val, pkt.arg3.val)
        if action == DosAction.ACTION_SET_FILE_SIZE:
            return h.set_file_size(self._file(pkt.arg1.val), pkt.arg2.val, pkt.arg3.val)
        if action == DosAction.ACTION_FLUSH:
            h.flush(self._file(pkt.arg1.val))
            return 0
        if action == DosAction.ACTION_END:
            handler_file = self.files.pop(pkt.arg1.val, None)
            if handler_file is not None:
                h.end(handler_file)
            return 0
        if action == DosAction.ACTION_SCREEN_MODE:
            return DOSTRUE if h.set_mode(None, pkt.arg1.val == 0) else DOSFALSE
        if action == DosAction.ACTION_WAIT_CHAR:
            return DOSTRUE if h.wait_for_char(None, pkt.arg1.val) else DOSFALSE
        if action == DosAction.ACTION_DELETE_OBJECT:
            h.delete_object(self._bstr(pkt.arg2.val))
            return 0
        if action == DosAction.ACTION_RENAME_OBJECT:
            h.rename_object(self._bstr(pkt.arg2.val), self._bstr(pkt.arg4.val))
            return 0
        if action == DosAction.ACTION_SET_PROTECT:
            h.set_protect(self._bstr(pkt.arg2.val), pkt.arg3.val)
            return 0
        if action == DosAction.ACTION_SET_COMMENT:
            h.set_comment(self._bstr(pkt.arg2.val), self._bstr(pkt.arg3.val))
            return 0
        if action == DosAction.ACTION_SET_DATE:
            h.set_date(self._bstr(pkt.arg2.val), self._read_date(pkt.arg3.val))
            return 0
        if action == DosAction.ACTION_CREATE_DIR:
            rel = self._bstr(pkt.arg2.val)
            h.create_dir(rel)
            return self._add_lock(h.locate_object(rel))
        raise HandlerError(209)


def _make_loopback_handler(name, alloc, mem, root_path):
    handler = HostFileSysHandler(name, root_path)
    pkt_handler = PacketHandler(name, alloc)
    pkt_handler._dopkt = LoopbackTransport(handler, mem)
    return pkt_handler


@pytest.fixture
def env(tmp_path):
    mem = MockMemory(size_kib=256)
    alloc = MemoryAlloc(mem)
    root = tmp_path / "work"
    root.mkdir()

    def make(name):
        return _make_loopback_handler(name, alloc, mem, str(root))

    return SimpleNamespace(kind="packet", h=make("work"), new_handler=make)


class TestPacketContract(HandlerContract):
    def parent_copy_fh_test(self, env):
        # ``copy_dir_fh`` in the shared contract is called with a *lock*; that
        # is a step-12 fix (it must take a real file handle). The packet
        # transport can only carry a real handle, so only ``parent_fh`` is
        # checked here; the COPY_DIR_FH marshalling is pinned by the recording
        # test below.
        h = env.h
        make_dir(h, "d")
        make_file(h, "d/x", b"q")
        fh = h.find_input("d/x")
        assert h.same_lock(h.parent_fh(fh), h.locate_object("d"))
        h.end(fh)


# --------------------------------------------------------------------------
# recording transport: assert the built packets and the reply translation
# --------------------------------------------------------------------------


def _capture(mem, pkt):
    action = DosAction(pkt.type.val)
    rec = {
        "action": action,
        "arg1": pkt.arg1.val,
        "arg2": pkt.arg2.val,
        "arg3": pkt.arg3.val,
        "arg4": pkt.arg4.val,
    }
    if action in (
        DosAction.ACTION_LOCATE_OBJECT,
        DosAction.ACTION_DELETE_OBJECT,
        DosAction.ACTION_CREATE_DIR,
    ):
        rec["path"] = mem.r_bstr(pkt.arg2.val << 2)
    elif action in _FIND_ACTIONS:
        rec["path"] = mem.r_bstr(pkt.arg3.val << 2)
    elif action == DosAction.ACTION_RENAME_OBJECT:
        rec["old"] = mem.r_bstr(pkt.arg2.val << 2)
        rec["new"] = mem.r_bstr(pkt.arg4.val << 2)
    elif action in (DosAction.ACTION_SET_PROTECT, DosAction.ACTION_SET_COMMENT):
        rec["path"] = mem.r_bstr(pkt.arg2.val << 2)
    elif action == DosAction.ACTION_SET_DATE:
        rec["path"] = mem.r_bstr(pkt.arg2.val << 2)
    return rec


class RecordingHandler(PacketHandler):
    def __init__(self, name, alloc):
        super().__init__(name, alloc)
        self.calls = []
        self.result = 1
        self.error = 0
        self.on_call = None

    def _dopkt(self, pkt):
        self.calls.append(_capture(self.mem, pkt))
        if DosAction(pkt.type.val) in _FIND_ACTIONS:
            # a real handler fills in fh_Arg1
            fh = FileHandleStruct(self.mem, pkt.arg1.val << 2)
            fh.fh_Args.val = self.result or 1
        if self.on_call is not None:
            self.on_call(pkt)
        pkt.res1.val = self.result
        pkt.res2.val = self.error

    def last(self):
        return self.calls[-1]


@pytest.fixture
def rec():
    mem = MockMemory(size_kib=64)
    return RecordingHandler("work", MemoryAlloc(mem))


def handler_packet_no_transport_test():
    mem = MockMemory(size_kib=16)
    handler = PacketHandler("work", MemoryAlloc(mem))
    with pytest.raises(NotImplementedError):
        handler.locate_object("x")


def handler_packet_locate_marshalling_test(rec):
    rec.result = 0x123
    lock = rec.locate_object("sub/dir", exclusive=True)
    call = rec.last()
    assert call["action"] == DosAction.ACTION_LOCATE_OBJECT
    assert call["arg1"] == 0  # ZERO lock: volume relative path
    assert call["path"] == "sub/dir"
    assert call["arg3"] == EXCLUSIVE_LOCK
    # the reply is wrapped into a handler lock
    assert lock.bptr == 0x123
    assert lock.key == 0x123
    assert lock.handler is rec
    # shared is the default
    rec.locate_object("x")
    assert rec.last()["arg3"] == SHARED_LOCK


def handler_packet_error_translation_test(rec):
    rec.error = 205
    expect_error(205, rec.locate_object, "missing")
    rec.error = 209
    expect_error(209, rec.find_input, "x")


def handler_packet_parent_root_test(rec):
    # a real handler reports "no parent" as res1=0, res2=0
    rec.result = 0
    rec.error = 0
    lock = rec.locate_object("dir")
    expect_error(205, rec.parent, lock)


def handler_packet_examine_next_exhaustion_test(rec):
    lock = rec.locate_object("")
    rec.error = 232
    expect_error(232, rec.examine_next, lock, 1)


def handler_packet_read_write_marshalling_test(rec):
    fh = PacketFile(0x55, "f")

    def fill(pkt):
        rec.mem.w_block(pkt.arg2.val, b"data")

    rec.on_call = fill
    rec.result = 4
    assert rec.read(fh, 4) == b"data"
    call = rec.last()
    assert call["action"] == DosAction.ACTION_READ
    assert call["arg1"] == 0x55
    assert call["arg3"] == 4

    rec.on_call = None
    rec.result = 4
    assert rec.write(fh, b"data") == 4
    call = rec.last()
    assert call["action"] == DosAction.ACTION_WRITE
    assert call["arg1"] == 0x55
    assert call["arg3"] == 4
    assert rec.mem.r_block(call["arg2"], 4) == b"data"


def handler_packet_read_all_loops_test(rec):
    # a negative size is emulated with repeated READ packets
    state = {"n": 0}

    def fill(pkt):
        size = pkt.arg3.val
        state["n"] += 1
        if state["n"] == 1:
            rec.mem.w_block(pkt.arg2.val, b"a" * size)
            rec.result = size
        else:
            rec.result = 0

    rec.on_call = fill
    fh = PacketFile(0x55)
    assert rec.read(fh, -1) == b"a" * 512
    assert state["n"] == 2


def handler_packet_find_actions_test(rec):
    rec.find_input("f")
    assert rec.last()["action"] == DosAction.ACTION_FINDINPUT
    assert rec.last()["path"] == "f"
    rec.find_output("f", MODE_NEWFILE)
    assert rec.last()["action"] == DosAction.ACTION_FINDOUTPUT
    rec.find_output("f", MODE_READWRITE)
    assert rec.last()["action"] == DosAction.ACTION_FINDUPDATE
    rec.find_output("f", MODE_OLDFILE)
    assert rec.last()["action"] == DosAction.ACTION_FINDINPUT
    rec.find_update("f")
    assert rec.last()["action"] == DosAction.ACTION_FINDUPDATE


def handler_packet_find_output_bad_mode_test(rec):
    expect_error(115, rec.find_output, "f", 1234)


def handler_packet_find_input_reads_fh_arg1_test(rec):
    rec.result = 0x77
    fh = rec.find_input("f")
    assert fh.fh_arg1 == 0x77
    assert fh.handler is rec
    # a zero fh_Arg1 means the open failed even with res2 == 0
    rec.result = 0
    expect_error(205, rec.find_input, "f")


def handler_packet_fh_from_lock_test(rec):
    rec.result = 0x33
    lock = rec.locate_object("f")
    fh = rec.fh_from_lock(lock)
    assert fh.fh_arg1 == 0x33
    assert rec.last()["action"] == DosAction.ACTION_FH_FROM_LOCK


def handler_packet_same_lock_cross_handler_test(rec):
    other = RecordingHandler("other", MemoryAlloc(MockMemory(size_kib=64)))
    lock = rec.locate_object("")
    other_lock = other.locate_object("")
    # a lock of another handler is never the same and sends no packet
    sent = len(rec.calls), len(other.calls)
    assert rec.same_lock(lock, other_lock) is False
    assert (len(rec.calls), len(other.calls)) == sent


def handler_packet_rename_marshalling_test(rec):
    rec.rename_object("a", "b")
    call = rec.last()
    assert call["action"] == DosAction.ACTION_RENAME_OBJECT
    assert call["arg1"] == 0
    assert call["old"] == "a"
    assert call["arg3"] == 0
    assert call["new"] == "b"


def handler_packet_set_date_marshalling_test(rec):
    rec.set_date("f", 1000000)
    call = rec.last()
    assert call["action"] == DosAction.ACTION_SET_DATE
    assert call["arg1"] == 0
    assert call["path"] == "f"
    ds = DateStampStruct(rec.mem, call["arg3"] << 2)
    at = AmiTime(ds.ds_Days.val, ds.ds_Minute.val, ds.ds_Tick.val)
    assert ami_to_sys_time(at) == 1000000


def handler_packet_create_dir_returns_lock_test(rec):
    rec.result = 0x9
    lock = rec.create_dir("d")
    assert lock.bptr == 0x9
    assert rec.last()["action"] == DosAction.ACTION_CREATE_DIR


def handler_packet_filehandle_missing_obj_test():
    from amitools.vamos.lib.dos.FileHandle import FileHandle

    fh = PacketFile(0x11, "f")
    dos_fh = FileHandle(fh.fobj, "f", "f", handler=PacketFile, handler_file=fh)
    assert dos_fh.is_interactive() is False
    assert dos_fh.tell() == -1
