import datetime

import pytest
from amitools.vamos.lib.util.AmiDate import read_clock_data, write_clock_data
from amitools.vamos.libstructs import ClockDataStruct
from amitools.vamos.machine.mock import MockMemory


def libstructs_util_clockdata_test():
    mem = MockMemory()
    clock_data = ClockDataStruct(mem, 0x100)
    assert clock_data.get_byte_size() == 14


@pytest.mark.parametrize(
    ("dt", "wday"),
    (
        (datetime.datetime(2026, 4, 5, 12, 34, 56), 0),
        (datetime.datetime(2026, 4, 6, 12, 34, 56), 1),
    ),
)
def libstructs_util_clockdata_write_wday_test(dt, wday):
    mem = MockMemory()
    access = ClockDataStruct(mem, 0x100)
    write_clock_data(dt, mem, 0x100)
    assert access.sec.val == dt.second
    assert access.min.val == dt.minute
    assert access.hour.val == dt.hour
    assert access.mday.val == dt.day
    assert access.month.val == dt.month
    assert access.year.val == dt.year
    assert access.wday.val == wday


def libstructs_util_clockdata_read_ignores_wday_test():
    mem = MockMemory()
    access = ClockDataStruct(mem, 0x100)
    dt = datetime.datetime(2026, 4, 6, 12, 34, 56)
    write_clock_data(dt, mem, 0x100)
    access.wday.val = 7
    assert read_clock_data(mem, 0x100) == dt
