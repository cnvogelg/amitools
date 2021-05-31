from amitools.fs.block.rdb.RDBlock import *
from amitools.fs.block.rdb.PartitionBlock import *
import amitools.util.ByteSize as ByteSize
import amitools.fs.DosType as DosType
from .FileSystem import FileSystem
from .Partition import Partition


class RDisk:
    def __init__(self, rawblk):
        self.rawblk = rawblk
        self.valid = False
        self.rdb = None
        self.parts = []
        self.fs = []
        self.used_blks = []
        self.max_blks = 0
        self.block_bytes = 0

    def peek_block_size(self):
        self.rdb = RDBlock(self.rawblk)
        if not self.rdb.read():
            self.valid = False
            return None
        return self.rdb.block_size

    def open(self):
        # read RDB
        if not self.rdb:
            self.rdb = RDBlock(self.rawblk)
            if not self.rdb.read():
                self.valid = False
                return False

        # check block size of rdb vs. raw block device
        if self.rdb.block_size != self.rawblk.block_bytes:
            raise ValueError(
                "block size mismatch: rdb=%d != device=%d"
                % (self.rdb.block_size, self.rawblk.block_bytes)
            )
        self.block_bytes = self.rdb.block_size

        # create used block list
        self.used_blks = [self.rdb.blk_num]

        # read partitions
        part_blk = self.rdb.part_list
        self.parts = []
        num = 0
        while part_blk != Block.no_blk:
            p = Partition(self.rawblk, part_blk, num, self.rdb.log_drv.cyl_blks, self)
            num += 1
            if not p.read():
                self.valid = False
                return False
            self.parts.append(p)
            # store used block
            self.used_blks.append(p.get_blk_num())
            # next partition
            part_blk = p.get_next_partition_blk()

        # read filesystems
        fs_blk = self.rdb.fs_list
        self.fs = []
        num = 0
        while fs_blk != PartitionBlock.no_blk:
            fs = FileSystem(self.rawblk, fs_blk, num)
            num += 1
            if not fs.read():
                self.valid = False
                return False
            self.fs.append(fs)
            # store used blocks
            self.used_blks += fs.get_blk_nums()
            # next partition
            fs_blk = fs.get_next_fs_blk()

        # TODO: add bad block blocks

        self.valid = True
        self.max_blks = self.rdb.log_drv.rdb_blk_hi + 1
        return True

    def close(self):
        self.rdb = None
        self.valid = False

    # ----- query -----

    def dump(self, hex_dump=False):
        # rdb
        if self.rdb != None:
            self.rdb.dump()
        # partitions
        for p in self.parts:
            p.dump()
        # fs
        for fs in self.fs:
            fs.dump(hex_dump)

    def get_info(self, part_name=None):
        res = []
        part = None
        # only show single partition
        if part_name:
            part = self.find_partition_by_string(part_name)
            if not part:
                res.append("Partition not found: %s!" % part_name)
                return res
        # physical disk info
        if part:
            logic_blks = self.get_logical_blocks()
            res.append(part.get_info(logic_blks))
            extra = part.get_extra_infos()
            for e in extra:
                res.append("%s%s" % (" " * 70, e))
        else:
            pd = self.rdb.phy_drv
            total_blks = self.get_total_blocks()
            total_bytes = self.get_total_bytes()
            bs = self.rdb.block_size
            extra = "heads=%d sectors=%d block_size=%d" % (pd.heads, pd.secs, bs)
            res.append(
                "PhysicalDisk:        %8d %8d  %10d  %s  %s"
                % (
                    0,
                    pd.cyls - 1,
                    total_blks,
                    ByteSize.to_byte_size_str(total_bytes),
                    extra,
                )
            )
            # logical disk info
            ld = self.rdb.log_drv
            extra = "rdb_blks=[%d:%d,#%d] used=[hi=%d,#%d] cyl_blks=%d" % (
                ld.rdb_blk_lo,
                ld.rdb_blk_hi,
                self.max_blks,
                ld.high_rdsk_blk,
                len(self.used_blks),
                ld.cyl_blks,
            )
            logic_blks = self.get_logical_blocks()
            logic_bytes = self.get_logical_bytes()
            res.append(
                "LogicalDisk:         %8d %8d  %10d  %s  %s"
                % (
                    ld.lo_cyl,
                    ld.hi_cyl,
                    logic_blks,
                    ByteSize.to_byte_size_str(logic_bytes),
                    extra,
                )
            )
            # add partitions
            for p in self.parts:
                res.append(p.get_info(logic_blks))
                extra = p.get_extra_infos()
                for e in extra:
                    res.append("%s%s" % (" " * 70, e))
            # add fileystems
            for f in self.fs:
                res.append(f.get_info())
        return res

    def get_block_map(self):
        res = []
        for i in range(self.max_blks):
            blk = None
            # check partitions
            if i == 0:
                blk = "RD"
            else:
                for p in self.parts:
                    if i == p.get_blk_num():
                        blk = "P%d" % p.num
                        break
                if blk == None:
                    # check file systems
                    for f in self.fs:
                        if i in f.get_blk_nums():
                            blk = "F%d" % f.num
                            break
                if blk == None:
                    blk = "--"
            res.append(blk)
        return res

    def get_logical_cylinders(self):
        ld = self.rdb.log_drv
        return ld.hi_cyl - ld.lo_cyl + 1

    def get_logical_blocks(self):
        ld = self.rdb.log_drv
        cyls = ld.hi_cyl - ld.lo_cyl + 1
        return cyls * ld.cyl_blks

    def get_logical_bytes(self):
        return self.get_logical_blocks() * self.block_bytes

    def get_cyls_heads_secs(self):
        pd = self.rdb.phy_drv
        return pd.cyls, pd.heads, pd.secs

    def get_total_blocks(self):
        pd = self.rdb.phy_drv
        return pd.cyls * pd.heads * pd.secs

    def get_total_bytes(self):
        return self.get_total_blocks() * self.block_bytes

    def get_cylinder_blocks(self):
        ld = self.rdb.log_drv
        return ld.cyl_blks

    def get_cylinder_bytes(self):
        return self.get_cylinder_blocks() * self.block_bytes

    def get_num_partitions(self):
        return len(self.parts)

    def get_partition(self, num):
        if num < len(self.parts):
            return self.parts[num]
        else:
            return None

    def find_partition_by_drive_name(self, name):
        lo_name = name.lower()
        num = 0
        for p in self.parts:
            drv_name = p.get_drive_name().get_unicode().lower()
            if drv_name == lo_name:
                return p
        return None

    def find_partition_by_string(self, s):
        p = self.find_partition_by_drive_name(s)
        if p != None:
            return p
        # try partition number
        try:
            num = int(s)
            return self.get_partition(num)
        except ValueError:
            return None

    def get_filesystem(self, num):
        if num < len(self.fs):
            return self.fs[num]
        else:
            return None

    def get_used_blocks(self):
        return self.used_blks

    def find_filesystem_by_string(self, s):
        # try filesystem number
        try:
            num = int(s)
            return self.get_filesystem(num)
        except ValueError:
            return None

    # ----- edit -----

    def create(
        self, disk_geo, rdb_cyls=1, hi_rdb_blk=0, disk_names=None, ctrl_names=None
    ):
        cyls = disk_geo.cyls
        heads = disk_geo.heads
        secs = disk_geo.secs
        cyl_blks = heads * secs
        rdb_blk_hi = cyl_blks * rdb_cyls - 1

        if disk_names != None:
            disk_vendor = disk_names[0]
            disk_product = disk_names[1]
            disk_revision = disk_names[2]
        else:
            disk_vendor = "RDBTOOL"
            disk_product = "IMAGE"
            disk_revision = "2012"

        if ctrl_names != None:
            ctrl_vendor = ctrl_names[0]
            ctrl_product = ctrl_names[1]
            ctrl_revision = ctrl_names[2]
        else:
            ctrl_vendor = ""
            ctrl_product = ""
            ctrl_revision = ""

        flags = 0x7
        if disk_names != None:
            flags |= 0x10
        if ctrl_names != None:
            flags |= 0x20

        # create RDB
        phy_drv = RDBPhysicalDrive(cyls, heads, secs)
        log_drv = RDBLogicalDrive(
            rdb_blk_hi=rdb_blk_hi,
            lo_cyl=rdb_cyls,
            hi_cyl=cyls - 1,
            cyl_blks=cyl_blks,
            high_rdsk_blk=hi_rdb_blk,
        )
        drv_id = RDBDriveID(
            disk_vendor,
            disk_product,
            disk_revision,
            ctrl_vendor,
            ctrl_product,
            ctrl_revision,
        )
        self.block_bytes = self.rawblk.block_bytes
        self.rdb = RDBlock(self.rawblk)
        self.rdb.create(
            phy_drv, log_drv, drv_id, block_size=self.block_bytes, flags=flags
        )
        self.rdb.write()

        self.used_blks = [self.rdb.blk_num]
        self.max_blks = self.rdb.log_drv.rdb_blk_hi + 1
        self.valid = True

    def resize(self, new_lo_cyl=None, new_hi_cyl=None, adjust_physical=False):
        # if the rdb region has to be minimized then check if no partition
        # is in the way
        if not new_lo_cyl:
            new_lo_cyl = self.rdb.log_drv.lo_cyl
        if not new_hi_cyl:
            new_hi_cyl = self.rdb.log_drv.hi_cyl
        # same range? silently ignore and return true
        if (
            new_lo_cyl == self.rdb.log_drv.lo_cyl
            and new_hi_cyl == self.rdb.log_drv.hi_cyl
        ):
            return
        # invalid range
        if new_lo_cyl > new_hi_cyl:
            raise ValueError(
                "Invalid cylinder range: %d > %d" % (new_lo_cyl, new_hi_cyl)
            )
        # check partitions
        for p in self.parts:
            (lo, hi) = p.get_cyl_range()
            if lo < new_lo_cyl or hi > new_hi_cyl:
                raise ValueError("Partition %d does not fit in new range!" % p.num)
        # need to adjust phyisical disc?
        if new_hi_cyl != self.rdb.phy_drv.cyls - 1:
            if adjust_physical:
                self.rdb.phy_drv.cyls = new_hi_cyl + 1
            else:
                # not allowed to grow physical disk. abort!
                raise ValueError("Need to adjust physical disk!")
        # adjust logical range
        self.rdb.log_drv.lo_cyl = new_lo_cyl
        self.rdb.log_drv.hi_cyl = new_hi_cyl
        # update block
        self.rdb.write()

    def remap(self, new_heads=None, new_secs=None):
        """Change the RDB structure to use new head and sector values"""
        old_heads = self.rdb.phy_drv.heads
        old_secs = self.rdb.phy_drv.secs
        if not new_heads:
            new_heads = old_heads
        if not new_secs:
            new_secs = old_secs
        # nothing to do?
        if new_heads == old_heads and new_secs == old_secs:
            return
        # validate if remapping is possible
        old_cyl_blocks = old_heads * old_secs
        new_cyl_blocks = new_heads * new_secs
        if old_cyl_blocks > new_cyl_blocks:
            # finer resolution wanted
            # check that factor is integer multiple
            if old_cyl_blocks % new_cyl_blocks != 0:
                raise ValueError("Smaller cylinder blocks are not a multiple!")
            factor = old_cyl_blocks // new_cyl_blocks
            # no further checks required

            # conversion op
            def op(x):
                return x * factor

        else:
            # coarser resolution wanted
            # check that factor is integer multiple
            if new_cyl_blocks & old_cyl_blocks != 0:
                raise ValueError("Larger cylinder blocks are not a multiple!")
            factor = new_cyl_blocks // old_cyl_blocks

            def check(x):
                return x % factor == 0

            # check physical drive range
            pd = self.rdb.phy_drv
            if not check(pd.cyls):
                raise ValueError("Physical Range %d can't be remapped!" % pd.cyls)
            # check logical drive range
            ld = self.rdb.log_drv
            if not check(ld.lo_cyl) or not check(ld.hi_cyl):
                raise ValueError(
                    "Logical Range [%d,%d] can't be remapped!" % (ld.lo_cyl, ld.hi_cyl)
                )
            # check partition lo/hi cyls
            for p in self.parts:
                lo, hi = p.get_cyl_range()
                if not check(lo) or not check(hi):
                    raise ValueError(
                        "Partition %d [%d,%d] can't be remapped!" % (p.num, lo, hi)
                    )

            # conversion op
            def op(x):
                return x // factor

        # new blocks per cylinder
        cyl_blks = new_heads * new_secs
        # process RDB's cyl values with 'op':
        # change physical disk
        pd = self.rdb.phy_drv
        pd.heads = new_heads
        pd.secs = new_secs
        pd.cyls = op(pd.cyls)
        # change logical disk
        ld = self.rdb.log_drv
        ld.lo_cyl = op(ld.lo_cyl)
        ld.hi_cyl = op(ld.hi_cyl)
        ld.cyl_blks = cyl_blks
        # update rdb
        self.rdb.write()
        # change partitions
        for p in self.parts:
            p.cyl_blks = cyl_blks
            de = p.part_blk.dos_env
            de.low_cyl = op(de.low_cyl)
            de.high_cyl = op(de.high_cyl)
            de.blk_per_trk = cyl_blks
            p.part_blk.write()
        # done

    def get_cyl_range(self):
        log_drv = self.rdb.log_drv
        return (log_drv.lo_cyl, log_drv.hi_cyl)

    def check_cyl_range(self, lo_cyl, hi_cyl):
        if lo_cyl > hi_cyl:
            return False
        (lo, hi) = self.get_cyl_range()
        if not (lo_cyl >= lo and hi_cyl <= hi):
            return False
        # check partitions
        for p in self.parts:
            (lo, hi) = p.get_cyl_range()
            if not ((hi_cyl < lo) or (lo_cyl > hi)):
                return False
        return True

    def get_free_cyl_ranges(self):
        lohi = self.get_cyl_range()
        free = [lohi]
        for p in self.parts:
            pr = p.get_cyl_range()
            new_free = []
            for r in free:
                # partition completely fills range
                if pr[0] == r[0] and pr[1] == r[1]:
                    pass
                # partition starts at range
                elif pr[0] == r[0]:
                    n = (pr[1] + 1, r[1])
                    new_free.append(n)
                # partition ends at range
                elif pr[1] == r[1]:
                    n = (r[0], pr[0] - 1)
                    new_free.append(n)
                # partition inside range
                elif pr[0] > r[0] and pr[1] < r[1]:
                    new_free.append((r[0], pr[0] - 1))
                    new_free.append((pr[1] + 1, r[1]))
                else:
                    new_free.append(r)
            free = new_free
        if len(free) == 0:
            return None
        return free

    def find_free_cyl_range_start(self, num_cyls):
        ranges = self.get_free_cyl_ranges()
        if ranges == None:
            return None
        for r in ranges:
            size = r[1] - r[0] + 1
            if num_cyls <= size:
                return r[0]
        return None

    # ----- manage rdb blocks -----

    def _has_free_rdb_blocks(self, num):
        return (len(self.used_blks) + num) <= self.max_blks

    def get_free_blocks(self):
        res = []
        for i in range(self.max_blks):
            if i not in self.used_blks:
                res.append(i)
        return res

    def _alloc_rdb_blocks(self, num):
        free = self.get_free_blocks()
        n = len(free)
        if n == num:
            return free
        elif n > num:
            return free[:num]
        else:
            return None

    def _next_rdb_block(self):
        free = self.get_free_blocks()
        if len(free) > 0:
            return free[0]
        else:
            return None

    def _update_hi_blk(self):
        hi = 0
        for blk_num in self.used_blks:
            if blk_num > hi:
                hi = blk_num
        ld = self.rdb.log_drv
        ld.high_rdsk_blk = hi

    # ----- partition handling -----

    def _adjust_dos_env(self, dos_env, more_dos_env):
        if more_dos_env is None:
            return
        for p in more_dos_env:
            key = p[0]
            if hasattr(dos_env, key):
                setattr(dos_env, key, int(p[1]))

    def add_partition(
        self,
        drv_name,
        cyl_range,
        dev_flags=0,
        flags=0,
        dos_type=DosType.DOS0,
        boot_pri=0,
        more_dos_env=None,
        fs_block_size=None,
    ):
        # cyl range is not free anymore or invalid
        if not self.check_cyl_range(*cyl_range):
            raise ValueError("Partition range is not free!")
        # no space left for partition block
        if not self._has_free_rdb_blocks(1):
            raise ValueError("No space left in RDB for partition block!")
        # allocate block for partition
        blk_num = self._alloc_rdb_blocks(1)[0]
        self.used_blks.append(blk_num)
        self._update_hi_blk()
        # crete a new parttion block
        pb = PartitionBlock(self.rawblk, blk_num)
        # setup fs block size (may be multiple sectors)
        if not fs_block_size:
            fs_block_size = self.block_bytes
        sec_per_blk = int(fs_block_size // self.block_bytes)
        if sec_per_blk < 1 or sec_per_blk > 16:
            raise ValueError("Invalid sec_per_blk: " + sec_per_blk)
        # block size in longs
        bsl = self.block_bytes >> 2
        # setup dos env
        heads = self.rdb.phy_drv.heads
        blk_per_trk = self.rdb.phy_drv.secs
        dos_env = PartitionDosEnv(
            low_cyl=cyl_range[0],
            high_cyl=cyl_range[1],
            surfaces=heads,
            blk_per_trk=blk_per_trk,
            dos_type=dos_type,
            boot_pri=boot_pri,
            block_size=bsl,
            sec_per_blk=sec_per_blk,
        )
        self._adjust_dos_env(dos_env, more_dos_env)
        pb.create(drv_name, dos_env, flags=flags)
        pb.write()
        # link block
        if len(self.parts) == 0:
            # write into RDB
            self.rdb.part_list = blk_num
        else:
            # write into last partition block
            last_pb = self.parts[-1]
            last_pb.part_blk.next = blk_num
            last_pb.write()
        # always write RDB as allocated block is stored there, too
        self.rdb.write()
        # flush out all changes before we read again
        self.rawblk.flush()
        # create partition object and add to partition list
        blk_per_cyl = blk_per_trk * heads
        p = Partition(self.rawblk, blk_num, len(self.parts), blk_per_cyl, self)
        p.read()
        self.parts.append(p)
        return p

    def change_partition(
        self,
        pid,
        drv_name=None,
        dev_flags=None,
        dos_type=None,
        flags=None,
        boot_pri=None,
        more_dos_env=None,
        fs_block_size=None,
    ):
        # partition not found
        if pid < 0 or pid >= len(self.parts):
            return False
        p = self.parts[pid]
        pb = p.part_blk
        if pb == None:
            return False
        # set flags
        dirty = False
        if flags != None:
            pb.flags = flags
            dirty = True
        if drv_name != None:
            pb.drv_name = drv_name
            dirty = True
        if dev_flags != None:
            pb.dev_flags = dev_flags
            dirty = True
        # set dosenv flags
        if dos_type != None:
            pb.dos_env.dos_type = dos_type
            dirty = True
        if boot_pri != None:
            pb.dos_env.boot_pri = boot_pri
            dirty = True
        # change fs block size
        if fs_block_size:
            sec_per_blk = int(fs_block_size // self.block_bytes)
            if sec_per_blk < 1 or sec_per_blk > 16:
                raise ValueError("Invalid sec_per_blk: " + sec_per_blk)
            pb.dos_env.sec_per_blk = sec_per_blk
        # update dos env
        if more_dos_env is not None:
            self._adjust_dos_env(pb.dos_env, more_dos_env)
            dirty = True
        # write change
        if dirty:
            pb.write()
        return True

    def delete_partition(self, pid):
        # partition not found
        if pid < 0 or pid >= len(self.parts):
            return False
        # unlink partition block
        next = Block.no_blk
        if (pid + 1) < len(self.parts):
            next = self.parts[pid + 1].get_blk_num()
        if pid == 0:
            self.rdb.part_list = next
        else:
            last_pb = self.parts[-1]
            last_pb.part_blk.next = next
            last_pb.write()
        # free block
        p = self.parts[pid]
        blk_num = p.get_blk_num()
        self.used_blks.remove(blk_num)
        self._update_hi_blk()
        # write RDB
        self.rdb.write()
        # remove partition instance
        self.parts.remove(p)
        # relabel remaining parts
        num = 0
        for p in self.parts:
            p.num = num
            num += 1
        # done!
        return True

    # ----- file system handling ------

    def add_filesystem(self, data, dos_type=DosType.DOS1, version=0, dev_flags=None):
        # create a file system
        blk_num = self._next_rdb_block()
        fs_num = len(self.fs)
        fs = FileSystem(self.rawblk, blk_num, fs_num)
        # get total number of blocks for fs data
        num_blks = fs.get_total_blocks(data)
        # check if RDB has space left
        if not self._has_free_rdb_blocks(num_blks):
            return False
        # allocate blocks
        blks = self._alloc_rdb_blocks(num_blks)
        self.used_blks += blks
        self._update_hi_blk()
        # create file system
        fs.create(blks[1:], data, version, dos_type, dev_flags)
        fs.write()
        # link fs block
        if len(self.fs) == 0:
            # write into RDB
            self.rdb.fs_list = blk_num
        else:
            # write into last fs block
            last_fs = self.fs[-1]
            last_fs.fshd.next = blk_num
            last_fs.write(only_fshd=True)
        # update rdb: allocated blocks and optional link
        self.rdb.write()
        # add fs to list
        self.fs.append(fs)
        return True

    def delete_filesystem(self, fid):
        # check filesystem id
        if fid < 0 or fid >= len(self.fs):
            return False
        # unlink partition block
        next = Block.no_blk
        if (fid + 1) < len(self.fs):
            next = self.fs[fid + 1].blk_num
        if fid == 0:
            self.rdb.fs_list = next
        else:
            last_fs = self.fs[-1]
            last_fs.fshd.next = next
            last_fs.write()
        # free block
        f = self.fs[fid]
        blks = f.get_blk_nums()
        for b in blks:
            self.used_blks.remove(b)
        self._update_hi_blk()
        # write RDB
        self.rdb.write()
        # remove partition instance
        self.fs.remove(f)
        # relabel remaining parts
        num = 0
        for f in self.fs:
            f.num = num
            num += 1
        # done!
        return True
