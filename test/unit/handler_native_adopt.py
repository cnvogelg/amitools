"""Native handler device-node adoption (HANDLER.md step 24c).

A ``?handler=native`` volume must not create a second DOS node for a name the
``DiskSession`` already published. ``DosList.add_host_devices`` skips a native
volume (the manager owns its node), and the manager *adopts* an existing
``--disk`` partition node when the mount name matches, filling in the handler
fields and leaving ``dol_Startup`` to the session. When the mount name differs
it creates its own node from the referenced partition's startup.
"""

from types import SimpleNamespace
import os

from native_task import TaskHandler

from amitools.fs.FSString import FSString
from amitools.fs.blkdev.DiskGeometry import DiskGeometry
from amitools.fs.blkdev.RawBlockDevice import RawBlockDevice
from amitools.fs.rdb.RDisk import RDisk
from amitools.vamos.disk import DiskSession
from amitools.vamos.handler.native import NativeHandler, NativeHandlerManager
from amitools.vamos.lib.dos.DosList import DosList
from amitools.vamos.libmgr import SetupLibManager
from amitools.vamos.machine import Machine, MemoryMap, Runtime
from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.main import wire_handler_transports
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.path.vamos import VamosPathManager
from amitools.vamos.schedule import Scheduler

HUNK = os.path.join(os.path.dirname(__file__), "data", "tinyhandler.hunk")


class _FakeHandlerMgr:
    """the bits of ``HandlerManager`` ``add_host_devices`` uses"""

    def __init__(self, handlers):
        self.handlers = handlers

    def get_handler(self, name):
        return self.handlers.get(str(name).lower())

    def is_filesystem(self, name):
        return True

    def get_all_names(self):
        return list(self.handlers)


def _fake_handler(is_native, port):
    return SimpleNamespace(is_native=is_native, dispatcher=SimpleNamespace(port=port))


def _make_rdb(path):
    raw = RawBlockDevice(str(path), read_only=False, block_bytes=512)
    raw.create(320)
    rdisk = RDisk(raw)
    rdisk.create(DiskGeometry(10, 1, 32), rdb_cyls=1)
    rdisk.add_partition(FSString("DH0"), (1, 9))
    raw.flush()
    rdisk.close()
    raw.close()


def _make_slm(tmp_path):
    machine = Machine()
    mem_map = MemoryMap(machine)
    mem_map.setup_ram_allocator()
    runtime = Runtime(machine)
    scheduler = Scheduler(machine)
    path_mgr = VamosPathManager(vols_base_dir=str(tmp_path / "volumes"))
    assert path_mgr.setup()
    slm = SetupLibManager(machine, mem_map, runtime.run, scheduler, path_mgr)
    slm.setup()
    return machine, scheduler, slm


def _make_manager(slm, harness, disk_session):
    return NativeHandlerManager(
        slm.machine,
        slm.alloc,
        slm.scheduler,
        slm.seg_loader,
        slm.exec_impl,
        slm.dos_impl,
        handler_mgr=slm.handler_mgr,
        disk_session=disk_session,
        task_factory=harness,
    )


def dos_list_add_host_devices_skips_native_test(mem_alloc):
    """A native volume gets no paired device node; a host volume still does."""
    mem, alloc = mem_alloc
    mgr = _FakeHandlerMgr(
        {
            "work": _fake_handler(is_native=True, port=0x1111),
            "host": _fake_handler(is_native=False, port=0x2222),
        }
    )
    listing = DosList(None, None, mem, alloc, handler_mgr=mgr)
    listing.add_volume("work")
    listing.add_volume("host")

    listing.add_host_devices()

    assert listing.get_device_by_name("work") is None
    dev = listing.get_device_by_name("host")
    assert dev is not None
    assert dev.struct.dol_Task.aptr == 0x2222
    listing.free_list()


def dos_list_get_device_by_name_test(mem_alloc):
    """``get_device_by_name`` ignores a volume entry of the same name."""
    mem, alloc = mem_alloc
    listing = DosList(None, None, mem, alloc)
    volume = listing.add_volume("DH0")
    device = listing.add_device("DH0", startup_bptr=0x1234)

    # the plain lookup prefers the volume entry, the device lookup does not
    assert listing.get_entry_by_name("DH0") is volume
    assert listing.get_device_by_name("DH0") is device
    assert listing.get_device_by_name("missing") is None
    listing.free_list()


def dos_list_fill_device_test(mem_alloc):
    """``fill_device`` sets and clears the handler fields of a device node."""
    mem, alloc = mem_alloc
    listing = DosList(None, None, mem, alloc)
    device = listing.add_device("DH0", startup_bptr=0x1234)

    listing.fill_device(device, task=0x2000, seg_list=0x100, glob_vec=-1, handler=0x40)
    s = device.struct
    assert s.dol_Task.aptr == 0x2000
    assert s.dol_SegList.aptr == 0x100
    assert s.dol_GlobVec.val == -1
    assert s.dol_Handler.aptr == 0x40
    # dol_Startup is left to the DiskSession
    assert s.dol_Startup.val == 0x1234

    listing.fill_device(device)
    assert s.dol_Task.aptr == 0
    assert s.dol_SegList.aptr == 0
    assert s.dol_GlobVec.val == 0
    assert s.dol_Handler.aptr == 0
    assert s.dol_Startup.val == 0x1234
    listing.free_list()


def disk_session_install_dos_ignores_volume_entry_test(tmp_path):
    """A same-named volume entry (a native volume) is not a device duplicate."""
    image = tmp_path / "disk.hdf"
    _make_rdb(image)
    mem = MockMemory(size_kib=64)
    alloc = MemoryAlloc(mem)
    listing = DosList(None, None, mem, alloc)
    free_before = alloc.get_free_bytes()
    listing.add_volume("DH0")  # the native volume's DOS list entry
    dos = SimpleNamespace(
        alloc=alloc, dos_list=listing, update_dos_list_head=lambda: None
    )
    session = DiskSession([image]).open()
    try:
        session.install_dos(dos)
        # the partition node is created next to the volume entry
        assert listing.get_device_by_name("DH0") is not None
        assert listing.get_entry_by_name("DH0") is not None
        session.release_dos(dos)
        listing.free_list()
        assert alloc.get_free_bytes() == free_before
    finally:
        session.close()


def handler_native_adopts_partition_node_test(tmp_path):
    """A native volume named like its partition adopts the ``--disk`` node."""
    image = tmp_path / "disk.hdf"
    _make_rdb(image)
    machine, scheduler, slm = _make_slm(tmp_path)
    disk_session = DiskSession([image]).open()
    disk_session.install_devices(slm)
    slm.open_base_libs()

    # the DiskSession publishes the partition node with a FileSysStartupMsg
    disk_session.install_dos(slm.dos_impl)
    dos_list = slm.dos_impl.dos_list
    node = dos_list.get_device_by_name("DH0")
    assert node is not None
    startup_bptr = node.struct.dol_Startup.val
    assert startup_bptr != 0

    harness = TaskHandler()
    handler = NativeHandler("DH0", {"part": "DH0"})
    slm.handler_mgr.register("DH0", handler)
    mgr = _make_manager(slm, harness, disk_session)
    mgr.start(handler)

    # the very same node was adopted, not duplicated
    assert dos_list.get_device_by_name("DH0") is node
    assert node.struct.dol_Task.aptr == handler.handler_port
    assert node.struct.dol_Handler.aptr != 0
    # ... and the adopted startup is what the handler saw
    assert harness.startup_pkt.arg2.val == startup_bptr

    started = mgr.started[0]
    assert started.adopted is True
    assert started.resources is None

    # stopping clears the handler fields but keeps the session-owned node
    mgr.stop(handler)
    assert dos_list.get_device_by_name("DH0") is node
    assert node.struct.dol_Task.aptr == 0
    assert node.struct.dol_Handler.aptr == 0
    assert node.struct.dol_Startup.val == startup_bptr

    disk_session.release_dos(slm.dos_impl)
    assert dos_list.get_device_by_name("DH0") is None

    mgr.shutdown()
    slm.close_base_libs()
    slm.cleanup()
    disk_session.close()
    assert slm.alloc.is_all_free()


def handler_native_creates_node_for_different_mount_name_test(tmp_path):
    """A mount name differing from the partition creates its own node."""
    image = tmp_path / "disk.hdf"
    _make_rdb(image)
    machine, scheduler, slm = _make_slm(tmp_path)
    disk_session = DiskSession([image]).open()
    disk_session.install_devices(slm)
    slm.open_base_libs()
    disk_session.install_dos(slm.dos_impl)
    dos_list = slm.dos_impl.dos_list

    harness = TaskHandler()
    handler = NativeHandler("WORK", {"device": "DH0"})
    slm.handler_mgr.register("WORK", handler)
    mgr = _make_manager(slm, harness, disk_session)
    mgr.start(handler)

    # the partition node is untouched; the manager created a separate node
    partition = dos_list.get_device_by_name("DH0")
    assert partition is not None
    assert partition.struct.dol_Task.aptr == 0
    node = dos_list.get_device_by_name("WORK")
    assert node is not None
    assert node.struct.dol_Task.aptr == handler.handler_port
    # the created node reuses the partition's FileSysStartupMsg
    assert node.struct.dol_Startup.val != 0
    assert node.struct.dol_Startup.val == partition.struct.dol_Startup.val

    started = mgr.started[0]
    assert started.adopted is False
    # the created node shares the session-owned startup, so the manager owns
    # no startup memory for it
    assert started.resources is None

    # the manager owns its node: stopping removes it again
    mgr.stop(handler)
    assert dos_list.get_device_by_name("WORK") is None
    assert dos_list.get_device_by_name("DH0") is partition

    disk_session.release_dos(slm.dos_impl)
    mgr.shutdown()
    slm.close_base_libs()
    slm.cleanup()
    disk_session.close()
    assert slm.alloc.is_all_free()


def handler_native_creates_node_without_partition_node_test(tmp_path):
    """Without a partition node the manager builds its own startup."""
    image = tmp_path / "disk.hdf"
    _make_rdb(image)
    machine, scheduler, slm = _make_slm(tmp_path)
    disk_session = DiskSession([image]).open()
    disk_session.install_devices(slm)
    slm.open_base_libs()
    # install_dos is not called, so no partition node exists to reuse

    harness = TaskHandler()
    handler = NativeHandler("WORK", {"device": "DH0"})
    slm.handler_mgr.register("WORK", handler)
    mgr = _make_manager(slm, harness, disk_session)
    mgr.start(handler)

    node = slm.dos_impl.dos_list.get_device_by_name("WORK")
    assert node is not None
    assert node.struct.dol_Startup.val != 0
    started = mgr.started[0]
    assert started.adopted is False
    # the manager allocated the startup itself and frees it on teardown
    assert started.resources is not None

    mgr.stop(handler)
    mgr.shutdown()
    slm.close_base_libs()
    slm.cleanup()
    disk_session.close()
    assert slm.alloc.is_all_free()


def handler_native_lifecycle_adopts_via_post_setup_test(tmp_path):
    """The lifecycle publishes the partitions before the handler starts (24f).

    This mirrors ``main``: the disk DOS install is a post-setup callback
    registered *before* the handler transports, so the manager sees the
    partition node when it starts and adopts it.
    """
    image = tmp_path / "disk.hdf"
    _make_rdb(image)
    machine, scheduler, slm = _make_slm(tmp_path)
    disk_session = DiskSession([image]).open()
    disk_session.install_devices(slm)
    slm.disk_session = disk_session
    slm.add_post_setup_callback(
        lambda lib_mgr: disk_session.install_dos(lib_mgr.dos_impl)
    )
    handler = NativeHandler("DH0", {"binary": HUNK, "part": "DH0"})
    slm.handler_mgr.register("DH0", handler)
    wire_handler_transports(slm, slm.handler_mgr, machine, scheduler, disk_session)

    slm.open_base_libs()
    dos_list = slm.dos_impl.dos_list
    node = dos_list.get_device_by_name("DH0")
    assert node is not None
    assert node.struct.dol_Task.aptr == handler.handler_port
    assert node.struct.dol_SegList.aptr != 0
    assert node.struct.dol_Startup.val != 0
    assert slm.handler_mgr.native_mgr.started[0].adopted is True

    # the lifecycle stops the handler before the session frees its node
    slm.handler_mgr.stop_native_transport()
    assert node.struct.dol_Task.aptr == 0
    disk_session.release_dos(slm.dos_impl)
    assert dos_list.get_device_by_name("DH0") is None

    slm.close_base_libs()
    slm.cleanup()
    disk_session.close()
    assert slm.alloc.is_all_free()
