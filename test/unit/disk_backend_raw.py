"""The raw ADF/HDF backend and the type-detecting factory (HANDLER.md step 25).

``RawDiskImage`` wraps the ``amitools.fs`` block devices opened by
``BlkDevFactory`` (raw ADF/HDF and gzipped images), exposes the same block
protocol as the RDB ``DiskImage`` and publishes one synthetic whole-disk DOS
device. ``open_disk_backend`` picks raw vs RDB from the image contents.
"""

import gzip
import shutil

import pytest

import amitools.fs.DosType as DosType
from amitools.fs.FSString import FSString
from amitools.fs.blkdev.ADFBlockDevice import ADFBlockDevice
from amitools.fs.blkdev.DiskGeometry import DiskGeometry
from amitools.fs.blkdev.HDFBlockDevice import HDFBlockDevice
from amitools.fs.blkdev.RawBlockDevice import RawBlockDevice
from amitools.fs.block.BootBlock import BootBlock
from amitools.fs.rdb.RDisk import RDisk
from amitools.vamos.disk import DiskImage, DiskSession, RawDiskImage, open_disk_backend


def _make_adf(path, dos_type=None):
    adf = ADFBlockDevice(str(path))
    adf.create()
    if dos_type is not None:
        boot = BootBlock(adf, 0)
        boot.create(dos_type=dos_type)
        boot.write()
    adf.close()


def _make_hdf(path, geo):
    hdf = HDFBlockDevice(str(path))
    hdf.create(geo)
    hdf.close()


def _make_rdb(path):
    raw = RawBlockDevice(str(path), read_only=False, block_bytes=512)
    raw.create(320)
    rdisk = RDisk(raw)
    rdisk.create(DiskGeometry(10, 1, 32), rdb_cyls=1)
    rdisk.add_partition(FSString("DH0"), (1, 9), dos_type=DosType.DOS3)
    raw.flush()
    rdisk.close()
    raw.close()


def _make_rdb_two(path):
    raw = RawBlockDevice(str(path), read_only=False, block_bytes=512)
    raw.create(320)
    rdisk = RDisk(raw)
    rdisk.create(DiskGeometry(10, 1, 32), rdb_cyls=1)
    rdisk.add_partition(FSString("DH0"), (1, 4), dos_type=DosType.DOS3)
    rdisk.add_partition(FSString("DH1"), (5, 9), dos_type=DosType.DOS3)
    raw.flush()
    rdisk.close()
    raw.close()


def disk_backend_raw_adf_test(tmp_path):
    path = tmp_path / "floppy.adf"
    _make_adf(path, dos_type=DosType.DOS3)

    image = RawDiskImage(path, read_only=False)
    image.open()
    try:
        assert image.block_size == 512
        assert (image.cyls, image.heads, image.secs) == (80, 2, 11)
        assert image.total_blocks == 80 * 2 * 11
        assert image.read_only is False
        assert image.exclusive is True
        # the whole disk is published as one synthetic partition for the
        # native handler (step 27b)
        assert [p.name for p in image.partitions] == ["floppy"]
        assert image.partitions[0].index == 0
        assert image.partitions[0].dos_env.high_cyl == 79

        payload = bytes(range(256)) * 2
        image.write_blocks(3, payload)
        assert image.read_blocks(3) == payload
        assert image.read_blocks(2, 2) == image.read_blocks(2) + image.read_blocks(3)

        device = image.dos_devices()[0]
        assert device.name == "floppy"
        assert device.explicit_name is False
        assert device.dos_env.block_size == 128  # longwords
        assert device.dos_env.surfaces == 2
        assert device.dos_env.blk_per_trk == 11
        assert device.dos_env.low_cyl == 0
        assert device.dos_env.high_cyl == 79
        assert device.dos_env.dos_type == DosType.DOS3
    finally:
        image.close()
    assert image.is_open is False


def disk_backend_raw_read_only_test(tmp_path):
    path = tmp_path / "floppy.adf"
    _make_adf(path)

    image = RawDiskImage(path, read_only=True).open()
    try:
        assert image.read_only is True
        assert len(image.read_blocks(0, 2)) == 1024
        with pytest.raises(PermissionError, match="read-only"):
            image.write_blocks(0, b"\0" * 512)
    finally:
        image.close()


def disk_backend_raw_bounds_test(tmp_path):
    path = tmp_path / "floppy.adf"
    _make_adf(path)

    image = RawDiskImage(path, read_only=False).open()
    try:
        with pytest.raises(ValueError, match="exceeds"):
            image.read_blocks(image.total_blocks - 1, 2)
        with pytest.raises(ValueError, match="negative"):
            image.read_blocks(-1)
        with pytest.raises(ValueError, match="expected"):
            image.write_blocks(0, b"\0" * 512, 2)
    finally:
        image.close()


def disk_backend_raw_hdf_test(tmp_path):
    path = tmp_path / "disk.hdf"
    geo = DiskGeometry(1, 1, 32)
    _make_hdf(path, geo)

    image = RawDiskImage(path, read_only=False).open()
    try:
        assert (image.cyls, image.heads, image.secs) == (1, 1, 32)
        assert image.total_blocks == 32
        payload = b"\xa5" * 512
        image.write_blocks(31, payload)
        assert image.read_blocks(31) == payload
    finally:
        image.close()


def disk_backend_raw_hdf_chs_option_test(tmp_path):
    path = tmp_path / "disk.hdf"
    geo = DiskGeometry(2, 2, 11)
    _make_hdf(path, geo)

    image = RawDiskImage(path, options={"chs": "2,2,11"}).open()
    try:
        assert (image.cyls, image.heads, image.secs) == (2, 2, 11)
        assert image.total_blocks == 44
    finally:
        image.close()


def disk_backend_raw_gzip_test(tmp_path):
    adf = tmp_path / "floppy.adf"
    _make_adf(adf, dos_type=DosType.DOS1)
    adz = tmp_path / "floppy.adz"
    with open(adf, "rb") as src, gzip.open(adz, "wb") as dst:
        shutil.copyfileobj(src, dst)

    image = RawDiskImage(adz, read_only=True).open()
    try:
        assert image.read_only is True
        assert image.total_blocks == 80 * 2 * 11
        assert image.dos_devices()[0].dos_env.dos_type == DosType.DOS1
    finally:
        image.close()

    # a gzipped image cannot be opened read-write
    with pytest.raises(IOError, match="gzip"):
        RawDiskImage(adz, read_only=False).open()


def disk_backend_raw_name_option_test(tmp_path):
    path = tmp_path / "floppy.adf"
    _make_adf(path)
    image = RawDiskImage(path, name="DF0").open()
    try:
        device = image.dos_devices()[0]
        assert device.name == "DF0"
        assert device.explicit_name is True
    finally:
        image.close()


def disk_backend_raw_sanitizes_default_name_test(tmp_path):
    path = tmp_path / "my floppy!.adf"
    _make_adf(path)
    image = RawDiskImage(path).open()
    try:
        assert image.dos_devices()[0].name == "my_floppy_"
    finally:
        image.close()


def disk_backend_factory_picks_raw_test(tmp_path):
    adf = tmp_path / "floppy.adf"
    _make_adf(adf)
    backend = open_disk_backend(adf, options={"name": "DF0"})
    assert isinstance(backend, RawDiskImage)
    assert backend.name == "DF0"
    assert backend.unit == 0

    hdf = tmp_path / "disk.hdf"
    _make_hdf(hdf, DiskGeometry(1, 1, 32))
    assert isinstance(open_disk_backend(hdf), RawDiskImage)

    # a forced type overrides the extension
    assert isinstance(open_disk_backend(hdf, options={"type": "adf_hd"}), RawDiskImage)


def disk_backend_factory_picks_rdb_test(tmp_path):
    rdb = tmp_path / "disk.hdf"
    _make_rdb(rdb)
    backend = open_disk_backend(rdb)
    assert isinstance(backend, DiskImage)


def disk_backend_factory_rejects_raw_options_on_rdb_test(tmp_path):
    rdb = tmp_path / "disk.hdf"
    _make_rdb(rdb)
    with pytest.raises(ValueError, match="does not accept raw options"):
        open_disk_backend(rdb, options={"name": "DH9"})


def disk_backend_part_selects_by_name_test(tmp_path):
    rdb = tmp_path / "disk.hdf"
    _make_rdb_two(rdb)
    backend = open_disk_backend(rdb, options={"part": "DH1"}).open()
    try:
        assert [p.name for p in backend.partitions] == ["DH1"]
        assert backend.partitions[0].index == 1
        assert [d.name for d in backend.dos_devices()] == ["DH1"]
    finally:
        backend.close()


def disk_backend_part_selects_by_index_test(tmp_path):
    rdb = tmp_path / "disk.hdf"
    _make_rdb_two(rdb)
    backend = open_disk_backend(rdb, options={"part": "1"}).open()
    try:
        assert [p.name for p in backend.partitions] == ["DH1"]
    finally:
        backend.close()


def disk_backend_part_unknown_raises_test(tmp_path):
    rdb = tmp_path / "disk.hdf"
    _make_rdb_two(rdb)
    backend = open_disk_backend(rdb, options={"part": "DH9"})
    with pytest.raises(IOError, match="can't find partition"):
        backend.open()


def disk_backend_part_rejected_on_raw_test(tmp_path):
    adf = tmp_path / "floppy.adf"
    _make_adf(adf)
    with pytest.raises(ValueError, match="does not accept RDB options"):
        open_disk_backend(adf, options={"part": "DH0"})


def disk_backend_part_option_through_session_test(tmp_path):
    # the ``?part=`` option flows through the DiskSession spec parsing
    rdb = tmp_path / "disk.hdf"
    _make_rdb_two(rdb)
    session = DiskSession([str(rdb) + "?part=DH1"]).open()
    try:
        assert [p.name for p in session.get_backend(0).partitions] == ["DH1"]
    finally:
        session.close()
