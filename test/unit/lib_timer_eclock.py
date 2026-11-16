from unittest.mock import Mock

from amitools.vamos.lib.TimerDevice import TimerDevice


def timer_eclock_pal_rate_test(monkeypatch):
    import time

    timer = TimerDevice()
    value = Mock()
    # One exact second advances by the advertised PAL frequency, including
    # across the 32-bit low-word boundary. Keep subsecond precision too.
    start_ns = 6_054_500_000_000
    readings = []
    for timestamp in [start_ns, start_ns + 1_000_000_000, start_ns + 1_500_000_000]:
        monkeypatch.setattr(time, "monotonic_ns", lambda: timestamp)
        assert timer.ReadEClock(None, value) == 709_379
        hi, lo = value.set_time_val.call_args.args
        readings.append((hi << 32) | lo)
    assert readings[1] - readings[0] == 709_379
    assert readings[2] - readings[1] in (354_689, 354_690)
    assert readings[0] < 1 << 32 <= readings[1]


def timer_exec_frequency_fields_test():
    from amitools.vamos.libmgr import SetupLibManager
    from amitools.vamos.machine import Machine, MemoryMap, Runtime
    from amitools.vamos.path import PathManager
    from amitools.vamos.schedule import Scheduler

    machine = Machine()
    memory_map = MemoryMap(machine)
    memory_map.setup_ram_allocator()
    manager = SetupLibManager(
        machine, memory_map, Runtime(machine).run, Scheduler(machine), PathManager()
    )
    manager.setup()
    manager.open_base_libs()
    try:
        base = machine.mem.r32(4)
        assert machine.mem.r8(base + 530) == 50
        assert machine.mem.r8(base + 531) == 50
        assert machine.mem.r32(base + 568) == TimerDevice.ECLOCK_HZ == 709_379
    finally:
        manager.close_base_libs()
        manager.cleanup()
        machine.cleanup()
