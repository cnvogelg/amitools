from amitools.fs.blkdev.RawBlockDevice import RawBlockDevice
from amitools.fs.block.rdb.PartitionBlock import PartitionBlock
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
