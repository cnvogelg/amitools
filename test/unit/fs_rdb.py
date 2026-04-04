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
            dos_type=0x444f5301,
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
