from amitools.vamos.libstructs import DosListAssignStruct, DosListVolumeStruct
from amitools.vamos.lib.dos.Error import DOSTRUE

LDF_VOLUMES = 1 << 3
LDF_ASSIGNS = 1 << 4


def pytask_dos_find_dos_entry_test(vamos_task):
    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()

        root_entry = ctx.dos_lib.dos_list.get_entry_by_name("root")
        root_name = ctx.alloc.alloc_bstr("root:")

        assert (
            dos_proxy.FindDosEntry(0, root_name.addr, LDF_VOLUMES)
            == root_entry.mem.addr
        )
        assert dos_proxy.FindDosEntry(0, root_name.addr, LDF_ASSIGNS) == 0

        first_volume = dos_proxy.LockDosList(LDF_VOLUMES)
        assert first_volume != 0
        assert dos_proxy.AttemptLockDosList(LDF_VOLUMES) == first_volume
        dos_proxy.UnLockDosList(LDF_VOLUMES)

        ctx.alloc.free_bstr(root_name)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_make_add_rem_free_entry_test(vamos_task):
    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()

        vol_name = ctx.alloc.alloc_bstr("scratch")
        assign_name = ctx.alloc.alloc_bstr("ramalias")

        vol_addr = dos_proxy.MakeDosEntry(vol_name.addr, 2)
        assign_addr = dos_proxy.MakeDosEntry(assign_name.addr, 1)

        vol_entry = DosListVolumeStruct(ctx.mem, vol_addr)
        assign_entry = DosListAssignStruct(ctx.mem, assign_addr)

        assert vol_entry.name.str == "scratch"
        assert vol_entry.type.val == 2
        assert assign_entry.name.str == "ramalias"
        assert assign_entry.type.val == 1

        assert dos_proxy.AddDosEntry(vol_addr) == DOSTRUE
        assert dos_proxy.RemDosEntry(vol_addr) == DOSTRUE
        assert dos_proxy.AddDosEntry(assign_addr) == DOSTRUE
        assert dos_proxy.RemDosEntry(assign_addr) == DOSTRUE

        assert vol_addr in ctx.dos_lib.dos_entries
        assert assign_addr in ctx.dos_lib.dos_entries

        dos_proxy.FreeDosEntry(vol_addr)
        dos_proxy.FreeDosEntry(assign_addr)

        assert vol_addr not in ctx.dos_lib.dos_entries
        assert assign_addr not in ctx.dos_lib.dos_entries

        ctx.alloc.free_bstr(vol_name)
        ctx.alloc.free_bstr(assign_name)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]
