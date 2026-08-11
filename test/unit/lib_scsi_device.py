from types import SimpleNamespace

from amitools.vamos.lib.ExecLibrary import ExecLibrary
from amitools.vamos.lib.ScsiDevice import (
    CMD_READ,
    CMD_WRITE,
    HD_SCSICMD,
    IOERR_ABORTED,
    IOERR_BADADDRESS,
    IOERR_BADLENGTH,
    IOERR_NOCMD,
    NSCMD_DEVICEQUERY,
    NSCMD_TD_FORMAT64,
    NSCMD_TD_READ64,
    NSCMD_TD_WRITE64,
    NSDEVTYPE_TRACKDISK,
    SCSICmdStruct,
    ScsiDevice,
    TD_ADDCHANGEINT,
    TD_FORMAT,
    TD_FORMAT64,
    TD_READ64,
    TD_WRITE64,
    TDERR_BAD_UNIT_NUM,
    TDERR_WRITE_PROT,
)
from amitools.vamos.libstructs.exec_ import IORequestStruct
from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc


IOR_ADDR = 0x1000
DATA_ADDR = 0x2000
SCSI_ADDR = 0x3000
CDB_ADDR = 0x4000
SENSE_ADDR = 0x5000


class Backend:
    def __init__(self, *, read_only=False, total_blocks=1000):
        self.block_size = 512
        self.total_blocks = total_blocks
        self.cyls = 10
        self.heads = 10
        self.secs = 10
        self.read_only = read_only
        self.read_calls = []
        self.write_calls = []

    def read_blocks(self, block_num, num_blocks=1):
        self.read_calls.append((block_num, num_blocks))
        return b"\x5a" * (num_blocks * self.block_size)

    def write_blocks(self, block_num, data, num_blocks=1):
        self.write_calls.append((block_num, data, num_blocks))


class BackendProvider:
    def __init__(self, backends, acknowledge_read_only_writes=False):
        self.backends = backends
        self.acknowledge_read_only_writes = acknowledge_read_only_writes

    def get_backend(self, unit):
        return self.backends.get(unit)


def _make_ctx():
    mem = MockMemory(size_kib=64)
    return SimpleNamespace(mem=mem, alloc=MemoryAlloc(mem))


def _run_io(
    dev,
    ctx,
    command,
    *,
    offset=0,
    length=512,
    data_addr=DATA_ADDR,
    high_offset=0,
):
    ior = IORequestStruct(ctx.mem, IOR_ADDR)
    ior.command.val = command
    ior.offset.val = offset
    ior.length.val = length
    ior.data.val = data_addr
    ior.actual.val = high_offset
    dev.BeginIO(ctx, IOR_ADDR)
    return IORequestStruct(ctx.mem, IOR_ADDR)


def scsi_device_routes_open_requests_by_unit_test():
    backend0 = Backend()
    backend2 = Backend()
    provider = BackendProvider({0: backend0, 2: backend2})
    dev = ScsiDevice(provider)
    ctx = _make_ctx()

    assert dev.open_dev(ctx, IOR_ADDR, 2, 0) == 0
    ior = _run_io(dev, ctx, CMD_READ)

    assert ior.error.val == 0
    assert backend0.read_calls == []
    assert backend2.read_calls == [(0, 1)]

    dev.close_dev(ctx, IOR_ADDR)
    ior = _run_io(dev, ctx, CMD_READ)
    assert ior.error.val == TDERR_BAD_UNIT_NUM


def scsi_device_exposes_provider_unit_zero_backend_test():
    backend0 = Backend()
    provider = BackendProvider({})
    dev = ScsiDevice(provider)
    ctx = _make_ctx()

    assert dev.backend is None

    provider.backends[0] = backend0
    assert dev.open_dev(ctx, IOR_ADDR, 0, 0) == 0
    assert dev.backend is backend0

    ior = _run_io(dev, ctx, CMD_READ)
    assert ior.error.val == 0
    assert backend0.read_calls == [(0, 1)]

    dev.close_dev(ctx, IOR_ADDR)
    ior = _run_io(dev, ctx, CMD_READ)
    assert ior.error.val == TDERR_BAD_UNIT_NUM


def scsi_device_rejects_unknown_unit_test():
    dev = ScsiDevice(BackendProvider({0: Backend()}))
    ctx = _make_ctx()

    assert dev.open_dev(ctx, IOR_ADDR, 3, 0) == TDERR_BAD_UNIT_NUM


def scsi_device_rejects_unaligned_and_unbounded_io_test():
    backend = Backend(total_blocks=2)
    dev = ScsiDevice(backend)
    ctx = _make_ctx()

    ior = _run_io(dev, ctx, CMD_READ, offset=1)
    assert ior.error.val == IOERR_BADLENGTH
    ior = _run_io(dev, ctx, CMD_READ, length=513)
    assert ior.error.val == IOERR_BADLENGTH
    ior = _run_io(dev, ctx, CMD_READ, offset=2 * 512, length=512)
    assert ior.error.val == IOERR_BADLENGTH
    assert backend.read_calls == []


def scsi_device_supports_td64_and_nsd_offsets_test():
    block_num = (1 << 32) // 512
    backend = Backend(total_blocks=block_num + 2)
    dev = ScsiDevice(backend)
    ctx = _make_ctx()

    for command in (TD_READ64, NSCMD_TD_READ64):
        ior = _run_io(dev, ctx, command, high_offset=1)
        assert ior.error.val == 0
        assert ior.actual.val == 512

    assert backend.read_calls == [(block_num, 1), (block_num, 1)]


def scsi_device_reports_write_protection_for_all_write_paths_test():
    backend = Backend(read_only=True)
    dev = ScsiDevice(backend)
    ctx = _make_ctx()
    ctx.mem.w_block(DATA_ADDR, b"\xa5" * 512)

    for command in (CMD_WRITE, TD_WRITE64, NSCMD_TD_WRITE64):
        ior = _run_io(dev, ctx, command)
        assert ior.error.val == TDERR_WRITE_PROT
        assert ior.actual.val == 0

    assert backend.write_calls == []


def scsi_device_allocates_nsd_command_table_test():
    dev = ScsiDevice(Backend())
    ctx = _make_ctx()

    ior = _run_io(
        dev,
        ctx,
        NSCMD_DEVICEQUERY,
        length=16,
        data_addr=DATA_ADDR,
    )
    table_addr = ctx.mem.r32(DATA_ADDR + 12)
    commands = []
    pos = 0
    while True:
        command = ctx.mem.r16(table_addr + pos * 2)
        commands.append(command)
        if command == 0:
            break
        pos += 1

    assert ior.error.val == 0
    assert table_addr != 0
    assert table_addr != 0x7FFF00
    assert ctx.mem.r16(DATA_ADDR + 8) == NSDEVTYPE_TRACKDISK
    assert TD_READ64 in commands
    assert TD_WRITE64 in commands
    assert NSCMD_TD_READ64 in commands
    assert NSCMD_TD_WRITE64 in commands
    assert TD_FORMAT in commands
    assert HD_SCSICMD in commands

    first_table_addr = table_addr
    _run_io(dev, ctx, NSCMD_DEVICEQUERY, length=16, data_addr=DATA_ADDR)
    assert ctx.mem.r32(DATA_ADDR + 12) == first_table_addr

    dev.finish_lib(ctx)
    assert ctx.alloc.is_all_free()


def scsi_device_aborts_pending_change_request_test():
    dev = ScsiDevice(Backend())
    ctx = _make_ctx()

    ior = _run_io(dev, ctx, TD_ADDCHANGEINT)
    assert ior.flags.val & 1 == 0

    assert dev.AbortIO(ctx, IOR_ADDR) == 0
    assert ior.flags.val & 1 == 1
    assert ior.error.val == IOERR_ABORTED
    assert ior.actual.val == 0


def scsi_device_format_commands_write_supplied_blocks_test():
    backend = Backend()
    dev = ScsiDevice(backend)
    ctx = _make_ctx()
    data = b"\xa5" * 512
    ctx.mem.w_block(DATA_ADDR, data)

    for command in (TD_FORMAT, TD_FORMAT64, NSCMD_TD_FORMAT64):
        ior = _run_io(dev, ctx, command)
        assert ior.error.val == 0
        assert ior.actual.val == 512

    assert backend.write_calls == [(0, data, 1)] * 3


def scsi_device_rejects_malformed_direct_scsi_requests_test():
    backend = Backend()
    dev = ScsiDevice(backend)
    ctx = _make_ctx()

    ior = _run_io(
        dev,
        ctx,
        HD_SCSICMD,
        length=SCSICmdStruct.get_byte_size(),
        data_addr=0,
    )
    assert ior.error.val == IOERR_BADADDRESS

    ior = _run_io(
        dev,
        ctx,
        HD_SCSICMD,
        length=SCSICmdStruct.get_byte_size() - 1,
        data_addr=SCSI_ADDR,
    )
    assert ior.error.val == IOERR_BADLENGTH

    scsi = SCSICmdStruct(ctx.mem, SCSI_ADDR)
    scsi.scsi_Command.val = CDB_ADDR
    scsi.scsi_CmdLength.val = 5
    scsi.scsi_SenseData.val = SENSE_ADDR
    scsi.scsi_SenseLength.val = 18
    ctx.mem.w8(CDB_ADDR, 0x12)
    ior = _run_io(
        dev,
        ctx,
        HD_SCSICMD,
        length=SCSICmdStruct.get_byte_size(),
        data_addr=SCSI_ADDR,
    )
    assert ior.error.val == 0
    assert SCSICmdStruct(ctx.mem, SCSI_ADDR).scsi_Status.val == 2

    scsi.scsi_Data.val = 0
    scsi.scsi_Length.val = 36
    scsi.scsi_CmdLength.val = 6
    ctx.mem.w8(CDB_ADDR + 4, 36)
    ior = _run_io(
        dev,
        ctx,
        HD_SCSICMD,
        length=SCSICmdStruct.get_byte_size(),
        data_addr=SCSI_ADDR,
    )
    assert ior.error.val == 0
    assert SCSICmdStruct(ctx.mem, SCSI_ADDR).scsi_Status.val == 2


def scsi_device_caps_read_capacity_last_lba_test():
    cases = (
        (1000, 999),
        (1 << 32, 0xFFFFFFFF),
        ((1 << 32) + 1000, 0xFFFFFFFF),
    )

    for total_blocks, expected_last_lba in cases:
        dev = ScsiDevice(Backend(total_blocks=total_blocks))
        ctx = _make_ctx()
        scsi = SCSICmdStruct(ctx.mem, SCSI_ADDR)
        scsi.scsi_Data.val = DATA_ADDR
        scsi.scsi_Length.val = 8
        scsi.scsi_Command.val = CDB_ADDR
        scsi.scsi_CmdLength.val = 10
        ctx.mem.w8(CDB_ADDR, 0x25)

        ior = _run_io(
            dev,
            ctx,
            HD_SCSICMD,
            length=SCSICmdStruct.get_byte_size(),
            data_addr=SCSI_ADDR,
        )

        assert ior.error.val == 0
        assert scsi.scsi_Status.val == 0
        assert scsi.scsi_Actual.val == 8
        assert ctx.mem.r32(DATA_ADDR) == expected_last_lba
        assert ctx.mem.r32(DATA_ADDR + 4) == 512


def scsi_device_rejects_unknown_commands_by_default_test():
    ctx = _make_ctx()
    ior = _run_io(ScsiDevice(Backend()), ctx, 0x1234)
    assert ior.error.val == IOERR_NOCMD

    compatible = ScsiDevice(
        Backend(), acknowledge_unsupported_commands=True
    )
    ior = _run_io(compatible, ctx, 0x1234)
    assert ior.error.val == 0


def scsi_device_reports_direct_scsi_write_protection_test():
    backend = Backend(read_only=True)
    dev = ScsiDevice(backend)
    ctx = _make_ctx()
    ior = IORequestStruct(ctx.mem, IOR_ADDR)
    ior.command.val = HD_SCSICMD
    ior.data.val = SCSI_ADDR
    ior.length.val = SCSICmdStruct.get_byte_size()

    scsi = SCSICmdStruct(ctx.mem, SCSI_ADDR)
    scsi.scsi_Data.val = DATA_ADDR
    scsi.scsi_Length.val = 512
    scsi.scsi_Command.val = CDB_ADDR
    scsi.scsi_CmdLength.val = 10
    scsi.scsi_SenseData.val = SENSE_ADDR
    scsi.scsi_SenseLength.val = 18
    ctx.mem.w8(CDB_ADDR, 0x2A)
    ctx.mem.w32(CDB_ADDR + 2, 0)
    ctx.mem.w16(CDB_ADDR + 7, 1)

    dev.BeginIO(ctx, IOR_ADDR)

    assert SCSICmdStruct(ctx.mem, SCSI_ADDR).scsi_Status.val == 2
    assert ctx.mem.r8(SENSE_ADDR + 2) == 0x07
    assert ctx.mem.r8(SENSE_ADDR + 12) == 0x27
    assert backend.write_calls == []


def scsi_device_supports_explicit_read_only_acknowledgement_test():
    backend = Backend(read_only=True)
    dev = ScsiDevice(backend, acknowledge_read_only_writes=True)
    ctx = _make_ctx()
    ctx.mem.w_block(DATA_ADDR, b"\xa5" * 512)

    ior = _run_io(dev, ctx, CMD_WRITE)

    assert ior.error.val == 0
    assert ior.actual.val == 512
    assert backend.write_calls == []


def scsi_device_honors_provider_read_only_compatibility_policy_test():
    backend = Backend(read_only=True)
    provider = BackendProvider(
        {0: backend}, acknowledge_read_only_writes=True
    )
    dev = ScsiDevice(provider)
    ctx = _make_ctx()
    ctx.mem.w_block(DATA_ADDR, b"\xa5" * 512)
    assert dev.open_dev(ctx, IOR_ADDR, 0, 0) == 0

    ior = _run_io(dev, ctx, CMD_WRITE)

    assert ior.error.val == 0
    assert ior.actual.val == 512
    assert backend.write_calls == []


class HookDevice:
    def __init__(self, open_error=0):
        self.open_error = open_error
        self.calls = []

    def open_dev(self, ctx, io_request, unit, flags):
        self.calls.append(("open", io_request, unit, flags))
        return self.open_error

    def close_dev(self, ctx, io_request):
        self.calls.append(("close", io_request))

    def AbortIO(self, ctx, io_request):
        self.calls.append(("abort", io_request))
        return 0


class FakeVLib:
    def __init__(self, impl):
        self.impl = impl

    def get_impl(self):
        return self.impl


class FakeLibManager:
    def __init__(self, impl):
        self.vlib = FakeVLib(impl)
        self.closed = []

    def open_lib(self, name):
        return 0x6000

    def get_vlib_by_addr(self, addr):
        return self.vlib if addr == 0x6000 else None

    def close_lib(self, addr):
        self.closed.append(addr)


def exec_open_close_device_invokes_optional_hooks_test():
    ctx = _make_ctx()
    impl = HookDevice()
    lib_mgr = FakeLibManager(impl)
    exec_impl = ExecLibrary()
    exec_impl.lib_mgr = lib_mgr
    name = SimpleNamespace(str="scsi.device")

    assert exec_impl.OpenDevice(ctx, name, 2, IOR_ADDR, 7) == 0
    assert IORequestStruct(ctx.mem, IOR_ADDR).device.aptr == 0x6000
    exec_impl.CloseDevice(ctx, IOR_ADDR)

    assert impl.calls == [
        ("open", IOR_ADDR, 2, 7),
        ("close", IOR_ADDR),
    ]
    assert lib_mgr.closed == [0x6000]
    assert IORequestStruct(ctx.mem, IOR_ADDR).device.aptr == 0


def exec_abort_device_invokes_device_hook_test():
    ctx = _make_ctx()
    impl = HookDevice()
    lib_mgr = FakeLibManager(impl)
    exec_impl = ExecLibrary()
    exec_impl.lib_mgr = lib_mgr
    IORequestStruct(ctx.mem, IOR_ADDR).device.aptr = 0x6000

    assert exec_impl.AbortIO(ctx, IOR_ADDR) == 0
    assert impl.calls == [("abort", IOR_ADDR)]


def exec_open_device_rolls_back_failed_hook_test():
    ctx = _make_ctx()
    impl = HookDevice(open_error=TDERR_BAD_UNIT_NUM)
    lib_mgr = FakeLibManager(impl)
    exec_impl = ExecLibrary()
    exec_impl.lib_mgr = lib_mgr

    result = exec_impl.OpenDevice(
        ctx, SimpleNamespace(str="scsi.device"), 9, IOR_ADDR, 0
    )

    assert result == TDERR_BAD_UNIT_NUM
    assert lib_mgr.closed == [0x6000]
    assert IORequestStruct(ctx.mem, IOR_ADDR).device.aptr == 0
