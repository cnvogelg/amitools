from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.lib.ExecLibrary import ExecLibrary
from amitools.vamos.machine import Machine, REG_A1, REG_D0, REG_D1
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.task import DosProcess


@pytest.mark.parametrize("method", ["OpenLibrary", "OldOpenLibrary"])
def process_library_directories_test(method):
    machine = Machine()
    alloc = MemoryAlloc.for_machine(machine)
    proc = DosProcess(machine, alloc, "child", func=lambda task: 0)
    name = alloc.alloc_cstr("test.library", label="library name")
    ctx = SimpleNamespace(mem=machine.mem, cpu=machine.cpu, process=proc)
    impl = ExecLibrary()
    locks = {0: None, 0x100: object(), 0x200: object(), 0x300: object()}
    dos = SimpleNamespace(lock_mgr=SimpleNamespace(get_by_b_addr=locks.get))
    impl.lib_mgr = SimpleNamespace(
        get_vlib_by_name=lambda name: SimpleNamespace(get_impl=lambda: dos),
        open_lib=Mock(return_value=0x1234),
    )
    proc.set_current_dir(0x400)
    proc.set_home_dir(0x800)
    assert proc.get_current_dir() == 0x400
    assert proc.get_home_dir() == 0x800
    for cwd in (0x100, 0x300):
        # Guest code changes the public Process, not a cached loader lock.
        proc.proc.current_dir.bptr = cwd
        machine.cpu.w_reg(REG_A1, name.addr)
        machine.cpu.w_reg(REG_D0, 39)
        assert getattr(impl, method)(ctx) == 0x1234
        impl.lib_mgr.open_lib.assert_called_with(
            "test.library",
            39 if method == "OpenLibrary" else 0,
            cwd_lock=locks[cwd],
            progdir_lock=locks[0x200],
        )
    proc.free()
    alloc.free_cstr(name)
    assert alloc.is_all_free()
    machine.cleanup()


def process_current_dir_released_lock_test():
    machine = Machine()
    alloc = MemoryAlloc.for_machine(machine)
    proc = DosProcess(machine, alloc, "child", func=lambda task: 0)
    ctx = SimpleNamespace(mem=machine.mem, cpu=machine.cpu, process=proc)
    # Even a released lock must be returned verbatim, without resolving it.
    proc.proc.current_dir.bptr = 0x1234
    machine.cpu.w_reg(REG_D1, 0x5678)
    assert DosLibrary().CurrentDir(ctx) == 0x1234
    assert proc.proc.current_dir.bptr == 0x5678
    machine.cpu.w_reg(REG_D1, 0)
    assert DosLibrary().CurrentDir(ctx) == 0x5678
    assert proc.get_current_dir() == 0
    proc.free()
    assert alloc.is_all_free()
    machine.cleanup()
