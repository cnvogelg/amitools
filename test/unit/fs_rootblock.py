import struct

import pytest

from amitools.fs import DosType
from amitools.fs.ADFSBitmap import ADFSBitmap
from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs import DosType
from amitools.fs.FSString import FSString
from amitools.fs.TimeStamp import TimeStamp
from amitools.fs.blkdev.DiskGeometry import DiskGeometry
from amitools.fs.blkdev.HDFBlockDevice import HDFBlockDevice
from amitools.fs.block.Block import Block
from amitools.fs.block.BootBlock import BootBlock
from amitools.fs.block.RootBlock import RootBlock
from amitools.fs.validate.Log import Log
from amitools.fs.validate.Validator import Validator


@pytest.fixture(params=[(1760, 2, 880), (1761, 2, 881), (1760, 4, 881), (1761, 4, 882)])
def root_disk(request, tmp_path):
    blocks, reserved, root_num = request.param
    disk = HDFBlockDevice(str(tmp_path / "root.hdf"))
    disk.create(DiskGeometry(1, 1, blocks), reserved=reserved)
    try:
        yield disk, root_num
    finally:
        disk.close()


def fs_rootblock_format_location_test(root_disk):
    disk, root_num = root_disk
    volume = ADFSVolume(disk)
    volume.create(FSString("Test"))
    volume.close()
    # Check the on-disk location independently of the reader's calculation.
    root = RootBlock(disk, root_num)
    root.read()
    assert root.valid
    assert root.name == FSString("Test")
    boot = BootBlock(disk)
    boot.read()
    assert boot.got_root_blk == root_num


@pytest.mark.parametrize("dos_type", range(DosType.DOS0, DosType.DOS7 + 1))
def fs_rootblock_dos_type_extension_fields_test(root_disk, dos_type):
    disk, root_num = root_disk
    root = RootBlock(disk, root_num)
    root.create(FSString("Test"), fstype=dos_type)
    root.blocks_used = 123
    root.write()

    data = disk.read_block(root_num)
    expected = dos_type if DosType.rootblock_tracks_used_blocks(dos_type) else 0
    assert int.from_bytes(data[-16:-12], "big") == expected
    assert int.from_bytes(data[-44:-40], "big") == (
        123 if DosType.rootblock_tracks_used_blocks(dos_type) else 0
    )


@pytest.mark.parametrize("scan_boot", [True, False])
def fs_rootblock_open_external_layout_test(root_disk, scan_boot):
    disk, root_num = root_disk
    # Hard disks formatted by AmigaDOS can leave the boot root pointer zero.
    # Build a volume at an explicit location, bypassing volume.create().
    boot = BootBlock(disk)
    boot.create(root_blk=0)
    boot.write()
    root = RootBlock(disk, root_num)
    ts = TimeStamp()
    root.create(FSString("External"), create_ts=ts, disk_ts=ts, mod_ts=ts)
    bitmap = ADFSBitmap(root)
    bitmap.create()
    bitmap.write()

    volume = ADFSVolume(disk)
    volume.open()
    assert volume.valid
    assert volume.root.blk_num == root_num
    assert volume.name == FSString("External")
    volume.close()

    validator = Validator(disk, Log.ERROR)
    if scan_boot:
        assert validator.scan_boot()[0]
    assert validator.scan_root()
    assert validator.root.blk_num == root_num


def root_long(disk, root_num, idx):
    data = disk.read_block(root_num)
    return struct.unpack_from(">I", data, disk.block_bytes + idx * 4)[0]


@pytest.mark.parametrize(
    "dos_type", [DosType.DOS0 + i for i in range(6)], ids=lambda d: "DOS%d" % (d & 7)
)
def fs_rootblock_format_no_dos_type_test(root_disk, dos_type):
    disk, root_num = root_disk
    volume = ADFSVolume(disk)
    volume.create(FSString("Test"), dos_type=dos_type)
    volume.close()
    # DOS0-5: next hash link (-4) and unused long (-11) stay 0
    assert root_long(disk, root_num, -4) == 0
    assert root_long(disk, root_num, -11) == 0
    root = RootBlock(disk, root_num)
    root.read()
    assert root.fstype == 0
    assert root.blocks_used == 0


@pytest.mark.parametrize(
    "dos_type", [DosType.DOS6, DosType.DOS7], ids=lambda d: "DOS%d" % (d & 7)
)
def fs_rootblock_format_dos_type_test(root_disk, dos_type):
    disk, root_num = root_disk
    volume = ADFSVolume(disk)
    volume.create(FSString("Test"), dos_type=dos_type)
    num_used = volume.bitmap.get_num_used()
    volume.close()
    # DOS6/7: root block keeps dos type (-4) and used blocks (-11)
    assert root_long(disk, root_num, -4) == dos_type
    assert root_long(disk, root_num, -11) == num_used
    assert num_used > 0
    root = RootBlock(disk, root_num)
    root.read()
    assert root.fstype == dos_type
    assert root.blocks_used == num_used


def fs_rootblock_clear_stale_dos_type_test(root_disk):
    disk, root_num = root_disk
    volume = ADFSVolume(disk)
    volume.create(FSString("Test"), dos_type=DosType.DOS1)
    volume.close()
    # older images carry the dos type in the next hash link
    root = RootBlock(disk, root_num)
    root.read()
    root._put_long(-4, DosType.DOS1)
    Block.write(root)
    assert root_long(disk, root_num, -4) == DosType.DOS1
    root = RootBlock(disk, root_num)
    root.read()
    assert root.fstype == 0
    root.write()
    assert root_long(disk, root_num, -4) == 0
