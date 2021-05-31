import pytest
from amitools.vamos.libstructs import ClockDataStruct
from amitools.vamos.machine import MockMemory


def libstructs_util_clockdata_test():
    mem = MockMemory()
    clock_data = ClockDataStruct(mem, 0x100)
    assert clock_data.get_byte_size() == 14
