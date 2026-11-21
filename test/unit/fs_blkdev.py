"""Multi-block read/write on the ADF and HDF block devices.

``RawBlockDevice``/``ImageFile`` already accept a ``num_blks`` argument; these
tests pin the same behaviour for the ADF and HDF block devices so a whole-disk
backend can read and write several blocks in one call.
"""

import pytest

from amitools.fs.blkdev.ADFBlockDevice import ADFBlockDevice
from amitools.fs.blkdev.BlkDevFactory import BlkDevFactory
from amitools.fs.blkdev.DiskGeometry import DiskGeometry
from amitools.fs.blkdev.HDFBlockDevice import HDFBlockDevice
from amitools.fs.blkdev.ImageFile import ImageFile


def adf_block_device_multi_block_test(tmp_path):
    path = tmp_path / "floppy.adf"
    adf = ADFBlockDevice(str(path))
    adf.create()
    try:
        assert adf.block_bytes == 512
        # the default is still a single block
        assert len(adf.read_block(0)) == 512
        # a multi-block read matches consecutive single-block reads
        assert adf.read_block(2, 3) == (
            adf.read_block(2) + adf.read_block(3) + adf.read_block(4)
        )
        # a multi-block write round-trips
        payload = bytes(range(256)) * 2 * 3
        adf.write_block(5, payload, 3)
        assert adf.read_block(5, 3) == payload
    finally:
        adf.close()

    # the multi-block write survived the flush to disk
    adf = ADFBlockDevice(str(path), read_only=True)
    adf.open()
    try:
        assert adf.read_block(5, 3) == bytes(range(256)) * 2 * 3
    finally:
        adf.close()


def adf_block_device_bounds_test(tmp_path):
    path = tmp_path / "floppy.adf"
    adf = ADFBlockDevice(str(path))
    adf.create()
    try:
        # a range that runs past the end is rejected
        with pytest.raises(ValueError):
            adf.read_block(adf.num_blocks - 1, 2)
        # a wrong sized write is rejected
        with pytest.raises(ValueError):
            adf.write_block(0, b"\0" * 512, 2)
    finally:
        adf.close()


def adf_block_device_read_only_write_test(tmp_path):
    path = tmp_path / "floppy.adf"
    adf = ADFBlockDevice(str(path))
    adf.create()
    adf.close()

    adf = ADFBlockDevice(str(path), read_only=True)
    adf.open()
    try:
        assert len(adf.read_block(0, 2)) == 1024
        with pytest.raises(IOError):
            adf.write_block(0, b"\0" * 512, 1)
    finally:
        adf.close()


def hdf_block_device_multi_block_test(tmp_path):
    path = tmp_path / "disk.hdf"
    geo = DiskGeometry(2, 2, 11)
    hdf = HDFBlockDevice(str(path))
    hdf.create(geo)
    try:
        assert hdf.block_bytes == 512
        assert hdf.num_blocks == geo.get_num_blocks()
        assert len(hdf.read_block(0)) == 512
        assert hdf.read_block(1, 2) == hdf.read_block(1) + hdf.read_block(2)
        payload = bytes(range(256)) * 2 * 2
        hdf.write_block(3, payload, 2)
        assert hdf.read_block(3, 2) == payload
        # a range past the end is rejected instead of short-reading
        with pytest.raises(IOError):
            hdf.read_block(hdf.num_blocks - 1, 2)
        with pytest.raises(IOError):
            hdf.write_block(0, b"\0" * 512, 2)
    finally:
        hdf.close()


def image_file_multi_block_bounds_test(tmp_path):
    path = tmp_path / "image.hdf"
    path.write_bytes(b"a" * 2048)
    image = ImageFile(str(path))
    image.open()
    try:
        assert image.num_blocks == 4
        assert image.read_blk(1, 3) == b"a" * 1536
        # a multi-block access must stay within the image
        with pytest.raises(IOError):
            image.read_blk(2, 3)
        with pytest.raises(IOError):
            image.write_blk(2, b"a" * 512, 3)
    finally:
        image.close()


def blkdev_factory_create_adf_hd_test(tmp_path):
    # ``type=adf_hd`` creates a 1760 KiB / 22-sector HD floppy (step 27e)
    path = tmp_path / "hd.adf"
    blkdev = BlkDevFactory().create(str(path), options={"type": "adf_hd"})
    try:
        assert isinstance(blkdev, ADFBlockDevice)
        assert blkdev.hd is True
        assert blkdev.sectors == 22
        assert blkdev.num_blocks == 80 * 2 * 22
    finally:
        blkdev.close()
    assert path.stat().st_size == 80 * 2 * 22 * 512

    # reopening detects the HD floppy from its size
    blkdev = BlkDevFactory().open(str(path))
    try:
        assert blkdev.hd is True
        assert blkdev.sectors == 22
    finally:
        blkdev.close()

    # without a type a DD floppy is still the default
    dd = tmp_path / "dd.adf"
    blkdev = BlkDevFactory().create(str(dd))
    try:
        assert blkdev.hd is False
        assert blkdev.sectors == 11
        assert blkdev.num_blocks == 80 * 2 * 11
    finally:
        blkdev.close()
    assert dd.stat().st_size == 80 * 2 * 11 * 512
