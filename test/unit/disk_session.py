from unittest.mock import MagicMock

import pytest

from amitools.fs.FSString import FSString
from amitools.fs.blkdev.DiskGeometry import DiskGeometry
from amitools.fs.blkdev.RawBlockDevice import RawBlockDevice
from amitools.fs.rdb.RDisk import RDisk
from amitools.vamos.disk import DiskImage, DiskSession


def _make_rdb(path):
    raw = RawBlockDevice(str(path), read_only=False, block_bytes=512)
    raw.create(320)
    rdisk = RDisk(raw)
    rdisk.create(DiskGeometry(10, 1, 32), rdb_cyls=1)
    rdisk.add_partition(FSString("DH0"), (1, 9))
    raw.flush()
    rdisk.close()
    raw.close()


def disk_image_opens_whole_rdb_test(tmp_path):
    image_path = tmp_path / "disk.hdf"
    _make_rdb(image_path)

    image = DiskImage(image_path)
    image.open()

    assert image.read_only is True
    assert image.block_size == 512
    assert image.total_blocks == 320
    assert (image.cyls, image.heads, image.secs) == (10, 1, 32)
    assert image.read_blocks(0)[:4] == b"RDSK"
    assert [(part.name, part.index) for part in image.partitions] == [("DH0", 0)]
    assert image.partitions[0].dos_env.low_cyl == 1
    assert image.partitions[0].dos_env.high_cyl == 9

    image.close()
    assert image.is_open is False


def disk_image_checks_ranges_and_write_protection_test(tmp_path):
    image_path = tmp_path / "disk.hdf"
    _make_rdb(image_path)
    image = DiskImage(image_path).open()

    assert len(image.read_blocks(319)) == 512
    with pytest.raises(ValueError, match="exceeds"):
        image.read_blocks(319, 2)
    with pytest.raises(ValueError, match="negative"):
        image.read_blocks(-1)
    with pytest.raises(PermissionError, match="read-only"):
        image.write_blocks(10, b"\0" * 512)

    image.close()


def disk_image_rejects_geometry_larger_than_host_image_test(tmp_path):
    image_path = tmp_path / "disk.hdf"
    _make_rdb(image_path)
    raw = RawBlockDevice(str(image_path), read_only=False, block_bytes=512)
    raw.open()
    rdisk = RDisk(raw)
    assert rdisk.open()
    rdisk.rdb.phy_drv.cyls = 20
    rdisk.rdb.write()
    raw.flush()
    rdisk.close()
    raw.close()

    with pytest.raises(IOError, match="geometry exceeds"):
        DiskImage(image_path).open()


def disk_image_finds_rdb_in_first_sixteen_blocks_test(tmp_path):
    image_path = tmp_path / "disk.hdf"
    _make_rdb(image_path)
    raw = RawBlockDevice(str(image_path), read_only=False, block_bytes=512)
    raw.open()
    raw.write_block(15, raw.read_block(0))
    raw.write_block(0, b"\0" * 512)
    raw.flush()
    raw.close()

    image = DiskImage(image_path).open()
    assert image.rdb_block == 15
    assert [part.name for part in image.partitions] == ["DH0"]
    image.close()


def disk_image_holds_exclusive_host_lock_test(tmp_path):
    image_path = tmp_path / "disk.hdf"
    _make_rdb(image_path)
    first = DiskImage(image_path).open()
    second = DiskImage(image_path)

    assert first.exclusive is True
    with pytest.raises(IOError, match="exclusively lock"):
        second.open()

    first.close()
    assert first.exclusive is False
    second.open()
    second.close()


def disk_image_releases_lock_when_failed_backend_close_raises_test(tmp_path):
    image = DiskImage(tmp_path / "disk.hdf")
    image.host_lock = MagicMock()
    raw = MagicMock()
    raw.close.side_effect = IOError("close failed")
    image._open_raw = MagicMock(return_value=raw)
    image._scan_for_rdb = MagicMock(return_value=None)

    with pytest.raises(IOError, match="no RDB"):
        image.open()

    raw.close.assert_called_once_with()
    image.host_lock.release.assert_called_once_with()


def disk_session_assigns_units_and_closes_owned_backends_test():
    first = MagicMock()
    second = MagicMock()
    session = DiskSession()

    assert session.add_backend(first, owned=True) == 0
    assert session.add_backend(second, owned=True) == 1
    session.open()

    first.open.assert_called_once_with()
    second.open.assert_called_once_with()
    assert session.get_backend(0) is first
    assert session.get_backend(1) is second

    session.close()
    first.close.assert_called_once_with()
    second.close.assert_called_once_with()


def disk_session_closes_partial_open_on_failure_test():
    first = MagicMock()
    second = MagicMock()
    second.open.side_effect = IOError("broken image")
    session = DiskSession()
    session.add_backend(first, owned=True)
    session.add_backend(second, owned=True)

    with pytest.raises(IOError, match="broken image"):
        session.open()

    first.close.assert_called_once_with()
    second.close.assert_not_called()
    session.close()
    first.close.assert_called_once_with()
    second.close.assert_not_called()
