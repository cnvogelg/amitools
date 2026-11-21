"""End-to-end native handler test (HANDLER.md step 23j).

A real 68k file system handler is started on an RDB partition exposed through
``scsi.device`` and driven through genuine ``DosPacket``s: the test formats the
partition, creates a directory, writes a file, reads it back and examines it.
The handler binaries live in ``test/handler`` (checked in) and the test is
parameterised over :data:`HANDLERS`, so a new handler is covered by adding an
entry; a missing binary skips its case.
"""

import os

import pytest

from amitools.fs.FSString import FSString
from amitools.fs.blkdev.DiskGeometry import DiskGeometry
from amitools.fs.blkdev.HDFBlockDevice import HDFBlockDevice
from amitools.fs.blkdev.RawBlockDevice import RawBlockDevice
from amitools.fs.rdb.RDisk import RDisk
from amitools.vamos.disk import DiskSession
from amitools.vamos.handler.base import MODE_NEWFILE
from amitools.vamos.handler.native import NativeHandler
from amitools.vamos.libmgr import SetupLibManager
from amitools.vamos.main import wire_handler_transports
from amitools.vamos.machine import Machine, MemoryMap, Runtime
from amitools.vamos.path.vamos import VamosPathManager
from amitools.vamos.schedule import Scheduler

_HANDLER_DIR = os.path.join(os.path.dirname(__file__), "..", "handler")

# Real AmigaDOS file system handlers to run end-to-end. Add a new entry to
# cover a new handler; a case whose binary is absent is skipped. Each entry
# carries the CPU the handler needs, and the exact set of allocations the
# handler deliberately leaves alive after Quit() (see the RDB test). A handler
# that does not implement ACTION_DIE cannot be shut down at all (SFS): its
# ``leftovers`` is ``None`` and the orphan assertion is skipped for it.
#
# FastFileSystem is marked ``full``: its synchronous block I/O is emulated
# instruction by instruction and takes ~60s of the whole suite (~40s for the
# RDB case, ~21s for the raw-device case), so it only runs with --full-suite.
HANDLERS = [
    {
        "name": "pfs3aio",
        "binary": os.path.abspath(os.path.join(_HANDLER_DIR, "pfs3aio")),
        "dos_type": 0x50465303,  # 'PFS\3'
        "cpu": "68000",
        # pfs3aio's Quit() deliberately leaves its OS-lifetime objects alive:
        #   0x4d -> 0x50  AllocVec  the shared "PFS_<device>/<unit>" semaphore
        #   0x20 -> 0x20  AllocMem  the FileSystem.resource FileSysResource
        #   0x3e -> 0x40  AllocMem  the FileSystem.resource FileSysEntry
        "leftovers": [0x20, 0x40, 0x50],
    },
    {
        "name": "smartfilesystem",
        "binary": os.path.abspath(os.path.join(_HANDLER_DIR, "SmartFilesystem")),
        "dos_type": 0x53465300,  # 'SFS\0'
        "cpu": "68020",  # SFS requires a 68020 or better
        # SFS 1.279 does not implement ACTION_DIE: it replies
        # ERROR_ACTION_NOT_KNOWN and stays in its mainloop forever, keeping
        # dos/intuition/utility.library and timer/scsi.device open. The manager
        # forces the teardown (see NativeHandlerManager._request_die), but the
        # handler never runs its cleanup, so there is no clean orphan set to
        # pin. Only the filesystem flow is asserted for this handler.
        "leftovers": None,
    },
    pytest.param(
        {
            "name": "fastfilesystem",
            "binary": os.path.abspath(os.path.join(_HANDLER_DIR, "FastFileSystem")),
            "dos_type": 0x444F5303,  # 'DOS\3' (FFS)
            "cpu": "68000",
            "leftovers": [],
        },
        marks=pytest.mark.full,
    ),
]

# an RDB image large enough for a small volume (1 head, 32 sectors/cylinder)
_CYLS = 100
_SECS = 32
_PART_CYLS = (1, _CYLS - 1)


@pytest.fixture(params=HANDLERS, ids=lambda spec: spec["name"])
def handler_spec(request):
    spec = dict(request.param)
    if not os.path.exists(spec["binary"]):
        pytest.skip("handler fixture not available: %s" % spec["binary"])
    return spec


def _make_rdb(path, dos_type):
    """create a whole-disk RDB image with one partition of ``dos_type``"""
    raw = RawBlockDevice(str(path), read_only=False, block_bytes=512)
    raw.create(_CYLS * _SECS)
    rdisk = RDisk(raw)
    rdisk.create(DiskGeometry(_CYLS, 1, _SECS), rdb_cyls=1)
    rdisk.add_partition(FSString("DH0"), _PART_CYLS, dos_type=dos_type)
    raw.flush()
    rdisk.close()
    raw.close()


def _make_slm(tmp_path, cpu="68000"):
    machine = Machine.from_name(cpu, use_labels=True)
    assert machine is not None
    mem_map = MemoryMap(machine)
    mem_map.setup_ram_allocator()
    runtime = Runtime(machine)
    scheduler = Scheduler(machine)
    path_mgr = VamosPathManager(vols_base_dir=str(tmp_path / "volumes"))
    assert path_mgr.setup()
    slm = SetupLibManager(machine, mem_map, runtime.run, scheduler, path_mgr)
    slm.setup()
    return machine, scheduler, slm


def _assert_teardown(slm, handler_spec):
    """assert the handler's post-shutdown allocation footprint

    A handler that supports ``ACTION_DIE`` (pfs3aio, FFS) frees everything it
    allocated on exit, except a per-handler set of OS-lifetime objects (see
    ``HANDLERS``); assert that exact set is all that is left. A handler that
    does not implement ``ACTION_DIE`` (SFS) never runs its cleanup, so it keeps
    its libraries open and the session cannot be expunged: there is no clean set
    to pin (``leftovers`` is ``None``) and only the shutdown completing without
    an error is checked.
    """
    expected = handler_spec["leftovers"]
    if expected is None:
        return
    leftovers = sorted(size for _, size in slm.alloc.get_orphans())
    assert leftovers == expected


def handler_native_filesystem_end_to_end_test(tmp_path, handler_spec):
    dos_type = handler_spec["dos_type"]
    image = tmp_path / "disk.hdf"
    _make_rdb(image, dos_type)

    machine, scheduler, slm = _make_slm(tmp_path, handler_spec["cpu"])

    # the RDB partition is exposed through scsi.device, writable so it can be
    # formatted
    disk_session = DiskSession([str(image)], read_only=False)
    disk_session.open()
    slm.disk_session = disk_session
    disk_session.install_devices(slm)

    handler = NativeHandler("DH0", {"binary": handler_spec["binary"], "part": "DH0"})
    slm.handler_mgr.register("DH0", handler)
    wire_handler_transports(slm, slm.handler_mgr, machine, scheduler, disk_session)

    # opening the base libs starts the 68k handler task and does the handshake
    slm.open_base_libs()
    assert handler.handler_port != 0
    entry = slm.dos_impl.dos_list.get_entry_by_name("DH0")
    assert entry is not None
    assert entry.struct.dol_Task.aptr == handler.handler_port

    # format the partition, then create a directory and a file in it.
    # A file system handler only accepts ACTION_FORMAT while the volume is
    # inhibited, so inhibit it around the format like AmigaDOS's Format() does.
    handler.inhibit(True)
    handler.format("Work", dos_type)
    handler.inhibit(False)
    lock = handler.create_dir("dir")
    handler.free_lock(lock)

    payload = b"hello from a real 68k file system handler\n"
    fh = handler.find_output("dir/file.txt", MODE_NEWFILE)
    assert handler.write(fh, payload) == len(payload)
    handler.end(fh)

    fh = handler.find_input("dir/file.txt")
    assert handler.read(fh, -1) == payload
    handler.end(fh)

    # examine the file and list the directory through the handler
    lock = handler.locate_object("dir/file.txt")
    fib = handler.examine_object(lock)
    assert not fib.is_dir
    assert fib.size == len(payload)
    handler.free_lock(lock)

    lock = handler.locate_object("dir")
    assert handler.examine_object(lock).is_dir
    entry = handler.examine_next(lock, 0)
    assert entry.name == "file.txt"
    handler.free_lock(lock)

    # shutdown sends ACTION_DIE and frees every handler resource; the owned
    # handler manager is shut down by cleanup() itself
    slm.close_base_libs()
    slm.cleanup()
    disk_session.close()

    _assert_teardown(slm, handler_spec)


def _make_hdf(path, cyls, secs):
    """create a raw whole-disk HDF image (no RDB)"""
    hdf = HDFBlockDevice(str(path))
    hdf.create(DiskGeometry(cyls, 1, secs))
    hdf.close()


def handler_native_raw_device_end_to_end_test(tmp_path, handler_spec):
    # a raw HDF (no RDB) is mounted through the whole-disk synthetic partition
    # (step 27b): the handler formats and uses it without a partition table
    dos_type = handler_spec["dos_type"]
    image = tmp_path / "disk.hdf"
    _make_hdf(image, _CYLS, _SECS)

    machine, scheduler, slm = _make_slm(tmp_path, handler_spec["cpu"])

    disk_session = DiskSession([str(image)], read_only=False)
    disk_session.open()
    slm.disk_session = disk_session
    disk_session.install_devices(slm)

    # no device/part selector: the raw whole-disk partition is the fallback
    handler = NativeHandler("DH0", {"binary": handler_spec["binary"]})
    slm.handler_mgr.register("DH0", handler)
    wire_handler_transports(slm, slm.handler_mgr, machine, scheduler, disk_session)

    slm.open_base_libs()
    assert handler.handler_port != 0
    assert slm.dos_impl.dos_list.get_entry_by_name("DH0") is not None

    # format the raw device, then write and read a file
    handler.inhibit(True)
    handler.format("Work", dos_type)
    handler.inhibit(False)

    payload = b"hello from a raw device\n"
    fh = handler.find_output("file.txt", MODE_NEWFILE)
    assert handler.write(fh, payload) == len(payload)
    handler.end(fh)
    fh = handler.find_input("file.txt")
    assert handler.read(fh, -1) == payload
    handler.end(fh)

    slm.close_base_libs()
    slm.cleanup()
    disk_session.close()

    # same per-handler teardown check as the RDB path (see HANDLERS)
    _assert_teardown(slm, handler_spec)
