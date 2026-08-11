from amitools.fs.FSString import FSString
from amitools.fs.blkdev.DiskGeometry import DiskGeometry
from amitools.fs.blkdev.RawBlockDevice import RawBlockDevice
from amitools.fs.rdb.RDisk import RDisk
from amitools.vamos.lib.ScsiDevice import CMD_READ
from amitools.vamos.lib.dos.Error import DOSFALSE, DOSTRUE
from amitools.vamos.libstructs import (
    DosEnvecStruct,
    DosListDeviceStruct,
    FileSysStartupMsgStruct,
    IORequestStruct,
)


LDF_DEVICES = 1 << 2


def _make_rdb(path):
    raw = RawBlockDevice(str(path), read_only=False, block_bytes=512)
    raw.create(320)
    rdisk = RDisk(raw)
    rdisk.create(DiskGeometry(10, 1, 32), rdb_cyls=1)
    rdisk.add_partition(FSString("DH0"), (1, 9))
    raw.flush()
    rdisk.close()
    raw.close()


def pytask_disk_exposes_rdb_partition_and_raw_device_test(vamos_task, tmp_path):
    image_path = tmp_path / "disk.hdf"
    _make_rdb(image_path)

    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        name = ctx.alloc.alloc_cstr("DH0")

        device_addr = dos_proxy.FindDosEntry(0, name.addr, LDF_DEVICES)
        assert device_addr != 0
        device = DosListDeviceStruct(ctx.mem, device_addr)
        assert device.dol_Type.val == 0
        assert device.dol_Name.str == "DH0"
        assert ctx.dos_lib.dos_info.di_DevInfo.aptr != 0

        startup = FileSysStartupMsgStruct(
            ctx.mem, device.dol_Startup.val << 2
        )
        assert startup.fssm_Unit.val == 0
        assert startup.fssm_Device.str == "scsi.device"
        env = DosEnvecStruct(ctx.mem, startup.fssm_Environ.aptr)
        assert env.de_LowCyl.val == 1
        assert env.de_HighCyl.val == 9
        assert env.de_Surfaces.val == 1
        assert env.de_BlocksPerTrack.val == 32

        inhibit_name = ctx.alloc.alloc_cstr("DH0:")
        missing_name = ctx.alloc.alloc_cstr("MISSING:")
        assert dos_proxy.Inhibit(inhibit_name.addr, DOSTRUE) == DOSTRUE
        assert dos_proxy.Inhibit(inhibit_name.addr, DOSFALSE) == DOSTRUE
        assert dos_proxy.Inhibit(missing_name.addr, DOSTRUE) == DOSFALSE

        port = exec_proxy.CreateMsgPort()
        request_addr = exec_proxy.CreateIORequest(
            port, IORequestStruct.get_byte_size()
        )
        request = IORequestStruct(ctx.mem, request_addr)
        data = ctx.alloc.alloc_memory(512, label="disk read")

        assert exec_proxy.OpenDevice(
            "scsi.device", 0, request_addr, 0
        ) == 0
        request.command.val = CMD_READ
        request.offset.val = 0
        request.length.val = 512
        request.data.val = data.addr
        assert exec_proxy.DoIO(request_addr) == 0
        assert request.error.val == 0
        assert request.actual.val == 512
        assert ctx.mem.r_block(data.addr, 4) == b"RDSK"

        exec_proxy.CloseDevice(request_addr)
        exec_proxy.DeleteIORequest(request_addr)
        exec_proxy.DeleteMsgPort(port)
        ctx.alloc.free_memory(data)
        ctx.alloc.free_cstr(inhibit_name)
        ctx.alloc.free_cstr(missing_name)
        ctx.alloc.free_cstr(name)
        return 0

    exit_codes = vamos_task.run(
        [proc],
        process=True,
        args=[
            "--vols-base-dir",
            str(tmp_path / "volumes"),
            "--disk",
            str(image_path),
        ],
    )
    assert exit_codes == [0]
