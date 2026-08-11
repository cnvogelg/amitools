from amitools.vamos.lib.dos.DosList import DosList


LDF_DEVICES = 1 << 2
LDF_VOLUMES = 1 << 3


def dos_list_device_link_test(mem_alloc):
    mem, alloc = mem_alloc
    dos_list = DosList(None, None, mem, alloc)

    volume = dos_list.add_volume("root")
    dh0 = dos_list.add_device(
        "DH0", startup_bptr=0x1234, task=0, exclusive=True, unit=0
    )
    dh1 = dos_list.add_device("DH1", startup_bptr=0x5678, unit=0)

    assert mem.r_bstr(volume.name_addr.addr) == "root"
    assert mem.r_bstr(dh0.name_addr.addr) == "DH0"
    assert mem.r_bstr(dh1.name_addr.addr) == "DH1"
    assert dos_list.get_head_addr() == volume.mem.addr
    assert volume.struct.dol_Next.aptr == dh0.mem.addr
    assert dh0.struct.dol_Next.aptr == dh1.mem.addr
    assert dh1.struct.dol_Next.aptr == 0
    assert dh0.struct.dol_Type.val == 0
    assert dh0.struct.dol_Startup.val == 0x1234
    assert dh0.exclusive is True
    assert dh0.unit == 0

    device_lock = dos_list.lock_dos_list(LDF_DEVICES)
    assert device_lock == dh0.mem.addr + 1
    assert dos_list.next_dos_entry(LDF_DEVICES, device_lock) == dh0.mem.addr
    assert dos_list.next_dos_entry(LDF_DEVICES, dh0.mem.addr) == dh1.mem.addr
    assert dos_list.next_dos_entry(LDF_DEVICES, dh1.mem.addr) == 0
    assert dos_list.lock_dos_list(LDF_VOLUMES) == volume.mem.addr + 1

    assert dos_list.remove_entry(dh0) is True
    assert volume.next is dh1
    assert volume.struct.dol_Next.aptr == dh1.mem.addr
    assert dh0.struct.dol_Next.aptr == 0
    assert dos_list.get_entry_by_name("dh0") is None
    dos_list.free_entry(dh0)
    dos_list.free_list()


def dos_list_remove_head_test(mem_alloc):
    mem, alloc = mem_alloc
    dos_list = DosList(None, None, mem, alloc)
    dh0 = dos_list.add_device("DH0", startup_bptr=1)
    dh1 = dos_list.add_device("DH1", startup_bptr=2)

    assert dos_list.remove_entry(dh0) is True
    assert dos_list.get_head_addr() == dh1.mem.addr
    assert dh0.struct.dol_Next.aptr == 0
    dos_list.free_entry(dh0)
    dos_list.free_list()
