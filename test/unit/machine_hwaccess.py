import pytest
import logging
from amitools.vamos.machine import Machine, HWAccess, HWAccessError


def machine_hwaccess_create_test():
    machine = Machine()
    # disabled
    assert HWAccess.from_mode_str(machine, "disable") is None
    # valid modes
    for mode in ("emu", "abort", "ignore"):
        assert HWAccess.from_mode_str(machine, mode)
    # unknown mode
    with pytest.raises(ValueError):
        HWAccess.from_mode_str(machine, "bla")


def machine_hwaccess_ignore_test(caplog):
    caplog.set_level(logging.WARN, "hw")
    machine = Machine()
    mem = machine.get_mem()
    hw = HWAccess.from_mode_str(machine, "ignore")
    assert mem.cpu_r8(0xBF0000) == 0
    mem.cpu_w8(0xBF0000, 42)
    assert mem.cpu_r16(0xDF0000) == 0
    mem.cpu_w16(0xDF0000, 0xDEAD)
    assert caplog.record_tuples == [
        ("hw", logging.WARN, "CIA read byte @bf0000"),
        ("hw", logging.WARN, "CIA write byte @bf0000: 2a"),
        ("hw", logging.WARN, "Custom Chip read word @df0000"),
        ("hw", logging.WARN, "Custom Chip write word @df0000: dead"),
    ]


def machine_hwaccess_abort_test(caplog):
    caplog.set_level(logging.WARN, "hw")
    machine = Machine()
    mem = machine.get_mem()
    hw = HWAccess.from_mode_str(machine, "abort")
    with pytest.raises(HWAccessError):
        mem.cpu_r8(0xBF0000)
    with pytest.raises(HWAccessError):
        mem.cpu_w8(0xBF0000, 42)
    with pytest.raises(HWAccessError):
        mem.cpu_r16(0xDF0000)
    with pytest.raises(HWAccessError):
        mem.cpu_w16(0xDF0000, 0xDEAD)
    assert caplog.record_tuples == [
        ("hw", logging.WARN, "CIA read byte @bf0000"),
        ("hw", logging.WARN, "CIA write byte @bf0000: 2a"),
        ("hw", logging.WARN, "Custom Chip read word @df0000"),
        ("hw", logging.WARN, "Custom Chip write word @df0000: dead"),
    ]
