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
# cover a new handler; a case whose binary is absent is skipped.
HANDLERS = [
    {
        "name": "pfs3aio",
        "binary": os.path.abspath(os.path.join(_HANDLER_DIR, "pfs3aio")),
        "dos_type": 0x50465303,  # 'PFS\3'
    },
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


def handler_native_filesystem_end_to_end_test(tmp_path, handler_spec):
    dos_type = handler_spec["dos_type"]
    image = tmp_path / "disk.hdf"
    _make_rdb(image, dos_type)

    machine, scheduler, slm = _make_slm(tmp_path)

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

    # A real file system handler keeps a few OS-lifetime objects alive after it
    # exits: the device/unit lock semaphore shared with any other handler on the
    # same disk, and its FileSystem.resource entries that let the volume be
    # mounted again. pfs3aio deliberately never frees them (its Quit() leaves
    # them in the system lists), so these three blocks may remain (requested
    # size, then as reported by the 4-byte aligned allocator):
    #   0x4d -> 0x50  AllocVec  the shared "PFS_<device>/<unit>" semaphore
    #   0x20 -> 0x20  AllocMem  the FileSystem.resource FileSysResource
    #   0x3e -> 0x40  AllocMem  the FileSystem.resource FileSysEntry
    # Everything vamos allocated for the task, its ports, the transport, the
    # locks and files must be gone, so assert nothing else is left over.
    leftovers = sorted(size for _, size in slm.alloc.get_orphans())
    assert leftovers == [0x20, 0x40, 0x50]
