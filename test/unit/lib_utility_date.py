import logging
from types import SimpleNamespace

from amitools.vamos.lib.UtilityLibrary import UtilityLibrary
from amitools.vamos.libstructs import ClockDataStruct
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.machine.regs import REG_A0


def _make_ctx(mem, cpu):
    return SimpleNamespace(mem=mem, cpu=cpu)


def _write_invalid_clock_data(mem, addr):
    clock_data = ClockDataStruct(mem, addr)
    clock_data.sec.val = 56
    clock_data.min.val = 34
    clock_data.hour.val = 12
    clock_data.mday.val = 31
    clock_data.month.val = 2
    clock_data.year.val = 2026
    clock_data.wday.val = 7


def lib_utility_date_invalid_clock_data_stays_quiet_test(caplog):
    mem = MockMemory()
    cpu = MockCPU()
    ctx = _make_ctx(mem, cpu)
    util = UtilityLibrary()
    date_ptr = 0x100

    _write_invalid_clock_data(mem, date_ptr)
    cpu.w_reg(REG_A0, date_ptr)
    date = ClockDataStruct(mem, date_ptr)

    caplog.set_level(logging.INFO, "utility")

    assert util.Date2Amiga(ctx, date) == 0
    assert util.CheckDate(ctx, date) == 0
    assert caplog.record_tuples == []
