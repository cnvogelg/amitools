import pytest

from amitools.fs.ADFSBitmap import ADFSBitmap
from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.FSString import FSString
from amitools.fs.TimeStamp import TimeStamp
from amitools.fs.blkdev.DiskGeometry import DiskGeometry
from amitools.fs.blkdev.HDFBlockDevice import HDFBlockDevice
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
