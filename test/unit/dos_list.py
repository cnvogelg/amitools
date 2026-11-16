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


def dos_list_host_device_volume_pairs_test(mem_alloc):
    from types import SimpleNamespace
    from amitools.vamos.lib.lexec.PortManager import PortManager

    mem, alloc = mem_alloc
    listing = DosList(None, None, mem, alloc)
    first = listing.add_volume("system")
    second = listing.add_volume("ram")
    ports = PortManager(alloc)
    listing.add_host_devices(SimpleNamespace(fs_put_msg=lambda *args: None), ports)
    cursor = listing.lock_dos_list(LDF_DEVICES)
    found = []
    while cursor:
        cursor = listing.next_dos_entry(LDF_DEVICES, cursor)
        if cursor:
            found.append(listing.get_entry_by_b_addr(cursor >> 2))
    assert [entry.name for entry in found] == ["system", "ram"]
    for volume, device in zip((first, second), found):
        assert volume.struct.dol_Task.aptr == device.struct.dol_Task.aptr
        assert ports.has_port(device.struct.dol_Task.aptr)
        assert listing.get_entry_by_name(device.name) is volume
        assert listing.get_entry_by_name(device.name, LDF_DEVICES) is device
        assert device.struct.dol_Startup.val == 0
    assert first.struct.dol_Task.aptr != second.struct.dol_Task.aptr
    listing.free_list()
    assert not ports.ports
    assert alloc.is_all_free()


def dos_list_device_handler_test(mem_alloc):
    from types import SimpleNamespace
    from amitools.vamos.lib.lexec.PortManager import PortManager
    from amitools.vamos.libstructs import DosListVolumeStruct

    mem, alloc = mem_alloc

    def is_filesystem(name):
        return name != "nil"

    handler_mgr = SimpleNamespace(
        is_filesystem=is_filesystem,
        get_all_names=lambda: ["work", "nil"],
    )
    listing = DosList(None, None, mem, alloc, handler_mgr=handler_mgr)
    path_mgr = SimpleNamespace(
        get_all_volume_names=lambda: ["work", "nil"],
        get_all_assign_names=lambda: [],
    )
    listing.build_list(path_mgr)
    # a filesystem volume becomes a volume entry ...
    work = listing.get_entry_by_name("work")
    assert work.struct_def is DosListVolumeStruct
    # ... while a device handler is not a volume
    assert listing.get_entry_by_name("nil", LDF_VOLUMES) is None
    # add_host_devices publishes the device with no host port
    ports = PortManager(alloc)
    file_mgr = SimpleNamespace(fs_put_msg=lambda *args: None, handler_mgr=handler_mgr)
    listing.add_host_devices(file_mgr, ports)
    nil = listing.get_entry_by_name("nil", LDF_DEVICES)
    assert nil is not None
    assert nil.struct.dol_Type.val == 0
    assert nil.struct.dol_Task.aptr == 0
    assert listing.get_entry_by_name("nil") is nil
    listing.free_list()
    assert alloc.is_all_free()
