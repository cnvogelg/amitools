import time
from types import SimpleNamespace

import pytest

from amitools.vamos.astructs import LONG
from amitools.vamos.lib.dos import Date as DateModule
from amitools.vamos.lib.dos.AmiTime import sys_to_ami_time
from amitools.vamos.lib.dos.Error import (
    DOSFALSE,
    DOSTRUE,
    ERROR_OBJECT_NOT_FOUND,
)
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.libstructs import DateStampStruct, DateTimeStruct
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.machine.regs import REG_D1, REG_D2
from amitools.vamos.mem import MemoryAlloc

FORMAT_DOS = 0
FORMAT_INT = 1
FORMAT_USA = 2
FORMAT_CDN = 3
FORMAT_DEF = 4
DTF_SUBST = 1


def _date_to_str(date_format, flags=0, day=336):
    mem = MockMemory()
    cpu = MockCPU()
    ctx = SimpleNamespace(mem=mem, cpu=cpu)
    date_ptr = 0x100
    date = DateTimeStruct(mem, date_ptr)
    date.dat_Stamp.ds_Days.val = day
    date.dat_Stamp.ds_Minute.val = 12 * 60 + 34
    date.dat_Stamp.ds_Tick.val = 56 * 50
    date.dat_Format.val = date_format
    date.dat_Flags.val = flags
    date.dat_StrDay.aptr = 0x200
    date.dat_StrDate.aptr = 0x220
    date.dat_StrTime.aptr = 0x240
    cpu.w_reg(REG_D1, date_ptr)

    assert DosLibrary().DateToStr(ctx, date_ptr) != 0
    return mem.r_cstr(0x200), mem.r_cstr(0x220), mem.r_cstr(0x240)


@pytest.mark.parametrize(
    "date_format, expected",
    [
        (FORMAT_DOS, "03-Dec-78"),
        (FORMAT_INT, "78-12-03"),
        (FORMAT_USA, "12-03-78"),
        (FORMAT_CDN, "03-12-78"),
        (99, "03-Dec-78"),
    ],
)
def lib_dos_date_to_str_format_test(date_format, expected):
    assert _date_to_str(date_format)[1] == expected


def lib_dos_date_to_str_default_format_test():
    day_seconds = (336 + 2922) * 24 * 60 * 60
    expected = time.strftime("%x", time.gmtime(day_seconds))
    assert _date_to_str(FORMAT_DEF)[1] == expected


def lib_dos_date_to_str_substitution_flags_test(monkeypatch):
    amiga_epoch = 252460800
    monkeypatch.setattr(
        "amitools.vamos.lib.dos.Date.time.time",
        lambda: amiga_epoch + 100 * 24 * 60 * 60,
    )

    assert _date_to_str(FORMAT_DOS, flags=DTF_SUBST, day=100)[1] == "Today"
    assert _date_to_str(FORMAT_DOS, flags=DTF_SUBST, day=101)[1] == "Tomorrow"
    assert _date_to_str(FORMAT_DOS, flags=DTF_SUBST, day=99)[1] == "Yesterday"
    assert _date_to_str(FORMAT_DOS, flags=DTF_SUBST, day=102)[1] == "Future"


def lib_dos_date_to_str_without_substitution_test(monkeypatch):
    amiga_epoch = 252460800
    monkeypatch.setattr(
        "amitools.vamos.lib.dos.Date.time.time",
        lambda: amiga_epoch + 100 * 24 * 60 * 60,
    )
    assert _date_to_str(FORMAT_DOS, day=100)[1] == "11-Apr-78"


# ----- StrToDate / CompareDates (Step 18) -----

DT_PTR = 0x100
DATE_PTR = 0x200
TIME_PTR = 0x240


def _str_to_date(
    date_format,
    date_str=None,
    time_str=None,
    flags=0,
    days=1,
    minute=2,
    tick=3,
):
    mem = MockMemory()
    cpu = MockCPU()
    ctx = SimpleNamespace(mem=mem, cpu=cpu)
    dt = DateTimeStruct(mem, DT_PTR)
    dt.dat_Stamp.ds_Days.val = days
    dt.dat_Stamp.ds_Minute.val = minute
    dt.dat_Stamp.ds_Tick.val = tick
    dt.dat_Format.val = date_format
    dt.dat_Flags.val = flags
    if date_str is None:
        dt.dat_StrDate.aptr = 0
    else:
        mem.w_cstr(DATE_PTR, date_str)
        dt.dat_StrDate.aptr = DATE_PTR
    if time_str is None:
        dt.dat_StrTime.aptr = 0
    else:
        mem.w_cstr(TIME_PTR, time_str)
        dt.dat_StrTime.aptr = TIME_PTR
    cpu.w_reg(REG_D1, DT_PTR)

    res = DosLibrary().StrToDate(ctx, LONG(cpu=cpu, reg=REG_D1, mem=mem))
    return res, dt


@pytest.mark.parametrize(
    "date_format, date_str",
    [
        (FORMAT_DOS, "03-Dec-78"),
        (FORMAT_INT, "78-12-03"),
        (FORMAT_USA, "12-03-78"),
        (FORMAT_CDN, "03-12-78"),
    ],
)
def lib_dos_str_to_date_format_test(date_format, date_str):
    res, dt = _str_to_date(date_format, date_str)
    assert res == DOSTRUE
    # 1978-12-03 is 336 days after the AmigaDOS epoch
    assert dt.dat_Stamp.ds_Days.val == 336


def lib_dos_str_to_date_time_test():
    res, dt = _str_to_date(FORMAT_DOS, "03-Dec-78", "12:34:56")
    assert res == DOSTRUE
    assert dt.dat_Stamp.ds_Days.val == 336
    assert dt.dat_Stamp.ds_Minute.val == 12 * 60 + 34
    assert dt.dat_Stamp.ds_Tick.val == 56 * 50


def lib_dos_str_to_date_y2k_test():
    res, dt = _str_to_date(FORMAT_DOS, "01-Jan-00")
    assert res == DOSTRUE
    # 2000-01-01
    assert dt.dat_Stamp.ds_Days.val == 8035


def lib_dos_str_to_date_relative_test(monkeypatch):
    fixed_time = 252460800 + 100 * 24 * 60 * 60
    monkeypatch.setattr("amitools.vamos.lib.dos.Date.time.time", lambda: fixed_time)
    today = sys_to_ami_time(fixed_time).tday

    assert _str_to_date(FORMAT_DOS, "Today")[1].dat_Stamp.ds_Days.val == today
    assert _str_to_date(FORMAT_DOS, "Tomorrow")[1].dat_Stamp.ds_Days.val == today + 1
    assert _str_to_date(FORMAT_DOS, "Yesterday")[1].dat_Stamp.ds_Days.val == today - 1

    # a weekday always refers to the past occurrence
    weekday = (today + DateModule._EPOCH_WEEKDAY) % 7
    target = (weekday + 1) % 7
    name = next(k for k, v in DateModule._WEEKDAYS.items() if v == target)
    delta = (target - weekday) % 7
    if delta:
        delta -= 7
    days = _str_to_date(FORMAT_DOS, name)[1].dat_Stamp.ds_Days.val
    assert days == today + delta
    assert today - 7 < days <= today


def lib_dos_str_to_date_invalid_test():
    res, dt = _str_to_date(FORMAT_DOS, "99-Foo-78", days=42)
    assert res == DOSFALSE
    # a failed date conversion leaves the stamp untouched
    assert dt.dat_Stamp.ds_Days.val == 42

    res, dt = _str_to_date(FORMAT_DOS, "03-Dec-78", "99:99")
    assert res == DOSFALSE
    assert dt.dat_Stamp.ds_Days.val == 1


def lib_dos_str_to_date_null_strings_test():
    res, dt = _str_to_date(FORMAT_DOS, None, None, days=11, minute=22, tick=33)
    assert res == DOSTRUE
    assert dt.dat_Stamp.ds_Days.val == 11
    assert dt.dat_Stamp.ds_Minute.val == 22
    assert dt.dat_Stamp.ds_Tick.val == 33


def lib_dos_compare_dates_test():
    mem = MockMemory()
    cpu = MockCPU()
    ctx = SimpleNamespace(mem=mem, cpu=cpu)
    date1 = DateStampStruct(mem, 0x100)
    date2 = DateStampStruct(mem, 0x120)
    date1.ds_Days.val = 100
    date1.ds_Minute.val = 10
    date1.ds_Tick.val = 1
    date2.ds_Days.val = 100
    date2.ds_Minute.val = 10
    date2.ds_Tick.val = 2
    cpu.w_reg(REG_D1, 0x100)
    cpu.w_reg(REG_D2, 0x120)
    lib = DosLibrary()

    def compare():
        return lib.CompareDates(
            ctx, LONG(cpu=cpu, reg=REG_D1, mem=mem), LONG(cpu=cpu, reg=REG_D2, mem=mem)
        )

    # date2 is later -> positive
    assert compare() > 0
    date2.ds_Tick.val = 1
    assert compare() == 0
    date2.ds_Tick.val = 0
    # date1 is later -> negative
    assert compare() < 0


# ----- DateStamp (Step 22i) -----


def lib_dos_date_stamp_test(monkeypatch):
    fixed_time = 252460800
    monkeypatch.setattr("amitools.vamos.lib.dos.Date.time.time", lambda: fixed_time)
    mem = MockMemory()
    lib = DosLibrary()
    ctx = SimpleNamespace(mem=mem, cpu=MockCPU())

    ds_ptr = 0x400
    assert lib.DateStamp(ctx, ds_ptr) == ds_ptr
    ds = DateStampStruct(mem, ds_ptr)
    at = sys_to_ami_time(fixed_time)
    assert ds.ds_Days.val == at.tday
    assert ds.ds_Minute.val == at.tmin
    assert ds.ds_Tick.val == at.tick


# ----- IoErr / Fault / PrintFault (Step 22i) -----


class _Out:
    def __init__(self):
        self.data = []

    def write(self, data):
        self.data.append(bytes(data))


def lib_dos_set_io_err_test():
    lib = DosLibrary()
    lib.io_err = 5
    ctx = SimpleNamespace(mem=MockMemory(), cpu=MockCPU(), process=None)
    assert lib.SetIoErr(ctx, 7) == 5
    assert lib.io_err == 7


def lib_dos_fault_test():
    mem = MockMemory()
    lib = DosLibrary()
    lib.io_err = 0
    ctx = SimpleNamespace(mem=mem, cpu=MockCPU())

    mem.w_cstr(0x400, "HEADER")
    assert lib.Fault(ctx, ERROR_OBJECT_NOT_FOUND, 0x400, 0x500, 64) == DOSTRUE
    assert mem.r_cstr(0x500) == "HEADER: ERROR_OBJECT_NOT_FOUND"

    # without a header only the error string is written
    assert lib.Fault(ctx, ERROR_OBJECT_NOT_FOUND, 0, 0x500, 64) == DOSTRUE
    assert mem.r_cstr(0x500) == "ERROR_OBJECT_NOT_FOUND"

    # an unsigned 32-bit error code is decoded to its signed index
    assert lib.Fault(ctx, 0x100000000 - 160, 0, 0x500, 64) == DOSTRUE
    assert mem.r_cstr(0x500) == "%TH USE COUNT\n\n"


def lib_dos_print_fault_test():
    mem = MockMemory()
    out = _Out()
    lib = DosLibrary()
    ctx = SimpleNamespace(
        mem=mem, cpu=MockCPU(), process=SimpleNamespace(get_output=lambda: out)
    )

    mem.w_cstr(0x400, "HEADER")
    assert lib.PrintFault(ctx, ERROR_OBJECT_NOT_FOUND, 0x400) == DOSTRUE
    assert lib.io_err == ERROR_OBJECT_NOT_FOUND
    assert out.data == [b"HEADER: ERROR_OBJECT_NOT_FOUND\n"]

    # without a header
    assert lib.PrintFault(ctx, ERROR_OBJECT_NOT_FOUND, 0) == DOSTRUE
    assert out.data[-1] == b"ERROR_OBJECT_NOT_FOUND\n"


# ----- DosGetString (Step 22i) -----


def lib_dos_get_string_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    lib = DosLibrary()
    lib.alloc = alloc
    lib.mem_allocs = {}
    lib.errstrings = {}
    ctx = SimpleNamespace(mem=mem, cpu=MockCPU())

    addr = lib.DosGetString(ctx, ERROR_OBJECT_NOT_FOUND)
    assert addr != 0
    assert mem.r_cstr(addr) == "ERROR_OBJECT_NOT_FOUND"
    # the string is cached and returned again
    assert lib.DosGetString(ctx, ERROR_OBJECT_NOT_FOUND) == addr
    # an unknown error has no string
    assert lib.DosGetString(ctx, 12345) == 0


# ----- FilePart / PathPart / AddPart (Step 22i) -----


def lib_dos_file_part_test():
    mem = MockMemory()
    lib = DosLibrary()
    ctx = SimpleNamespace(mem=mem, cpu=MockCPU())

    mem.w_cstr(0x400, "work:dir/file.txt")
    assert lib.FilePart(ctx, 0x400) == 0x400 + len("work:dir/")
    # a path without a separator points at the whole string
    mem.w_cstr(0x500, "file.txt")
    assert lib.FilePart(ctx, 0x500) == 0x500


def lib_dos_path_part_test():
    mem = MockMemory()
    lib = DosLibrary()
    ctx = SimpleNamespace(mem=mem, cpu=MockCPU())

    mem.w_cstr(0x400, "work:dir/file.txt")
    assert lib.PathPart(ctx, 0x400) == 0x400 + len("work:dir")
    mem.w_cstr(0x500, "file.txt")
    assert lib.PathPart(ctx, 0x500) == 0x500


def lib_dos_add_part_test():
    mem = MockMemory()
    lib = DosLibrary()
    ctx = SimpleNamespace(mem=mem, cpu=MockCPU())

    mem.w_cstr(0x400, "work:")
    mem.w_cstr(0x480, "file.txt")
    assert lib.AddPart(ctx, 0x400, 0x480, 64) == DOSTRUE
    assert mem.r_cstr(0x400) == "work:file.txt"

    # a filename with its own device replaces the directory name
    mem.w_cstr(0x400, "work:")
    mem.w_cstr(0x480, "ram:x")
    assert lib.AddPart(ctx, 0x400, 0x480, 64) == DOSTRUE
    assert mem.r_cstr(0x400) == "ram:x"
