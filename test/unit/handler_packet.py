"""Packet handler (``handler/packet.py``) tests.

The client builds one packet per handler method call; a recording transport
asserts the exact ``dp_Type``/``dp_Arg*`` a method builds and that
``dp_Res1``/``dp_Res2`` are translated back correctly. The matching server
side -- a real handler driven by packets through the decoder -- is covered in
``handler_decode.py`` (``TestDecoderContract``).
"""

import pytest
from handler_contract import expect_error

from amitools.vamos.handler import (
    MODE_NEWFILE,
    MODE_OLDFILE,
    MODE_READWRITE,
    HandlerFileInfo,
    PacketFile,
    PacketHandler,
)
from amitools.vamos.handler.packet import EXCLUSIVE_LOCK, SHARED_LOCK
from amitools.vamos.lib.dos.AmiTime import AmiTime, ami_to_sys_time
from amitools.vamos.lib.dos.action import DosAction
from amitools.vamos.libstructs import (
    DateStampStruct,
    FileHandleStruct,
    FileInfoBlockStruct,
)
from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc

_FIND_ACTIONS = (
    DosAction.ACTION_FINDINPUT,
    DosAction.ACTION_FINDOUTPUT,
    DosAction.ACTION_FINDUPDATE,
    DosAction.ACTION_FH_FROM_LOCK,
)


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
        "arg5": pkt.arg5.val,
    }
    if action in (DosAction.ACTION_RENAME_DISK, DosAction.ACTION_FORMAT):
        rec["path"] = mem.r_bstr(pkt.arg1.val << 2)
    elif action in (
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
    elif action == DosAction.ACTION_MAKE_LINK:
        rec["name"] = mem.r_bstr(pkt.arg2.val << 2)
        rec["soft"] = pkt.arg4.val == 1
        if rec["soft"]:
            rec["dest"] = mem.r_cstr(pkt.arg3.val)
    elif action == DosAction.ACTION_READ_LINK:
        rec["path"] = mem.r_cstr(pkt.arg2.val)
    elif action == DosAction.ACTION_SET_OWNER:
        rec["path"] = mem.r_bstr(pkt.arg3.val << 2)
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


def handler_packet_volume_actions_test(rec):
    rec.rename_disk("newvol")
    call = rec.last()
    assert call["action"] == DosAction.ACTION_RENAME_DISK
    assert call["path"] == "newvol"
    assert rec.name == "newvol"

    rec.result = 3
    assert rec.more_cache(5) == 3
    call = rec.last()
    assert call["action"] == DosAction.ACTION_MORE_CACHE
    assert call["arg1"] == 5

    rec.inhibit(True)
    assert rec.last()["action"] == DosAction.ACTION_INHIBIT
    assert rec.last()["arg1"] == 1
    rec.inhibit(False)
    assert rec.last()["arg1"] == 0

    rec.format("vol", 0x444F5300)
    call = rec.last()
    assert call["action"] == DosAction.ACTION_FORMAT
    assert call["path"] == "vol"
    assert call["arg2"] == 0x444F5300
    assert rec.name == "vol"

    rec.write_protect(True)
    assert rec.last()["action"] == DosAction.ACTION_WRITE_PROTECT
    assert rec.last()["arg1"] == 1
    assert rec.write_protected is True
    rec.write_protect(False)
    assert rec.write_protected is False

    rec.result = 1
    assert rec.is_filesystem() is True
    assert rec.last()["action"] == DosAction.ACTION_IS_FILESYSTEM
    rec.result = 0
    assert rec.is_filesystem() is False


def handler_packet_link_marshalling_test(rec):
    lock = rec.locate_object("")
    rec.make_link(lock, "link", "target", soft=True)
    call = rec.last()
    assert call["action"] == DosAction.ACTION_MAKE_LINK
    assert call["arg1"] == lock.bptr
    assert call["name"] == "link"
    assert call["soft"] is True
    assert call["dest"] == "target"
    assert call["arg4"] == 1
    # a hard link carries the target lock in dp_Arg3
    target = rec.locate_object("t")
    rec.make_link(lock, "hard", target, soft=False)
    call = rec.last()
    assert call["soft"] is False
    assert call["arg3"] == target.bptr
    assert call["arg4"] == 0


def handler_packet_read_link_test(rec):
    lock = rec.locate_object("")

    def fill(pkt):
        rec.mem.w_cstr(pkt.arg3.val, "target")

    rec.on_call = fill
    rec.result = len("target")
    assert rec.read_link(lock, "link", 32) == "target"
    call = rec.last()
    assert call["action"] == DosAction.ACTION_READ_LINK
    assert call["arg1"] == lock.bptr
    assert call["path"] == "link"
    assert call["arg4"] == 32


def handler_packet_change_mode_test(rec):
    lock = rec.locate_object("f")
    rec.change_mode(lock, -2)
    call = rec.last()
    assert call["action"] == DosAction.ACTION_CHANGE_MODE
    assert call["arg1"] == 0  # CHANGE_LOCK
    assert call["arg2"] == lock.bptr
    assert call["arg3"] == -2
    fh = PacketFile(0x44, "f")
    rec.change_mode(fh, -1)
    call = rec.last()
    assert call["arg1"] == 1  # CHANGE_FH
    assert call["arg2"] == 0x44
    assert call["arg3"] == -1


def handler_packet_examine_fh_test(rec):
    fh = PacketFile(0x55, "f")

    def fill(pkt):
        fib = FileInfoBlockStruct(rec.mem, pkt.arg2.val)
        rec.mem.w_cstr(fib.fib_FileName.addr, "f")
        fib.fib_DirEntryType.val = HandlerFileInfo.FILE
        fib.fib_Size.val = 5

    rec.on_call = fill
    info = rec.examine_fh(fh)
    assert info.name == "f"
    assert info.entry_type == HandlerFileInfo.FILE
    assert info.size == 5
    call = rec.last()
    assert call["action"] == DosAction.ACTION_EXAMINE_FH
    assert call["arg1"] == 0x55


def handler_packet_set_owner_test(rec):
    lock = rec.locate_object("")
    rec.set_owner(lock, "f", 0x1234)
    call = rec.last()
    assert call["action"] == DosAction.ACTION_SET_OWNER
    assert call["arg2"] == lock.bptr
    assert call["path"] == "f"
    assert call["arg4"] == 0x1234


def handler_packet_record_locks_test(rec):
    fh = PacketFile(0x66, "f")
    rec.lock_record(fh, 0, 10, 0, 50)
    call = rec.last()
    assert call["action"] == DosAction.ACTION_LOCK_RECORD
    assert call["arg1"] == 0x66
    assert call["arg2"] == 0
    assert call["arg3"] == 10
    assert call["arg4"] == 0
    assert call["arg5"] == 50
    rec.free_record(fh, 0, 10)
    call = rec.last()
    assert call["action"] == DosAction.ACTION_FREE_RECORD
    assert call["arg1"] == 0x66
    assert call["arg2"] == 0
    assert call["arg3"] == 10


def handler_packet_notify_test(rec):
    rec.add_notify(0x1234)
    assert rec.last()["action"] == DosAction.ACTION_ADD_NOTIFY
    assert rec.last()["arg1"] == 0x1234
    rec.remove_notify(0x1234)
    assert rec.last()["action"] == DosAction.ACTION_REMOVE_NOTIFY
    assert rec.last()["arg1"] == 0x1234


def handler_packet_filehandle_missing_obj_test():
    from amitools.vamos.lib.dos.FileHandle import FileHandle

    fh = PacketFile(0x11, "f")
    dos_fh = FileHandle(fh.fobj, "f", "f", handler=PacketFile, handler_file=fh)
    assert dos_fh.is_interactive() is False
    assert dos_fh.tell() == -1
