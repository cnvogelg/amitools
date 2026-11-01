import pytest

from amitools.fs.blkdev.RawBlockDevice import RawBlockDevice
from amitools.fs.block.rdb.PartitionBlock import PartitionBlock
from amitools.fs.rdb.FileSystem import FileSystem
from amitools.fs.FSString import FSString


def create_part_blkdev(path):
    blkdev = RawBlockDevice(str(path))
    blkdev.create(1)
    pb = PartitionBlock(blkdev, 0)
    pb.create(FSString("DH0"), None)
    pb.write()
    return blkdev


def fs_rdb_block_part_roundtrip_test(tmp_path):
    blkdev = create_part_blkdev(tmp_path / "part.img")
    pb = PartitionBlock(blkdev, 0)
    assert pb.read()
    assert pb.size == 64
    assert pb.drv_name == FSString("DH0")
    blkdev.close()


def fs_rdb_block_chksum_ignores_unsummed_longs_test(tmp_path):
    # RDB block checksums only cover the first SummedLongs longs.
    # Data beyond them (e.g. left over by other tools) must be ignored.
    blkdev = create_part_blkdev(tmp_path / "part.img")
    data = bytearray(blkdev.read_block(0))
    data[64 * 4 :] = b"\xa5" * (len(data) - 64 * 4)
    blkdev.write_block(0, bytes(data))
    pb = PartitionBlock(blkdev, 0)
    assert pb.read()
    assert pb.valid_chksum
    blkdev.close()


@pytest.mark.parametrize("payload_size", [1001, 1002, 1003])
def fs_rdb_block_loadseg_misaligned_data_test(tmp_path, payload_size):
    blkdev = RawBlockDevice(str(tmp_path / "loadseg.img"))
    blkdev.create(4)
    try:
        payload = bytes((i % 251) + 1 for i in range(payload_size))
        fs = FileSystem(blkdev, 0, 0)
        fs.create(
            [1, 2, 3],
            payload,
            version=0x00010000,
            dos_type=0x444F5307,
        )
        fs.write()

        loaded_fs = FileSystem(blkdev, 0, 0)
        assert loaded_fs.read()
        padding = (-len(payload)) % 4
        assert loaded_fs.get_data() == payload + b"\0" * padding
        assert [lseg.size for lseg in loaded_fs.lsegs] == [128, 128, 10]
        assert all(lseg.valid_chksum for lseg in loaded_fs.lsegs)
    finally:
        blkdev.close()
