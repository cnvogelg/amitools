import time
from types import SimpleNamespace

import pytest

from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.libstructs import DateTimeStruct
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.machine.regs import REG_D1


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

    assert DosLibrary().DateToStr(ctx) != 0
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
        "amitools.vamos.lib.DosLibrary.time.time",
        lambda: amiga_epoch + 100 * 24 * 60 * 60,
    )

    assert _date_to_str(FORMAT_DOS, flags=DTF_SUBST, day=100)[1] == "Today"
    assert _date_to_str(FORMAT_DOS, flags=DTF_SUBST, day=101)[1] == "Tomorrow"
    assert _date_to_str(FORMAT_DOS, flags=DTF_SUBST, day=99)[1] == "Yesterday"
    assert _date_to_str(FORMAT_DOS, flags=DTF_SUBST, day=102)[1] == "Future"


def lib_dos_date_to_str_without_substitution_test(monkeypatch):
    amiga_epoch = 252460800
    monkeypatch.setattr(
        "amitools.vamos.lib.DosLibrary.time.time",
        lambda: amiga_epoch + 100 * 24 * 60 * 60,
    )
    assert _date_to_str(FORMAT_DOS, day=100)[1] == "11-Apr-78"
