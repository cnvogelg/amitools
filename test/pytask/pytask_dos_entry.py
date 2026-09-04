from amitools.vamos.libstructs import (
    DosEnvecStruct,
    DosListAssignStruct,
    DosListDeviceStruct,
    DosListVolumeStruct,
    FileSysStartupMsgStruct,
)
from amitools.vamos.lib.dos.Error import (
    DOSFALSE,
    DOSTRUE,
    ERROR_DEVICE_NOT_MOUNTED,
)

LDF_DEVICES = 1 << 2
LDF_VOLUMES = 1 << 3
LDF_ASSIGNS = 1 << 4


def pytask_dos_find_dos_entry_test(vamos_task):
    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()

        root_entry = ctx.dos_lib.dos_list.get_entry_by_name("root")
        root_name = ctx.alloc.alloc_cstr("root:")

        assert (
            dos_proxy.FindDosEntry(0, root_name.addr, LDF_VOLUMES)
            == root_entry.mem.addr
        )
        assert dos_proxy.FindDosEntry(0, root_name.addr, LDF_ASSIGNS) == 0

        first_volume = dos_proxy.LockDosList(LDF_VOLUMES)
        assert first_volume != 0
        assert dos_proxy.AttemptLockDosList(LDF_VOLUMES) == first_volume
        dos_proxy.UnLockDosList(LDF_VOLUMES)

        original_head = ctx.dos_lib.dos_list.get_head_addr()
        assign_name = ctx.alloc.alloc_cstr("dynamic")
        assign_lock = ctx.dos_lib.lock_mgr.create_lock(None, "root:", False)
        assert dos_proxy.AssignLock(assign_name.addr, assign_lock.b_addr) == DOSTRUE
        dynamic = ctx.dos_lib.dos_list.get_entry_by_name("dynamic")
        assert ctx.dos_lib.dos_list.get_head_addr() == dynamic.mem.addr
        assert ctx.dos_lib.dos_info.di_DevInfo.aptr == dynamic.mem.addr
        assert dos_proxy.AssignLock(assign_name.addr, 0) == DOSTRUE
        assert ctx.dos_lib.dos_list.get_head_addr() == original_head
        assert ctx.dos_lib.dos_info.di_DevInfo.aptr == original_head

        ctx.alloc.free_cstr(assign_name)
        ctx.alloc.free_cstr(root_name)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_make_add_rem_free_entry_test(vamos_task):
    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()

        vol_name = ctx.alloc.alloc_cstr("scratch")
        assign_name = ctx.alloc.alloc_cstr("ramalias")
        device_name = ctx.alloc.alloc_cstr("testdisk")

        vol_addr = dos_proxy.MakeDosEntry(vol_name.addr, 2)
        assign_addr = dos_proxy.MakeDosEntry(assign_name.addr, 1)
        device_addr = dos_proxy.MakeDosEntry(device_name.addr, 0)

        vol_entry = DosListVolumeStruct(ctx.mem, vol_addr)
        assign_entry = DosListAssignStruct(ctx.mem, assign_addr)
        device_entry = DosListDeviceStruct(ctx.mem, device_addr)

        assert vol_entry.name.str == "scratch"
        assert vol_entry.type.val == 2
        assert assign_entry.name.str == "ramalias"
        assert assign_entry.type.val == 1
        assert device_entry.name.str == "testdisk"
        assert device_entry.type.val == 0

        assert dos_proxy.AddDosEntry(vol_addr) == DOSTRUE
        assert dos_proxy.FindDosEntry(0, vol_name.addr, LDF_VOLUMES) == vol_addr
        assert dos_proxy.RemDosEntry(vol_addr) == DOSTRUE
        assert dos_proxy.FindDosEntry(0, vol_name.addr, LDF_VOLUMES) == 0
        assert dos_proxy.AddDosEntry(assign_addr) == DOSTRUE
        assert dos_proxy.FindDosEntry(0, assign_name.addr, LDF_ASSIGNS) == assign_addr
        assert dos_proxy.RemDosEntry(assign_addr) == DOSTRUE
        assert dos_proxy.FindDosEntry(0, assign_name.addr, LDF_ASSIGNS) == 0
        assert dos_proxy.AddDosEntry(device_addr) == DOSTRUE
        assert dos_proxy.FindDosEntry(0, device_name.addr, LDF_DEVICES) == device_addr
        assert dos_proxy.AddDosEntry(device_addr) == DOSFALSE
        assert dos_proxy.RemDosEntry(device_addr) == DOSTRUE
        assert dos_proxy.FindDosEntry(0, device_name.addr, LDF_DEVICES) == 0
        assert dos_proxy.RemDosEntry(device_addr) == DOSFALSE

        assert vol_addr in ctx.dos_lib.dos_entries
        assert assign_addr in ctx.dos_lib.dos_entries
        assert device_addr in ctx.dos_lib.dos_entries

        dos_proxy.FreeDosEntry(vol_addr)
        dos_proxy.FreeDosEntry(assign_addr)
        dos_proxy.FreeDosEntry(device_addr)

        assert vol_addr not in ctx.dos_lib.dos_entries
        assert assign_addr not in ctx.dos_lib.dos_entries
        assert device_addr not in ctx.dos_lib.dos_entries

        ctx.alloc.free_cstr(vol_name)
        ctx.alloc.free_cstr(assign_name)
        ctx.alloc.free_cstr(device_name)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_disk_device_test(vamos_task):
    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        env = ctx.alloc.alloc_astruct(DosEnvecStruct, label="TestDosEnvec")
        fssm = ctx.alloc.alloc_astruct(
            FileSysStartupMsgStruct, label="TestFileSysStartupMsg"
        )
        exec_name = ctx.alloc.alloc_bstr("scsi.device")
        env.de_LowCyl.val = 1
        env.de_HighCyl.val = 100
        fssm.fssm_Unit.val = 0
        fssm.fssm_Device.aptr = exec_name.addr
        fssm.fssm_Environ.aptr = env.addr

        entry = ctx.dos_lib.dos_list.add_device(
            "DH0", fssm.addr >> 2, exclusive=True, unit=0
        )
        ctx.dos_lib.update_dos_list_head()

        cname = ctx.alloc.alloc_cstr("DH0:")
        missing = ctx.alloc.alloc_cstr("MISSING:")
        assert dos_proxy.FindDosEntry(0, cname.addr, LDF_DEVICES) == entry.mem.addr
        assert entry.struct.dol_Startup.val == fssm.addr >> 2
        assert entry.struct.dol_Name.str == "DH0"
        assert fssm.fssm_Device.str == "scsi.device"
        assert fssm.fssm_Environ.aptr == env.addr
        assert ctx.dos_lib.dos_info.di_DevInfo.aptr == (
            ctx.dos_lib.dos_list.get_head_addr()
        )

        assert dos_proxy.Inhibit(cname.addr, DOSTRUE) == DOSTRUE
        assert entry.inhibited is True
        assert dos_proxy.Inhibit(cname.addr, DOSFALSE) == DOSTRUE
        assert entry.inhibited is False
        assert dos_proxy.Inhibit(missing.addr, DOSTRUE) == DOSFALSE
        assert dos_proxy.IoErr() == ERROR_DEVICE_NOT_MOUNTED

        assert ctx.dos_lib.dos_list.remove_entry(entry)
        ctx.dos_lib.update_dos_list_head()
        ctx.dos_lib.dos_list.free_entry(entry)

        ctx.alloc.free_cstr(cname)
        ctx.alloc.free_cstr(missing)
        ctx.alloc.free_bstr(exec_name)
        env.free()
        fssm.free()
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]
