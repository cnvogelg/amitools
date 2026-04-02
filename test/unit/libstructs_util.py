import datetime

import pytest
from amitools.vamos.astructs import AccessStruct
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
    access = AccessStruct(mem, ClockDataStruct, 0x100)
    write_clock_data(dt, mem, 0x100)
    assert access.r_s("sec") == dt.second
    assert access.r_s("min") == dt.minute
    assert access.r_s("hour") == dt.hour
    assert access.r_s("mday") == dt.day
    assert access.r_s("month") == dt.month
    assert access.r_s("year") == dt.year
    assert access.r_s("wday") == wday


def libstructs_util_clockdata_read_ignores_wday_test():
    mem = MockMemory()
    access = AccessStruct(mem, ClockDataStruct, 0x100)
    dt = datetime.datetime(2026, 4, 6, 12, 34, 56)
    write_clock_data(dt, mem, 0x100)
    access.w_s("wday", 7)
    assert read_clock_data(mem, 0x100) == dt
