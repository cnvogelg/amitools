import logging
from types import SimpleNamespace

import pytest

from amitools.vamos.machine import Machine, HWAccess, HWAccessError


@pytest.fixture
def machine():
    instance = Machine()
    yield instance
    instance.cleanup()


@pytest.mark.parametrize("mode", ["emu", "ignore", "abort"])
def machine_hwaccess_vhposr_mode_test(machine, monkeypatch, mode):
    clock_calls = []

    def clock():
        clock_calls.append(True)
        return 0x12345600

    monkeypatch.setattr(
        "amitools.vamos.machine.hwaccess.time", SimpleNamespace(time_ns=clock)
    )
    HWAccess.from_mode_str(machine, mode)
    mem = machine.get_mem()
    if mode == "abort":
        with pytest.raises(HWAccessError) as error:
            mem.cpu_r16(0xDFF006)
        assert error.value.addr == 0xDFF006
        assert error.value.mode == "R"
        assert error.value.width == 1
    else:
        assert mem.cpu_r16(0xDFF006) == (0x3456 if mode == "emu" else 0)
    assert len(clock_calls) == (1 if mode == "emu" else 0)


@pytest.mark.parametrize(
    "timestamp, expected",
    [(0, 0), (0x12345600, 0x3456), (0xFFFFFF00, 0xFFFF), (0x100000000, 0)],
)
def machine_hwaccess_vhposr_word_test(machine, monkeypatch, timestamp, expected):
    monkeypatch.setattr(
        "amitools.vamos.machine.hwaccess.time",
        SimpleNamespace(time_ns=lambda: timestamp),
    )
    hw = HWAccess.from_mode_str(machine, "emu")
    # Check the callback itself as well as the backend's word-read interface.
    assert hw.cc_r16(0xDFF006) == expected
    assert machine.get_mem().cpu_r16(0xDFF006) == expected


def machine_hwaccess_vhposr_progress_test(machine, monkeypatch):
    timestamps = iter([0xFFFF00, 0x1000000])
    monkeypatch.setattr(
        "amitools.vamos.machine.hwaccess.time",
        SimpleNamespace(time_ns=lambda: next(timestamps)),
    )
    HWAccess.from_mode_str(machine, "emu")
    mem = machine.get_mem()
    assert mem.cpu_r16(0xDFF006) == 0xFFFF
    assert mem.cpu_r16(0xDFF006) == 0


def machine_hwaccess_vhposr_log_test(machine, monkeypatch, caplog):
    caplog.set_level(logging.INFO, "hw")
    monkeypatch.setattr(
        "amitools.vamos.machine.hwaccess.time",
        SimpleNamespace(time_ns=lambda: 0x3400),
    )
    HWAccess.from_mode_str(machine, "emu")
    assert machine.get_mem().cpu_r16(0xDFF006) == 0x34
    assert caplog.record_tuples == [
        ("hw", logging.INFO, "Custom Chip read vhposr @dff006 -> 0034")
    ]


@pytest.mark.parametrize("mode", ["emu", "ignore", "abort"])
def machine_hwaccess_vhposr_write_test(machine, mode):
    HWAccess.from_mode_str(machine, mode)
    mem = machine.get_mem()
    if mode == "abort":
        with pytest.raises(HWAccessError):
            mem.cpu_w16(0xDFF006, 0x1234)
    else:
        mem.cpu_w16(0xDFF006, 0x1234)
