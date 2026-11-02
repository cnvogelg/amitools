from types import SimpleNamespace

from amitools.fs.rdb.Partition import Partition
from amitools.fs.rdb.RDisk import RDisk


def fs_rdb_partition_uses_partition_geometry_test():
    rdisk = SimpleNamespace(block_bytes=512)
    part = Partition(None, 0, 0, 1, rdisk)
    part.part_blk = SimpleNamespace(
        dos_env=SimpleNamespace(
            low_cyl=0,
            high_cyl=3,
            surfaces=256,
            blk_per_trk=1,
            dos_type=0x444F5301,
            boot_pri=0,
        ),
        drv_name="DH0",
        flags=0,
    )

    assert part.get_num_cyls() == 4
    assert part.get_num_blocks() == 1024
    assert part.get_num_bytes() == 1024 * 512


def fs_rdb_info_uses_physical_total_for_partition_ratio_test():
    seen = {}

    class DummyPart:
        def get_info(self, total_blks):
            seen["total_blks"] = total_blks
            return "partition"

        def get_extra_infos(self):
            return []

    rdisk = RDisk(None)
    rdisk.block_bytes = 512
    rdisk.max_blks = 4
    rdisk.rdb = SimpleNamespace(
        block_size=512,
        phy_drv=SimpleNamespace(cyls=1024, heads=16, secs=63),
        log_drv=SimpleNamespace(
            lo_cyl=0,
            hi_cyl=1023,
            cyl_blks=1,
            rdb_blk_lo=0,
            rdb_blk_hi=3,
            high_rdsk_blk=3,
        ),
    )
    rdisk.parts = [DummyPart()]
    rdisk.fs = []

    info = rdisk.get_info()

    assert info[-1] == "partition"
    assert seen["total_blks"] == 1024 * 16 * 63


# ----- lists that link back on themselves -----


def _rdb_image(tmp_path):
    """An RDB with one partition and a filesystem of three LSEG blocks.

    Returns the open device and the block numbers of the partition block,
    the filesystem header and the LSEG blocks.
    """
    from amitools.fs.FSString import FSString
    from amitools.fs.blkdev.DiskGeometry import DiskGeometry
    from amitools.fs.blkdev.RawBlockDevice import RawBlockDevice
    import amitools.fs.DosType as DosType

    raw = RawBlockDevice(str(tmp_path / "loop.hdf"), read_only=False, block_bytes=512)
    raw.create(160)
    rdisk = RDisk(raw)
    rdisk.create(DiskGeometry(10, 1, 16), rdb_cyls=1)
    assert rdisk.add_partition(FSString("DH0"), (1, 4))
    assert rdisk.add_filesystem(bytes(range(256)) * 5, dos_type=DosType.DOS3)
    blocks = (
        rdisk.parts[0].part_blk.blk_num,
        rdisk.fs[0].fshd.blk_num,
        [ls.blk_num for ls in rdisk.fs[0].lsegs],
    )
    rdisk.close()
    raw.flush()
    return raw, blocks


def fs_rdb_open_reads_the_lists_test(tmp_path):
    raw, (part_blk, fshd_blk, lseg_blks) = _rdb_image(tmp_path)
    try:
        rdisk = RDisk(raw)
        assert rdisk.open()
        assert [p.part_blk.blk_num for p in rdisk.parts] == [part_blk]
        assert [fs.fshd.blk_num for fs in rdisk.fs] == [fshd_blk]
        assert len(lseg_blks) == 3
        assert rdisk.fs[0].get_blk_nums() == [fshd_blk] + lseg_blks
    finally:
        raw.close()


def fs_rdb_open_stops_at_a_looping_lseg_chain_test(tmp_path):
    from amitools.fs.block.rdb.LoadSegBlock import LoadSegBlock

    raw, (_, _, lseg_blks) = _rdb_image(tmp_path)
    try:
        # the last LSEG block links back to the first
        ls = LoadSegBlock(raw, lseg_blks[-1])
        assert ls.read()
        ls.next = lseg_blks[0]
        ls.write()
        assert not RDisk(raw).open()
    finally:
        raw.close()


def fs_rdb_open_stops_at_a_looping_filesystem_list_test(tmp_path):
    from amitools.fs.block.rdb.FSHeaderBlock import FSHeaderBlock

    raw, (_, fshd_blk, _) = _rdb_image(tmp_path)
    try:
        fshd = FSHeaderBlock(raw, fshd_blk)
        assert fshd.read()
        fshd.next = fshd_blk
        fshd.write()
        assert not RDisk(raw).open()
    finally:
        raw.close()


def fs_rdb_open_stops_at_a_looping_partition_list_test(tmp_path):
    from amitools.fs.block.rdb.PartitionBlock import PartitionBlock

    raw, (part_blk, _, _) = _rdb_image(tmp_path)
    try:
        pb = PartitionBlock(raw, part_blk)
        assert pb.read()
        pb.next = part_blk
        pb.write()
        assert not RDisk(raw).open()
    finally:
        raw.close()
