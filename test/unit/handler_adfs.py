"""ADFS handler (``adfs``) tests.

The shared handler contract lives in :mod:`handler_contract` and runs here
against :class:`AdfsHandler` via ``TestAdfsContract``. Only behavior specific
to the ADFS handler is asserted in this module.
"""

from types import SimpleNamespace

import pytest
from handler_contract import HandlerContract, expect_error

from amitools.fs import DosType
from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.FSString import FSString
from amitools.fs.blkdev.ADFBlockDevice import ADFBlockDevice
from amitools.fs.blkdev.DiskGeometry import DiskGeometry
from amitools.fs.blkdev.HDFBlockDevice import HDFBlockDevice
from amitools.fs.blkdev.PartBlockDevice import PartBlockDevice
from amitools.fs.blkdev.RawBlockDevice import RawBlockDevice
from amitools.fs.rdb.RDisk import RDisk
from amitools.vamos.handler import (
    MODE_NEWFILE,
    MODE_READWRITE,
    AdfsHandler,
    open_adfs_blkdev,
)


def make_handler(path, name="work", dos_type=DosType.DOS0):
    """build a fresh ADFS volume in an image and open a handler on it"""
    blkdev = ADFBlockDevice(str(path))
    blkdev.create()
    volume = ADFSVolume(blkdev)
    volume.create(FSString(name), dos_type=dos_type)
    return AdfsHandler(name, blkdev)


def write_file(h, path, data, mode=MODE_NEWFILE):
    fh = h.find_output(path, mode)
    assert h.write(fh, data) == len(data)
    h.end(fh)


def read_file(h, path):
    fh = h.find_input(path)
    data = h.read(fh, -1)
    h.end(fh)
    return data


@pytest.fixture
def env(tmp_path):
    handler = make_handler(tmp_path / "work.adf")
    counter = [0]

    def new_handler(name):
        counter[0] += 1
        return make_handler(tmp_path / ("other%d.adf" % counter[0]), name)

    return SimpleNamespace(kind="adfs", h=handler, new_handler=new_handler)


class TestAdfsContract(HandlerContract):
    pass


# ----- ADFS-specific behavior -----


def handler_adfs_protect_comment_date_test(tmp_path):
    h = make_handler(tmp_path / "work.adf")
    write_file(h, "f", b"x")
    h.set_protect("f", 0x123)
    h.set_comment("f", "hello")
    h.set_date("f", 1000000000)
    info = h.examine_object(h.locate_object("f"))
    # ADFS stores the exact protection mask, the comment and the date
    assert info.protection == 0x123
    assert info.comment == "hello"
    assert info.date == 1000000000
    # missing objects fail
    expect_error(205, h.set_protect, "gone", 0)
    expect_error(205, h.set_comment, "gone", "x")
    expect_error(205, h.set_date, "gone", 0)


def handler_adfs_rename_onto_existing_test(tmp_path):
    h = make_handler(tmp_path / "work.adf")
    write_file(h, "a", b"A")
    write_file(h, "b", b"B")
    # ADFS rejects renaming onto an existing object instead of overwriting
    expect_error(203, h.rename_object, "a", "b")


def handler_adfs_create_dir_missing_parent_test(tmp_path):
    h = make_handler(tmp_path / "work.adf")
    # the parent must exist
    expect_error(205, h.create_dir, "missing/sub")


def handler_adfs_rename_directory_with_children_test(tmp_path):
    h = make_handler(tmp_path / "work.adf")
    h.create_dir("d")
    write_file(h, "d/x", b"q")
    h.rename_object("d", "e")
    assert h.examine_object(h.locate_object("e")).is_dir
    assert read_file(h, "e/x") == b"q"
    expect_error(205, h.locate_object, "d")


def handler_adfs_disk_full_test(tmp_path):
    blkdev = HDFBlockDevice(str(tmp_path / "small.hdf"))
    blkdev.create(DiskGeometry(1, 1, 32))
    volume = ADFSVolume(blkdev)
    volume.create(FSString("work"))
    h = AdfsHandler("work", blkdev)
    fh = h.find_output("big", MODE_NEWFILE)
    h.write(fh, b"x" * 20000)
    # the write-back cannot find enough blocks
    expect_error(221, h.end, fh)


def handler_adfs_write_protected_test(tmp_path):
    path = tmp_path / "work.adf"
    blkdev = ADFBlockDevice(str(path))
    blkdev.create()
    volume = ADFSVolume(blkdev)
    volume.create(FSString("work"))
    volume.close()
    blkdev.close()
    # reopen the image read-only
    blkdev = ADFBlockDevice(str(path), read_only=True)
    blkdev.open()
    h = AdfsHandler("work", blkdev, read_only=True)
    assert h.read_only
    expect_error(223, h.create_dir, "x")
    expect_error(223, h.delete_object, "x")
    expect_error(223, h.find_output, "f")
    expect_error(223, h.rename_object, "a", "b")
    expect_error(223, h.set_protect, "f", 0)
    expect_error(223, h.set_comment, "f", "c")
    expect_error(223, h.set_date, "f", 0)
    # reading is still allowed
    info = h.examine_object(h.locate_object(""))
    assert info.is_dir


def handler_adfs_fh_from_lock_readwrite_test(tmp_path):
    h = make_handler(tmp_path / "work.adf")
    write_file(h, "f", b"abc")
    fh = h.fh_from_lock(h.locate_object("f"), MODE_READWRITE)
    assert h.read(fh, 3) == b"abc"
    h.seek(fh, 0, 0)
    h.write(fh, b"XYZ")
    h.end(fh)
    assert read_file(h, "f") == b"XYZ"


# ----- block device construction -----


def handler_adfs_blkdev_dd_adf_test(tmp_path):
    path = tmp_path / "dd.adf"
    blkdev = ADFBlockDevice(str(path))
    blkdev.create()
    blkdev.close()
    # an explicit type and auto-detection both give a DD ADF device
    for kwargs in ({}, {"img": "adf"}, {"img": "xdf"}):
        blkdev = open_adfs_blkdev(str(path), **kwargs)
        try:
            assert isinstance(blkdev, ADFBlockDevice)
            assert not blkdev.hd
        finally:
            blkdev.close()


def handler_adfs_blkdev_hd_adf_test(tmp_path):
    path = tmp_path / "hd.adf"
    blkdev = ADFBlockDevice(str(path), hd=True)
    blkdev.create()
    blkdev.close()
    blkdev = open_adfs_blkdev(str(path), img="adf_hd")
    try:
        assert isinstance(blkdev, ADFBlockDevice)
        assert blkdev.hd
    finally:
        blkdev.close()


def handler_adfs_blkdev_hdf_test(tmp_path):
    path = tmp_path / "disk.hdf"
    blkdev = HDFBlockDevice(str(path))
    blkdev.create(DiskGeometry(16, 16, 63))
    blkdev.close()
    blkdev = open_adfs_blkdev(str(path), img="hdf")
    try:
        assert isinstance(blkdev, HDFBlockDevice)
        assert blkdev.num_blocks == 16 * 16 * 63
    finally:
        blkdev.close()


def handler_adfs_blkdev_rdb_partition_test(tmp_path):
    path = tmp_path / "disk.rdb"
    raw = RawBlockDevice(str(path), read_only=False, block_bytes=512)
    raw.create(160)
    rdisk = RDisk(raw)
    rdisk.create(DiskGeometry(10, 1, 16), rdb_cyls=1)
    assert rdisk.add_partition(FSString("DH0"), (1, 4))
    raw.flush()
    raw.close()
    # select the partition by drive name and by number
    for part in ("DH0", "0"):
        blkdev = open_adfs_blkdev(str(path), img="rdb", part=part)
        try:
            assert isinstance(blkdev, PartBlockDevice)
            # 4 cylinders of 1 head and 16 sectors
            assert blkdev.num_blocks == 4 * 16
        finally:
            blkdev.close()


def handler_adfs_blkdev_bad_image_test(tmp_path):
    path = tmp_path / "garbage.bin"
    path.write_bytes(b"\x00" * 512)
    with pytest.raises(IOError):
        open_adfs_blkdev(str(path))
