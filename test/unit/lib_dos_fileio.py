"""dos.library file I/O and file-handle functions (HANDLER.md step 22k).

These tests drive the typed ``DosLibrary`` methods with a real
``FileManager``/``MemoryAlloc`` over a ``MockMemory`` and handler-less
``FileHandle``s backed by in-memory streams, so the fd argument marshalling
and the error mapping of each function are exercised without a real disk.
"""

import io
from types import SimpleNamespace

import pytest

from amitools.vamos.astructs import CSTR, LONG
from amitools.vamos.error import UnsupportedFeatureError
from amitools.vamos.handler import HandlerError
from amitools.vamos.lib.dos.Error import (
    DOSFALSE,
    DOSTRUE,
    ERROR_ACTION_NOT_KNOWN,
    ERROR_NOT_IMPLEMENTED,
    ERROR_OBJECT_NOT_FOUND,
    ERROR_SEEK_ERROR,
)
from amitools.vamos.lib.dos.FileHandle import FileHandle
from amitools.vamos.lib.dos.FileManager import FileManager
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.libstructs import DateStampStruct, ProcessStruct
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.machine.regs import REG_D1, REG_D2
from amitools.vamos.mem import MemoryAlloc

PROC_ADDR = 0x2000
BUF_ADDR = 0x400
ARG_ADDR = 0x800


def _long(mem, cpu, reg, value):
    cpu.w_reg(reg, value)
    return LONG(cpu=cpu, reg=reg, mem=mem)


def _cstr(mem, cpu, reg, addr, text):
    cpu.w_reg(reg, addr)
    mem.w_cstr(addr, text)
    return CSTR(cpu=cpu, reg=reg, mem=mem)


class _Out:
    def __init__(self):
        self.data = []

    def write(self, data):
        self.data.append(bytes(data))

    def flush(self):
        pass


class _Stream(io.BytesIO):
    """an in-memory stream with the optional console hooks FileHandle uses"""

    def __init__(self, data=b"", interactive=False):
        super().__init__(data)
        self.interactive = interactive
        self.flushed = 0
        self.seek_error = False
        self.set_mode_result = True
        self.set_mode_calls = []
        self.wait_result = False
        self.wait_calls = []

    def isatty(self):
        return self.interactive

    def flush(self):
        self.flushed += 1

    def seek(self, pos, whence=0):
        if self.seek_error:
            raise OSError("seek failed")
        return super().seek(pos, whence)

    def set_mode(self, cooked):
        self.set_mode_calls.append(cooked)
        return self.set_mode_result

    def wait_for_char(self, timeout):
        self.wait_calls.append(timeout)
        return self.wait_result


class _HandlerMgr:
    def __init__(self):
        self.calls = []
        self.error = None

    def _record(self, *args):
        self.calls.append(args)
        if self.error is not None:
            raise HandlerError(self.error)

    def delete_object(self, path, cwd=None):
        self._record("delete", path, cwd)

    def rename_object(self, old, new, cwd=None):
        self._record("rename", old, new, cwd)

    def create_dir(self, path, cwd=None):
        self._record("create_dir", path, cwd)

    def set_protect(self, path, mask, cwd=None):
        self._record("set_protect", path, mask, cwd)

    def set_date(self, path, date, cwd=None):
        self._record("set_date", path, date, cwd)


class _LockMgr:
    def __init__(self):
        self.create_lock_error = False

    def get_by_b_addr(self, b_addr):
        return None

    def create_lock(self, lock, name, exclusive):
        if self.create_lock_error:
            return None
        return SimpleNamespace(b_addr=0x1234)


class _Env:
    def __init__(self):
        self.mem = MockMemory(size_kib=256)
        self.cpu = MockCPU()
        self.alloc = MemoryAlloc(self.mem)
        self.proc = ProcessStruct(self.mem, PROC_ADDR)
        self.out = _Out()
        self.output_handle = None
        self.input_handle = None

        self.handler_mgr = _HandlerMgr()
        self.file_mgr = FileManager.__new__(FileManager)
        self.file_mgr.handler_mgr = self.handler_mgr
        self.file_mgr.alloc = self.alloc
        self.file_mgr.mem = self.mem
        self.file_mgr.files_by_b_addr = {}
        self.file_mgr.std_input = None
        self.file_mgr.std_output = None
        self.lock_mgr = _LockMgr()

        self.lib = DosLibrary()
        self.lib.file_mgr = self.file_mgr
        self.lib.lock_mgr = self.lock_mgr
        self.lib.handler_mgr = self.handler_mgr
        self.lib.alloc = self.alloc
        self.lib.mem_allocs = {}
        self.lib.io_err = 0

        self.process = SimpleNamespace(
            get_current_dir=lambda: 0,
            get_home_dir=lambda: 0,
            get_output=lambda: self.out,
            set_input=self._set_input,
            set_output=self._set_output,
            proc=self.proc,
        )
        self.ctx = SimpleNamespace(
            mem=self.mem, cpu=self.cpu, process=self.process, alloc=self.alloc
        )

    def _set_input(self, fh):
        self.input_handle = fh

    def _set_output(self, fh):
        self.output_handle = fh

    def make_file(self, data=b"", interactive=False, obj=None):
        if obj is None:
            obj = _Stream(data, interactive)
        fh = FileHandle(obj, "SYS:f", "f", need_close=False)
        self.file_mgr._register_file(fh)
        return fh


@pytest.fixture
def env():
    return _Env()


# ----- Seek -----


def lib_dos_fileio_seek_modes_test(env):
    fh = env.make_file(b"0123456789")
    # OFFSET_BEGINNING (-1): returns the old position, moves to 4
    assert env.lib.Seek(env.ctx, fh.b_addr, 4, 0xFFFFFFFF) == 0
    # OFFSET_CURRENT (0)
    assert env.lib.Seek(env.ctx, fh.b_addr, 2, 0) == 4
    # OFFSET_END (1) with a negative offset (-2)
    assert env.lib.Seek(env.ctx, fh.b_addr, 0xFFFFFFFE, 1) == 6
    assert env.lib.io_err == 0


def lib_dos_fileio_seek_error_test(env):
    stream = _Stream(b"0123456789")
    fh = env.make_file(obj=stream)
    stream.seek_error = True
    assert env.lib.Seek(env.ctx, fh.b_addr, 0, 0xFFFFFFFF) == -1
    assert env.lib.io_err == ERROR_SEEK_ERROR


def lib_dos_fileio_seek_bad_mode_test(env):
    fh = env.make_file(b"x")
    with pytest.raises(UnsupportedFeatureError):
        env.lib.Seek(env.ctx, fh.b_addr, 0, 7)


# ----- FGetC / FPutC / UnGetC -----


def lib_dos_fileio_fgetc_test(env):
    fh = env.make_file(b"AB")
    assert env.lib.FGetC(env.ctx, fh.b_addr) == ord("A")
    assert env.lib.io_err == 0
    assert env.lib.FGetC(env.ctx, fh.b_addr) == ord("B")
    # EOF maps to -1
    assert env.lib.FGetC(env.ctx, fh.b_addr) == -1


def lib_dos_fileio_fputc_test(env):
    stream = _Stream()
    fh = env.make_file(obj=stream)
    assert env.lib.FPutC(env.ctx, fh.b_addr, ord("Z")) == ord("Z")
    assert stream.getvalue() == b"Z"


def lib_dos_fileio_ungetc_test(env):
    fh = env.make_file(b"AB")
    assert env.lib.FGetC(env.ctx, fh.b_addr) == ord("A")
    # push back a different char, it is read next
    assert env.lib.UnGetC(env.ctx, fh.b_addr, ord("X")) == ord("X")
    assert env.lib.FGetC(env.ctx, fh.b_addr) == ord("X")
    assert env.lib.FGetC(env.ctx, fh.b_addr) == ord("B")


# ----- FRead / FWrite -----


def lib_dos_fileio_fwrite_test(env):
    stream = _Stream()
    fh = env.make_file(obj=stream)
    env.mem.w_cstr(BUF_ADDR, "abcd")
    assert env.lib.FWrite(env.ctx, fh.b_addr, BUF_ADDR, 2, 2) == 2
    assert stream.getvalue() == b"abcd"


def lib_dos_fileio_fread_test(env):
    fh = env.make_file(b"abcd")
    assert env.lib.FRead(env.ctx, fh.b_addr, BUF_ADDR, 2, 2) == 2
    assert env.mem.r_cstr(BUF_ADDR) == "abcd"


def lib_dos_fileio_fputs_test(env):
    stream = _Stream()
    fh = env.make_file(obj=stream)
    env.mem.w_cstr(BUF_ADDR, "line")
    assert env.lib.FPuts(env.ctx, fh.b_addr, BUF_ADDR) == 0
    assert stream.getvalue() == b"line"


# ----- FGets -----


def lib_dos_fileio_fgets_test(env):
    fh = env.make_file(b"hello\nworld")
    assert env.lib.FGets(env.ctx, fh.b_addr, BUF_ADDR, 16) == BUF_ADDR
    assert env.mem.r_cstr(BUF_ADDR) == "hello\n"
    assert env.lib.FGets(env.ctx, fh.b_addr, BUF_ADDR, 16) == BUF_ADDR
    assert env.mem.r_cstr(BUF_ADDR) == "world"
    # at EOF the buffer is cleared and NULL returned
    assert env.lib.FGets(env.ctx, fh.b_addr, BUF_ADDR, 16) == 0


def lib_dos_fileio_fgets_faked_eof_test(env):
    fh = env.make_file(b"hello")
    # the 'endcli' hack: fh_End == 0 fakes EOF
    fh.struct.fh_End.val = 0
    assert env.lib.FGets(env.ctx, fh.b_addr, BUF_ADDR, 16) == 0


# ----- Flush / WriteChars / PutStr -----


def lib_dos_fileio_flush_test(env):
    stream = _Stream()
    fh = env.make_file(obj=stream)
    assert env.lib.Flush(env.ctx, fh.b_addr) == -1
    assert stream.flushed == 1


def lib_dos_fileio_write_chars_test(env):
    env.mem.w_cstr(BUF_ADDR, "hi!")
    assert env.lib.WriteChars(env.ctx, BUF_ADDR, 3) == 3
    assert env.out.data == [b"hi!"]


def lib_dos_fileio_put_str_test(env):
    env.mem.w_cstr(BUF_ADDR, "hello")
    assert env.lib.PutStr(env.ctx, BUF_ADDR) == 0
    assert env.out.data == [b"hello"]


# ----- VPrintf / VFPrintf / VFWritef -----


def lib_dos_fileio_vprintf_test(env):
    env.mem.w32(ARG_ADDR, 42)
    fmt = _cstr(env.mem, env.cpu, REG_D1, BUF_ADDR, "%ld")
    assert env.lib.VPrintf(env.ctx, fmt, ARG_ADDR) == len("42")
    assert env.out.data == [b"42"]


def lib_dos_fileio_vfprintf_test(env):
    stream = _Stream()
    fh = env.make_file(obj=stream)
    env.mem.w32(ARG_ADDR, 7)
    fmt = _cstr(env.mem, env.cpu, REG_D2, BUF_ADDR, "%ld")
    assert env.lib.VFPrintf(env.ctx, fh.b_addr, fmt, ARG_ADDR) == len("7")
    assert stream.getvalue() == b"7"


def lib_dos_fileio_vfwritef_test(env):
    stream = _Stream()
    fh = env.make_file(obj=stream)
    env.mem.w_cstr(0x600, "world")
    env.mem.w32(ARG_ADDR, 0x600)
    fmt = _cstr(env.mem, env.cpu, REG_D2, BUF_ADDR, "%s")
    assert env.lib.VFWritef(env.ctx, fh.b_addr, fmt, ARG_ADDR) == len("world")
    assert stream.getvalue() == b"world"


# ----- SelectInput / SelectOutput -----


def lib_dos_fileio_select_input_test(env):
    env.proc.pr_CIS.aptr = 0x100
    fh = env.make_file(b"x")
    assert env.lib.SelectInput(env.ctx, fh.b_addr) == 0x100 >> 2
    assert env.input_handle is fh


def lib_dos_fileio_select_output_test(env):
    env.proc.pr_COS.aptr = 0x200
    fh = env.make_file(b"x")
    assert env.lib.SelectOutput(env.ctx, fh.b_addr) == 0x200 >> 2
    assert env.output_handle is fh


# ----- IsInteractive / SetMode / WaitForChar -----


def lib_dos_fileio_is_interactive_test(env):
    assert env.lib.IsInteractive(env.ctx, 0) == DOSFALSE
    plain = env.make_file(b"x")
    assert env.lib.IsInteractive(env.ctx, plain.b_addr) == DOSFALSE
    console = env.make_file(b"x", interactive=True)
    assert env.lib.IsInteractive(env.ctx, console.b_addr) == DOSTRUE


def lib_dos_fileio_set_mode_test(env):
    console = env.make_file(b"x", interactive=True)
    assert (
        env.lib.SetMode(env.ctx, console.b_addr, _long(env.mem, env.cpu, REG_D2, 0))
        == DOSTRUE
    )
    assert console.obj.set_mode_calls == [True]
    assert env.lib.io_err == 0
    # medium mode is ignored
    assert (
        env.lib.SetMode(env.ctx, console.b_addr, _long(env.mem, env.cpu, REG_D2, 2))
        == DOSFALSE
    )
    # an unknown mode is an action-not-known error
    assert (
        env.lib.SetMode(env.ctx, console.b_addr, _long(env.mem, env.cpu, REG_D2, 9))
        == DOSFALSE
    )
    assert env.lib.io_err == ERROR_ACTION_NOT_KNOWN


def lib_dos_fileio_set_mode_non_interactive_test(env):
    plain = env.make_file(b"x")
    assert (
        env.lib.SetMode(env.ctx, plain.b_addr, _long(env.mem, env.cpu, REG_D2, 0))
        == DOSFALSE
    )
    assert env.lib.io_err == ERROR_ACTION_NOT_KNOWN


def lib_dos_fileio_wait_for_char_test(env):
    console = env.make_file(b"x", interactive=True)
    console.obj.wait_result = True
    assert (
        env.lib.WaitForChar(
            env.ctx, console.b_addr, _long(env.mem, env.cpu, REG_D2, 1_000_000)
        )
        == DOSTRUE
    )
    assert env.lib.io_err == 1
    # no char available
    console.obj.wait_result = False
    assert (
        env.lib.WaitForChar(
            env.ctx, console.b_addr, _long(env.mem, env.cpu, REG_D2, 1_000_000)
        )
        == DOSFALSE
    )
    assert env.lib.io_err == 0


def lib_dos_fileio_wait_for_char_unsupported_test(env):
    console = env.make_file(b"x", interactive=True)
    console.obj.wait_result = None
    assert (
        env.lib.WaitForChar(
            env.ctx, console.b_addr, _long(env.mem, env.cpu, REG_D2, 1_000_000)
        )
        == DOSFALSE
    )
    assert env.lib.io_err == ERROR_NOT_IMPLEMENTED
    # a non-interactive handle cannot wait
    plain = env.make_file(b"x")
    assert (
        env.lib.WaitForChar(
            env.ctx, plain.b_addr, _long(env.mem, env.cpu, REG_D2, 1_000_000)
        )
        == DOSFALSE
    )
    assert env.lib.io_err == ERROR_ACTION_NOT_KNOWN


# ----- DeleteFile / Rename / CreateDir / SetComment / SetProtection -----


def lib_dos_fileio_delete_file_test(env):
    name = _cstr(env.mem, env.cpu, REG_D1, BUF_ADDR, "work:x")
    assert env.lib.DeleteFile(env.ctx, name) == DOSTRUE
    assert env.lib.io_err == 0
    assert env.handler_mgr.calls == [("delete", "work:x", None)]


def lib_dos_fileio_delete_file_error_test(env):
    env.handler_mgr.error = ERROR_OBJECT_NOT_FOUND
    name = _cstr(env.mem, env.cpu, REG_D1, BUF_ADDR, "work:missing")
    assert env.lib.DeleteFile(env.ctx, name) == DOSFALSE
    assert env.lib.io_err == ERROR_OBJECT_NOT_FOUND


def lib_dos_fileio_rename_test(env):
    old = _cstr(env.mem, env.cpu, REG_D1, BUF_ADDR, "work:a")
    new = _cstr(env.mem, env.cpu, REG_D2, 0x480, "work:b")
    assert env.lib.Rename(env.ctx, old, new) == DOSTRUE
    assert env.handler_mgr.calls == [("rename", "work:a", "work:b", None)]


def lib_dos_fileio_create_dir_test(env):
    name = _cstr(env.mem, env.cpu, REG_D1, BUF_ADDR, "work:new")
    assert env.lib.CreateDir(env.ctx, name) == 0x1234
    assert env.lib.io_err == 0
    assert env.handler_mgr.calls == [("create_dir", "work:new", None)]


def lib_dos_fileio_create_dir_error_test(env):
    env.handler_mgr.error = ERROR_OBJECT_NOT_FOUND
    name = _cstr(env.mem, env.cpu, REG_D1, BUF_ADDR, "work:bad")
    assert env.lib.CreateDir(env.ctx, name) == 0
    assert env.lib.io_err == ERROR_OBJECT_NOT_FOUND


def lib_dos_fileio_create_dir_no_lock_test(env):
    env.lock_mgr.create_lock_error = True
    name = _cstr(env.mem, env.cpu, REG_D1, BUF_ADDR, "work:new")
    assert env.lib.CreateDir(env.ctx, name) == 0
    assert env.lib.io_err == ERROR_OBJECT_NOT_FOUND


def lib_dos_fileio_set_comment_test(env):
    name = _cstr(env.mem, env.cpu, REG_D1, BUF_ADDR, "work:f")
    comment = _cstr(env.mem, env.cpu, REG_D2, 0x480, "a comment")
    assert env.lib.SetComment(env.ctx, name, comment) == DOSTRUE


def lib_dos_fileio_set_protection_test(env):
    name = _cstr(env.mem, env.cpu, REG_D1, BUF_ADDR, "work:f")
    assert env.lib.SetProtection(env.ctx, name, 0) == DOSTRUE
    assert env.handler_mgr.calls == [("set_protect", "work:f", 0, None)]


def lib_dos_fileio_set_file_date_test(env):
    name = _cstr(env.mem, env.cpu, REG_D1, BUF_ADDR, "work:f")
    ds = DateStampStruct(env.mem, 0x600)
    ds.ds_Days.val = 100
    ds.ds_Minute.val = 10
    ds.ds_Tick.val = 20
    assert env.lib.SetFileDate(env.ctx, name, 0x600) == DOSTRUE
    kind, path, _seconds, cwd = env.handler_mgr.calls[0]
    assert (kind, path, cwd) == ("set_date", "work:f", None)


def lib_dos_fileio_set_file_date_error_test(env):
    env.handler_mgr.error = ERROR_NOT_IMPLEMENTED
    name = _cstr(env.mem, env.cpu, REG_D1, BUF_ADDR, "work:f")
    assert env.lib.SetFileDate(env.ctx, name, 0x600) == DOSFALSE
    assert env.lib.io_err == ERROR_NOT_IMPLEMENTED
