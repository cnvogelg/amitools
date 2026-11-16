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


@pytest.mark.parametrize("mode", ["emu", "ignore", "abort"])
@pytest.mark.parametrize(
    "bits,address",
    [
        (8, 0xDE0002),
        (8, 0xDE1000),
        (8, 0xDE0043),
        (16, 0xDCF004),
        (16, 0xDAF00A),
        (32, 0xDD0020),
        (8, 0xDC0FF3),
        (16, 0xDB0000),
    ],
)
def machine_hwaccess_absent_probe_test(mode, bits, address):
    machine = Machine()
    try:
        HWAccess.from_mode_str(machine, mode)
        mem = machine.get_mem()
        read = getattr(mem, "cpu_r%d" % bits)
        write = getattr(mem, "cpu_w%d" % bits)
        if mode == "abort":
            with pytest.raises(HWAccessError):
                read(address)
            with pytest.raises(HWAccessError):
                write(address, 0)
        else:
            expected = (1 << bits) - 1 if mode == "emu" else 0
            assert read(address) == expected
            write(address, 0x80)
            assert read(address) == expected
            write(address, 0)
            assert read(address) == expected
        # Adding probe windows must not convert ordinary bad pointers to RAM.
        from amitools.vamos.machine.error import InvalidMemoryAccessError

        with pytest.raises(InvalidMemoryAccessError):
            mem.cpu_r16(0x900000)
    finally:
        machine.cleanup()


@pytest.mark.parametrize("mode", ["emu", "ignore", "abort"])
@pytest.mark.parametrize("bits", [8, 32])
def machine_hwaccess_custom_width_test(mode, bits):
    machine = Machine()
    try:
        HWAccess.from_mode_str(machine, mode)
        mem = machine.get_mem()
        read, write = getattr(mem, "cpu_r%d" % bits), getattr(mem, "cpu_w%d" % bits)
        if mode == "abort":
            with pytest.raises(HWAccessError):
                read(0xDFF000)
            with pytest.raises(HWAccessError):
                write(0xDFF000, 0)
        else:
            assert read(0xDFF000) == 0
            write(0xDFF000, (1 << bits) - 1)
            assert read(0xDFF000) == 0
    finally:
        machine.cleanup()


@pytest.mark.parametrize("mode", ["emu", "ignore", "abort"])
@pytest.mark.parametrize("bits", [8, 16, 32])
def machine_hwaccess_absent_rom_test(mode, bits):
    machine = Machine()
    try:
        HWAccess.from_mode_str(machine, mode)
        mem = machine.get_mem()
        read, write = getattr(mem, "cpu_r%d" % bits), getattr(mem, "cpu_w%d" % bits)
        if mode == "abort":
            with pytest.raises(HWAccessError):
                read(0xF8000C)
            with pytest.raises(HWAccessError):
                write(0xF8000C, 1)
        else:
            assert read(0xF8000C) == 0
            write(0xF8000C, (1 << bits) - 1)
            assert read(0xF8000C) == 0
    finally:
        machine.cleanup()


@pytest.mark.parametrize("mode", ["emu", "ignore", "abort"])
@pytest.mark.parametrize("bits", [8, 16, 32])
def machine_hwaccess_high_rom_probe_test(mode, bits):
    machine = Machine()
    try:
        mem = machine.get_mem()
        if getattr(mem, "get_address_bits", lambda: 28)() < 32:
            pytest.skip("backend does not support the high ROM probe")
        HWAccess.from_mode_str(machine, mode)
        read, write = getattr(mem, "cpu_r%d" % bits), getattr(mem, "cpu_w%d" % bits)
        if mode == "abort":
            with pytest.raises(HWAccessError):
                read(0x10F8000C)
        else:
            expected = (1 << bits) - 1 if mode == "emu" else 0
            assert read(0x10F8000C) == expected
            write(0x10F8000C, 0)
            assert read(0x10F8000C) == expected
            assert read(0xF8000C) == 0
    finally:
        machine.cleanup()
