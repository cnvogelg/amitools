"""dos.library volume, link, notify and miscellaneous functions (Step 18)."""

from types import SimpleNamespace

from amitools.vamos.astructs import CSTR, LONG
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.machine.regs import REG_D0, REG_D1, REG_D2, REG_D3, REG_D4, REG_D5

from amitools.vamos.lib.dos.Error import (
    DOSFALSE,
    DOSTRUE,
    ERROR_NOT_IMPLEMENTED,
    ERROR_REQUIRED_ARG_MISSING,
)


def _long(mem, cpu, reg, value):
    cpu.w_reg(reg, value)
    return LONG(cpu=cpu, reg=reg, mem=mem)


def _cstr(mem, cpu, reg, base=0x400):
    cpu.w_reg(reg, base)
    return CSTR(cpu=cpu, reg=reg, mem=mem)


def _ctx():
    mem = MockMemory()
    cpu = MockCPU()
    return SimpleNamespace(mem=mem, cpu=cpu, process=None), mem, cpu


def lib_dos_volume_stubs_test():
    lib = DosLibrary()
    ctx, mem, cpu = _ctx()

    mem.w_cstr(0x400, "dos.library")
    mem.w_cstr(0x480, "Work")
    assert (
        lib.Format(
            ctx,
            _cstr(mem, cpu, REG_D1, 0x400),
            _cstr(mem, cpu, REG_D2, 0x480),
            _long(mem, cpu, REG_D3, 0x444F5300),
        )
        == DOSFALSE
    )
    assert lib.io_err == ERROR_NOT_IMPLEMENTED

    mem.w_cstr(0x400, "DF0:")
    mem.w_cstr(0x480, "NewName")
    assert (
        lib.Relabel(
            ctx,
            _cstr(mem, cpu, REG_D1, 0x400),
            _cstr(mem, cpu, REG_D2, 0x480),
        )
        == DOSFALSE
    )
    assert lib.io_err == ERROR_NOT_IMPLEMENTED

    assert (
        lib.AddBuffers(
            ctx,
            _cstr(mem, cpu, REG_D1, 0x400),
            _long(mem, cpu, REG_D2, 10),
        )
        == DOSFALSE
    )
    assert lib.io_err == ERROR_NOT_IMPLEMENTED

    # missing names are rejected before the stub
    cpu.w_reg(REG_D1, 0)
    assert (
        lib.AddBuffers(
            ctx,
            CSTR(cpu=cpu, reg=REG_D1, mem=mem),
            _long(mem, cpu, REG_D2, 10),
        )
        == DOSFALSE
    )
    assert lib.io_err == ERROR_REQUIRED_ARG_MISSING


def lib_dos_link_stubs_test():
    lib = DosLibrary()
    ctx, mem, cpu = _ctx()

    mem.w_cstr(0x400, "work:link")
    assert (
        lib.MakeLink(
            ctx,
            _cstr(mem, cpu, REG_D1, 0x400),
            _long(mem, cpu, REG_D2, 0x500),
            _long(mem, cpu, REG_D3, 1),
        )
        == DOSFALSE
    )
    assert lib.io_err == ERROR_NOT_IMPLEMENTED

    mem.w_cstr(0x480, "work:path")
    mem.w_cstr(0x400, "work:link")
    assert (
        lib.ReadLink(
            ctx,
            _long(mem, cpu, REG_D1, 0),
            _long(mem, cpu, REG_D2, 0),
            _cstr(mem, cpu, REG_D3, 0x480),
            _long(mem, cpu, REG_D4, 0x500),
            _long(mem, cpu, REG_D5, 64),
        )
        == -1
    )
    assert lib.io_err == ERROR_NOT_IMPLEMENTED


def lib_dos_notify_test():
    lib = DosLibrary()
    ctx, mem, cpu = _ctx()

    notify = _long(mem, cpu, REG_D1, 0x1234)
    assert lib.StartNotify(ctx, notify) == DOSTRUE
    assert lib.io_err == 0
    assert lib.notify.active == {0x1234}

    notify = _long(mem, cpu, REG_D1, 0x1234)
    assert lib.EndNotify(ctx, notify) == DOSTRUE
    assert lib.notify.active == set()

    notify = _long(mem, cpu, REG_D1, 0)
    assert lib.StartNotify(ctx, notify) == DOSFALSE
    assert lib.io_err == ERROR_REQUIRED_ARG_MISSING


def lib_dos_assist_stubs_test():
    lib = DosLibrary()
    ctx, mem, cpu = _ctx()

    assert (
        lib.ChangeMode(
            ctx,
            _long(mem, cpu, REG_D1, 0),
            _long(mem, cpu, REG_D2, 10),
            _long(mem, cpu, REG_D3, 0),
        )
        == DOSFALSE
    )
    assert lib.io_err == ERROR_NOT_IMPLEMENTED

    assert (
        lib.SetOwner(ctx, _cstr(mem, cpu, REG_D1), _long(mem, cpu, REG_D2, 0))
        == DOSFALSE
    )
    assert lib.io_err == ERROR_NOT_IMPLEMENTED

    assert lib.VolumeRequestHook(ctx, _long(mem, cpu, REG_D1, 0x100)) == 0
    assert lib.DoShellMethodTagList(ctx, _long(mem, cpu, REG_D0, 1), None) == 0
    assert (
        lib.ScanStackToken(
            ctx,
            _long(mem, cpu, REG_D1, 0x200),
            _long(mem, cpu, REG_D2, 4096),
        )
        == 4096
    )


def lib_dos_same_device_test():
    lib = DosLibrary()
    ctx, mem, cpu = _ctx()
    locks = {
        10: object(),
        11: object(),
        12: object(),
    }
    names = {id(locks[10]): "work:", id(locks[11]): "Work:", id(locks[12]): "ram:"}
    lib.lock_mgr = SimpleNamespace(
        get_by_b_addr=lambda b_addr: locks.get(b_addr),
        volume_name_of_lock=lambda lock: names[id(lock)],
    )

    assert (
        lib.SameDevice(
            ctx,
            _long(mem, cpu, REG_D1, 10),
            _long(mem, cpu, REG_D2, 11),
        )
        == DOSTRUE
    )
    assert (
        lib.SameDevice(
            ctx,
            _long(mem, cpu, REG_D1, 10),
            _long(mem, cpu, REG_D2, 12),
        )
        == DOSFALSE
    )
