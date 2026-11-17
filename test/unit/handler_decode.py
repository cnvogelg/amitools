"""Packet decoder (``handler/decode.py``) tests.

Two layers are exercised:

* a recording handler asserts the handler method + arguments the decoder
  dispatches to and the ``dp_Res1``/``dp_Res2`` it writes back;
* a loopback client drives a real :class:`HostFileSysHandler` through the
  decoder, so the shared :class:`handler_contract.HandlerContract` mixin runs
  through the packet boundary (``TestDecoderContract``).
"""

from types import SimpleNamespace

import pytest
from handler_contract import HandlerContract

from amitools.vamos.handler import (
    MODE_NEWFILE,
    MODE_OLDFILE,
    Handler,
    HandlerError,
    HandlerFile,
    HandlerFileInfo,
    HandlerInfoData,
    HandlerLock,
    HostFileSysHandler,
    PacketDecoder,
    PacketHandler,
)
from amitools.vamos.lib.dos.action import DosAction
from amitools.vamos.libstructs import (
    DateStampStruct,
    DosPacketStruct,
    FileHandleStruct,
    FileInfoBlockStruct,
    InfoDataStruct,
)
from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc

DOSFALSE = 0
DOSTRUE = -1
ERROR_INVALID_LOCK = 211
ERROR_OBJECT_NOT_FOUND = 205

EXCLUSIVE_LOCK = -1
SHARED_LOCK = -2


# --------------------------------------------------------------------------
# a decoder with in-memory handle tables (what dos.library provides in prod)
# --------------------------------------------------------------------------


class DecoderHarness:
    """a :class:`PacketDecoder` backed by dict-based handle tables

    It plays the role the DOS layer plays in production: it resolves the
    opaque lock/file ids carried in a packet to handler objects and registers
    the handler handles an action returns as new ids.
    """

    def __init__(self, handler, mem):
        self.handler = handler
        self.mem = mem
        self.locks = {}
        self.files = {}
        self._next_id = 0x100
        self.decoder = PacketDecoder(
            mem,
            resolve_fh=self._resolve_fh,
            resolve_lock=self._resolve_lock,
            volume_handler=lambda: handler,
            register_lock=self._register_lock,
            register_file=self._register_file,
            release_lock=self._release_lock,
            release_file=self._release_file,
        )

    def decode(self, pkt):
        return self.decoder.decode(pkt)

    # ----- handle tables -----

    def _new_id(self):
        self._next_id += 1
        return self._next_id

    def _resolve_fh(self, fh_id):
        if fh_id not in self.files:
            raise HandlerError(ERROR_INVALID_LOCK)
        handler, handler_file, ami_path = self.files[fh_id]
        return handler, handler_file, ami_path

    def _resolve_lock(self, lock_id):
        if lock_id not in self.locks:
            raise HandlerError(ERROR_INVALID_LOCK)
        handler, handler_lock, ami_path = self.locks[lock_id]
        return handler, handler_lock, ami_path

    def _register_lock(self, handler, handler_lock, ami_path):
        lock_id = self._new_id()
        self.locks[lock_id] = (handler, handler_lock, ami_path)
        return lock_id

    def _register_file(self, handler, handler_file, ami_path):
        fh_id = self._new_id()
        self.files[fh_id] = (handler, handler_file, ami_path)
        return fh_id

    def _release_lock(self, lock_id):
        self.locks.pop(lock_id, None)

    def _release_file(self, fh_id):
        self.files.pop(fh_id, None)


# --------------------------------------------------------------------------
# a recording handler: records the dispatched calls, returns canned values
# --------------------------------------------------------------------------


class RecordingHandler(Handler):
    def __init__(self, name="work"):
        super().__init__(name)
        self.calls = []
        self.lock = HandlerLock(key="lock")
        self.file = HandlerFile(key="file")
        self.fib_info = HandlerFileInfo("entry", HandlerFileInfo.FILE)
        self.disk_data = HandlerInfoData(num_blocks=42, num_blocks_used=7)
        self.same = True
        self.read_data = b""
        self.mode_result = True
        self.char_result = True
        self.error = None

    def _call(self, name, *args):
        self.calls.append((name,) + args)
        if self.error is not None:
            raise HandlerError(self.error)

    # locks
    def locate_object(self, ami_path, exclusive=False):
        self._call("locate_object", ami_path, exclusive)
        return self.lock

    def free_lock(self, lock):
        self._call("free_lock", lock)

    def copy_dir(self, lock):
        self._call("copy_dir", lock)
        return self.lock

    def parent(self, lock):
        self._call("parent", lock)
        return self.lock

    def same_lock(self, a, b):
        self._call("same_lock", a, b)
        return self.same

    def examine_object(self, lock):
        self._call("examine_object", lock)
        return self.fib_info

    def examine_next(self, lock, key):
        self._call("examine_next", lock, key)
        return self.fib_info

    def info(self, lock):
        self._call("info", lock)
        return self.disk_data

    def disk_info(self, lock):
        self._call("disk_info", lock)
        return self.disk_data

    def fh_from_lock(self, lock, mode=MODE_OLDFILE):
        self._call("fh_from_lock", lock)
        return self.file

    def parent_fh(self, fh):
        self._call("parent_fh", fh)
        return self.lock

    def copy_dir_fh(self, fh):
        self._call("copy_dir_fh", fh)
        return self.lock

    # files
    def find_input(self, ami_path):
        self._call("find_input", ami_path)
        return self.file

    def find_output(self, ami_path, mode=MODE_NEWFILE):
        self._call("find_output", ami_path, mode)
        return self.file

    def find_update(self, ami_path):
        self._call("find_update", ami_path)
        return self.file

    def read(self, fh, size):
        self._call("read", fh, size)
        return self.read_data

    def write(self, fh, data):
        self._call("write", fh, data)
        return len(data)

    def seek(self, fh, offset, whence):
        self._call("seek", fh, offset, whence)
        return offset

    def set_file_size(self, fh, size, mode):
        self._call("set_file_size", fh, size, mode)
        return size

    def flush(self, fh):
        self._call("flush", fh)

    def end(self, fh):
        self._call("end", fh)

    def set_mode(self, fh, cooked):
        self._call("set_mode", fh, cooked)
        return self.mode_result

    def wait_for_char(self, fh, timeout):
        self._call("wait_for_char", fh, timeout)
        return self.char_result

    # names
    def delete_object(self, ami_path):
        self._call("delete_object", ami_path)

    def rename_object(self, old_path, new_path):
        self._call("rename_object", old_path, new_path)

    def set_protect(self, ami_path, mask):
        self._call("set_protect", ami_path, mask)

    def set_comment(self, ami_path, comment):
        self._call("set_comment", ami_path, comment)

    def set_date(self, ami_path, date):
        self._call("set_date", ami_path, date)

    def create_dir(self, ami_path):
        self._call("create_dir", ami_path)


# --------------------------------------------------------------------------
# packet helpers
# --------------------------------------------------------------------------

_PKT_ADDR = 0x1000
_PATH_ADDR = 0x800
_PATH2_ADDR = 0x900
_BUF_ADDR = 0xA00
_FIB_ADDR = 0xC00
_INFO_ADDR = 0xD00
_DATE_ADDR = 0xE00
_FH_ADDR = 0x700


def _bstr(mem, text, addr):
    mem.w_bstr(addr, text)
    return addr >> 2


def _pkt(mem, action, arg1=0, arg2=0, arg3=0, arg4=0):
    pkt = DosPacketStruct(mem, _PKT_ADDR)
    pkt.type.val = action
    pkt.arg1.val = arg1
    pkt.arg2.val = arg2
    pkt.arg3.val = arg3
    pkt.arg4.val = arg4
    return pkt


@pytest.fixture
def dec():
    mem = MockMemory(size_kib=64)
    handler = RecordingHandler("work")
    return SimpleNamespace(mem=mem, h=handler, harness=DecoderHarness(handler, mem))


# --------------------------------------------------------------------------
# locks
# --------------------------------------------------------------------------


def handler_decode_locate_object_test(dec):
    mem, h = dec.mem, dec.h
    pkt = _pkt(
        mem,
        DosAction.ACTION_LOCATE_OBJECT,
        arg2=_bstr(mem, "sub/dir", _PATH_ADDR),
        arg3=EXCLUSIVE_LOCK,
    )
    lock_id = dec.harness.decode(pkt)
    assert h.calls[-1] == ("locate_object", "sub/dir", True)
    assert pkt.res2.val == 0
    assert dec.harness.locks[lock_id] == (h, h.lock, "work:sub/dir")
    # shared is the default
    dec.harness.decode(
        _pkt(
            mem,
            DosAction.ACTION_LOCATE_OBJECT,
            arg2=_bstr(mem, "x", _PATH_ADDR),
            arg3=SHARED_LOCK,
        )
    )
    assert h.calls[-1] == ("locate_object", "x", False)


def handler_decode_free_lock_test(dec):
    mem = dec.mem
    lock_id = dec.harness.decode(
        _pkt(mem, DosAction.ACTION_LOCATE_OBJECT, arg2=_bstr(mem, "", _PATH_ADDR))
    )
    pkt = _pkt(mem, DosAction.ACTION_FREE_LOCK, arg1=lock_id)
    assert dec.harness.decode(pkt) == 0
    assert lock_id not in dec.harness.locks


def handler_decode_copy_dir_test(dec):
    mem, h = dec.mem, dec.h
    src = dec.harness.decode(
        _pkt(mem, DosAction.ACTION_LOCATE_OBJECT, arg2=_bstr(mem, "d", _PATH_ADDR))
    )
    new = dec.harness.decode(_pkt(mem, DosAction.ACTION_COPY_DIR, arg1=src))
    assert h.calls[-1] == ("copy_dir", h.lock)
    assert dec.harness.locks[new] == (h, h.lock, "work:d")


def handler_decode_parent_test(dec):
    mem, h = dec.mem, dec.h
    src = dec.harness.decode(
        _pkt(mem, DosAction.ACTION_LOCATE_OBJECT, arg2=_bstr(mem, "a/b", _PATH_ADDR))
    )
    parent = dec.harness.decode(_pkt(mem, DosAction.ACTION_PARENT, arg1=src))
    assert h.calls[-1] == ("parent", h.lock)
    assert dec.harness.locks[parent] == (h, h.lock, "work:a")


def handler_decode_parent_root_test(dec):
    mem, h = dec.mem, dec.h
    src = dec.harness.decode(
        _pkt(mem, DosAction.ACTION_LOCATE_OBJECT, arg2=_bstr(mem, "", _PATH_ADDR))
    )
    h.error = ERROR_OBJECT_NOT_FOUND
    pkt = _pkt(mem, DosAction.ACTION_PARENT, arg1=src)
    # the volume root has no parent: res1=0, res2=0
    assert dec.harness.decode(pkt) == 0
    assert pkt.res2.val == 0


def handler_decode_same_lock_test(dec):
    mem, h = dec.mem, dec.h
    a = dec.harness.decode(
        _pkt(mem, DosAction.ACTION_LOCATE_OBJECT, arg2=_bstr(mem, "a", _PATH_ADDR))
    )
    b = dec.harness.decode(
        _pkt(mem, DosAction.ACTION_LOCATE_OBJECT, arg2=_bstr(mem, "a", _PATH_ADDR))
    )
    pkt = _pkt(mem, DosAction.ACTION_SAME_LOCK, arg1=a, arg2=b)
    assert dec.harness.decode(pkt) == DOSTRUE
    h.same = False
    assert dec.harness.decode(pkt) == DOSFALSE


def handler_decode_examine_object_test(dec):
    mem, h = dec.mem, dec.h
    src = dec.harness.decode(
        _pkt(mem, DosAction.ACTION_LOCATE_OBJECT, arg2=_bstr(mem, "f", _PATH_ADDR))
    )
    h.fib_info = HandlerFileInfo(
        "f", HandlerFileInfo.FILE, size=5, blocks=1, comment="c"
    )
    pkt = _pkt(mem, DosAction.ACTION_EXAMINE_OBJECT, arg1=src, arg2=_FIB_ADDR)
    assert dec.harness.decode(pkt) == DOSTRUE
    assert h.calls[-1] == ("examine_object", h.lock)
    fib = FileInfoBlockStruct(mem, _FIB_ADDR)
    assert mem.r_cstr(fib.fib_FileName.addr) == "f"
    assert fib.fib_Size.val == 5
    assert fib.fib_DirEntryType.val == HandlerFileInfo.FILE


def handler_decode_examine_next_test(dec):
    mem, h = dec.mem, dec.h
    src = dec.harness.decode(
        _pkt(mem, DosAction.ACTION_LOCATE_OBJECT, arg2=_bstr(mem, "", _PATH_ADDR))
    )
    fib = FileInfoBlockStruct(mem, _FIB_ADDR)
    fib.fib_DiskKey.val = 3
    h.fib_info = HandlerFileInfo("n", HandlerFileInfo.FILE, key=4)
    pkt = _pkt(mem, DosAction.ACTION_EXAMINE_NEXT, arg1=src, arg2=_FIB_ADDR)
    assert dec.harness.decode(pkt) == DOSTRUE
    assert h.calls[-1] == ("examine_next", h.lock, 3)
    assert fib.fib_DiskKey.val == 4


def handler_decode_info_test(dec):
    mem = dec.mem
    src = dec.harness.decode(
        _pkt(mem, DosAction.ACTION_LOCATE_OBJECT, arg2=_bstr(mem, "", _PATH_ADDR))
    )
    pkt = _pkt(mem, DosAction.ACTION_INFO, arg1=src, arg2=_INFO_ADDR)
    assert dec.harness.decode(pkt) == DOSTRUE
    info = InfoDataStruct(mem, _INFO_ADDR)
    assert info.id_NumBlocks.val == 42
    assert info.id_NumBlocksUsed.val == 7


def handler_decode_disk_info_test(dec):
    mem, h = dec.mem, dec.h
    pkt = _pkt(mem, DosAction.ACTION_DISK_INFO, arg1=_INFO_ADDR)
    assert dec.harness.decode(pkt) == DOSTRUE
    assert h.calls[-1] == ("disk_info", None)
    assert InfoDataStruct(mem, _INFO_ADDR).id_NumBlocks.val == 42


def handler_decode_fh_from_lock_test(dec):
    mem, h = dec.mem, dec.h
    src = dec.harness.decode(
        _pkt(mem, DosAction.ACTION_LOCATE_OBJECT, arg2=_bstr(mem, "f", _PATH_ADDR))
    )
    pkt = _pkt(mem, DosAction.ACTION_FH_FROM_LOCK, arg1=_FH_ADDR >> 2, arg2=src)
    assert dec.harness.decode(pkt) == DOSTRUE
    assert h.calls[-1] == ("fh_from_lock", h.lock)
    fh_id = dec.harness.files and list(dec.harness.files)[0]
    assert FileHandleStruct(mem, _FH_ADDR).fh_Args.val == fh_id


def handler_decode_parent_copy_fh_test(dec):
    mem, h = dec.mem, dec.h
    file_id = dec.harness._register_file(h, h.file, "work:f")
    parent = dec.harness.decode(_pkt(mem, DosAction.ACTION_PARENT_FH, arg1=file_id))
    assert h.calls[-1] == ("parent_fh", h.file)
    assert dec.harness.locks[parent] == (h, h.lock, "work:")
    copy = dec.harness.decode(_pkt(mem, DosAction.ACTION_COPY_DIR_FH, arg1=file_id))
    assert h.calls[-1] == ("copy_dir_fh", h.file)
    assert dec.harness.locks[copy] == (h, h.lock, "work:f")


# --------------------------------------------------------------------------
# files
# --------------------------------------------------------------------------


def handler_decode_find_actions_test(dec):
    mem, h = dec.mem, dec.h
    for action, expected in (
        (DosAction.ACTION_FINDINPUT, ("find_input", "f")),
        (DosAction.ACTION_FINDOUTPUT, ("find_output", "f", MODE_NEWFILE)),
        (DosAction.ACTION_FINDUPDATE, ("find_update", "f")),
    ):
        pkt = _pkt(mem, action, arg1=_FH_ADDR >> 2, arg3=_bstr(mem, "f", _PATH_ADDR))
        assert dec.harness.decode(pkt) == DOSTRUE
        assert h.calls[-1] == expected
        fh_id = mem.r32(_FH_ADDR + 36)
        assert fh_id in dec.harness.files
        assert dec.harness.files[fh_id] == (h, h.file, "work:f")


def handler_decode_read_test(dec):
    mem, h = dec.mem, dec.h
    fh_id = dec.harness._register_file(h, h.file, "work:f")
    h.read_data = b"hello"
    pkt = _pkt(mem, DosAction.ACTION_READ, arg1=fh_id, arg2=_BUF_ADDR, arg3=5)
    assert dec.harness.decode(pkt) == 5
    assert h.calls[-1] == ("read", h.file, 5)
    assert mem.r_block(_BUF_ADDR, 5) == b"hello"


def handler_decode_write_test(dec):
    mem, h = dec.mem, dec.h
    fh_id = dec.harness._register_file(h, h.file, "work:f")
    mem.w_block(_BUF_ADDR, b"data")
    pkt = _pkt(mem, DosAction.ACTION_WRITE, arg1=fh_id, arg2=_BUF_ADDR, arg3=4)
    assert dec.harness.decode(pkt) == 4
    assert h.calls[-1] == ("write", h.file, b"data")


def handler_decode_seek_flush_size_test(dec):
    mem, h = dec.mem, dec.h
    fh_id = dec.harness._register_file(h, h.file, "work:f")
    assert (
        dec.harness.decode(_pkt(mem, DosAction.ACTION_SEEK, arg1=fh_id, arg2=3, arg3=1))
        == 3
    )
    assert h.calls[-1] == ("seek", h.file, 3, 1)
    assert (
        dec.harness.decode(
            _pkt(mem, DosAction.ACTION_SET_FILE_SIZE, arg1=fh_id, arg2=8, arg3=-1)
        )
        == 8
    )
    assert h.calls[-1] == ("set_file_size", h.file, 8, -1)
    assert dec.harness.decode(_pkt(mem, DosAction.ACTION_FLUSH, arg1=fh_id)) == 0
    assert h.calls[-1] == ("flush", h.file)


def handler_decode_end_test(dec):
    mem, h = dec.mem, dec.h
    fh_id = dec.harness._register_file(h, h.file, "work:f")
    assert dec.harness.decode(_pkt(mem, DosAction.ACTION_END, arg1=fh_id)) == 0
    assert fh_id not in dec.harness.files


def handler_decode_screen_mode_test(dec):
    mem, h = dec.mem, dec.h
    pkt = _pkt(mem, DosAction.ACTION_SCREEN_MODE, arg1=0)
    assert dec.harness.decode(pkt) == DOSTRUE
    assert h.calls[-1] == ("set_mode", None, True)
    h.mode_result = False
    assert (
        dec.harness.decode(_pkt(mem, DosAction.ACTION_SCREEN_MODE, arg1=1)) == DOSFALSE
    )
    assert h.calls[-1] == ("set_mode", None, False)


def handler_decode_wait_char_test(dec):
    mem, h = dec.mem, dec.h
    pkt = _pkt(mem, DosAction.ACTION_WAIT_CHAR, arg1=50)
    assert dec.harness.decode(pkt) == DOSTRUE
    assert h.calls[-1] == ("wait_for_char", None, 50)


# --------------------------------------------------------------------------
# names
# --------------------------------------------------------------------------


def handler_decode_delete_rename_test(dec):
    mem, h = dec.mem, dec.h
    dec.harness.decode(
        _pkt(mem, DosAction.ACTION_DELETE_OBJECT, arg2=_bstr(mem, "x", _PATH_ADDR))
    )
    assert h.calls[-1] == ("delete_object", "x")
    dec.harness.decode(
        _pkt(
            mem,
            DosAction.ACTION_RENAME_OBJECT,
            arg2=_bstr(mem, "a", _PATH_ADDR),
            arg4=_bstr(mem, "b", _PATH2_ADDR),
        )
    )
    assert h.calls[-1] == ("rename_object", "a", "b")


def handler_decode_set_protect_comment_test(dec):
    mem, h = dec.mem, dec.h
    dec.harness.decode(
        _pkt(
            mem,
            DosAction.ACTION_SET_PROTECT,
            arg2=_bstr(mem, "x", _PATH_ADDR),
            arg3=0x1F,
        )
    )
    assert h.calls[-1] == ("set_protect", "x", 0x1F)
    dec.harness.decode(
        _pkt(
            mem,
            DosAction.ACTION_SET_COMMENT,
            arg2=_bstr(mem, "x", _PATH_ADDR),
            arg3=_bstr(mem, "hi", _PATH2_ADDR),
        )
    )
    assert h.calls[-1] == ("set_comment", "x", "hi")


def handler_decode_set_date_test(dec):
    mem, h = dec.mem, dec.h
    ds = DateStampStruct(mem, _DATE_ADDR)
    ds.ds_Days.val = 100
    ds.ds_Minute.val = 200
    ds.ds_Tick.val = 300
    dec.harness.decode(
        _pkt(
            mem,
            DosAction.ACTION_SET_DATE,
            arg2=_bstr(mem, "x", _PATH_ADDR),
            arg3=_DATE_ADDR >> 2,
        )
    )
    name, date = h.calls[-1][1], h.calls[-1][2]
    assert name == "x"
    # the AmiTime was converted to a unix timestamp
    assert date > 0


def handler_decode_create_dir_test(dec):
    mem, h = dec.mem, dec.h
    pkt = _pkt(mem, DosAction.ACTION_CREATE_DIR, arg2=_bstr(mem, "new", _PATH_ADDR))
    lock_id = dec.harness.decode(pkt)
    assert h.calls[0] == ("create_dir", "new")
    assert h.calls[1] == ("locate_object", "new", False)
    assert dec.harness.locks[lock_id] == (h, h.lock, "work:new")


# --------------------------------------------------------------------------
# errors
# --------------------------------------------------------------------------


def handler_decode_error_mapping_test(dec):
    mem, h = dec.mem, dec.h
    src = dec.harness.decode(
        _pkt(mem, DosAction.ACTION_LOCATE_OBJECT, arg2=_bstr(mem, "f", _PATH_ADDR))
    )
    h.error = ERROR_OBJECT_NOT_FOUND
    pkt = _pkt(mem, DosAction.ACTION_EXAMINE_OBJECT, arg1=src, arg2=_FIB_ADDR)
    assert dec.harness.decode(pkt) == DOSFALSE
    assert pkt.res2.val == ERROR_OBJECT_NOT_FOUND


def handler_decode_unknown_action_test(dec):
    mem = dec.mem
    pkt = _pkt(mem, DosAction.ACTION_MAKE_LINK)
    assert dec.harness.decode(pkt) == DOSFALSE
    assert pkt.res2.val == 209


def handler_decode_invalid_lock_test(dec):
    mem = dec.mem
    pkt = _pkt(mem, DosAction.ACTION_COPY_DIR, arg1=0x999)
    assert dec.harness.decode(pkt) == DOSFALSE
    assert pkt.res2.val == ERROR_INVALID_LOCK


def handler_decode_invalid_fh_test(dec):
    mem = dec.mem
    pkt = _pkt(mem, DosAction.ACTION_READ, arg1=0x999, arg2=_BUF_ADDR, arg3=1)
    assert dec.harness.decode(pkt) == DOSFALSE
    assert pkt.res2.val == ERROR_INVALID_LOCK


# --------------------------------------------------------------------------
# loopback: the HandlerContract runs through the decoder
# --------------------------------------------------------------------------


def _make_decoder_handler(name, alloc, mem, root_path):
    handler = HostFileSysHandler(name, root_path)
    harness = DecoderHarness(handler, mem)
    pkt_handler = PacketHandler(name, alloc)
    pkt_handler._dopkt = harness.decode
    return pkt_handler


@pytest.fixture
def env(tmp_path):
    mem = MockMemory(size_kib=256)
    alloc = MemoryAlloc(mem)
    root = tmp_path / "work"
    root.mkdir()

    def make(name):
        return _make_decoder_handler(name, alloc, mem, str(root))

    return SimpleNamespace(kind="decoder", h=make("work"), new_handler=make)


class TestDecoderContract(HandlerContract):
    pass
