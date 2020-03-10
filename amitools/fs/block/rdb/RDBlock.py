from ..Block import Block
from amitools.fs.FSString import FSString


class RDBPhysicalDrive:
    def __init__(
        self,
        cyls=0,
        heads=0,
        secs=0,
        interleave=1,
        parking_zone=-1,
        write_pre_comp=-1,
        reduced_write=-1,
        step_rate=3,
    ):
        if parking_zone == -1:
            parking_zone = cyls
        if write_pre_comp == -1:
            write_pre_comp = cyls
        if reduced_write == -1:
            reduced_write = cyls

        self.cyls = cyls
        self.heads = heads
        self.secs = secs
        self.interleave = interleave
        self.parking_zone = parking_zone
        self.write_pre_comp = write_pre_comp
        self.reduced_write = reduced_write
        self.step_rate = step_rate

    def dump(self):
        print("PhysicalDrive")
        print(" cyls:           %d" % self.cyls)
        print(" heads:          %d" % self.heads)
        print(" secs:           %d" % self.secs)
        print(" interleave:     %d" % self.interleave)
        print(" parking_zone:   %d" % self.parking_zone)
        print(" write_pre_comp: %d" % self.write_pre_comp)
        print(" reduced_write:  %d" % self.reduced_write)
        print(" step_rate:      %d" % self.step_rate)

    def read(self, blk):
        self.cyls = blk._get_long(16)
        self.secs = blk._get_long(17)
        self.heads = blk._get_long(18)
        self.interleave = blk._get_long(19)
        self.parking_zone = blk._get_long(20)

        self.write_pre_comp = blk._get_long(24)
        self.reduced_write = blk._get_long(25)
        self.step_rate = blk._get_long(26)

    def write(self, blk):
        blk._put_long(16, self.cyls)
        blk._put_long(17, self.secs)
        blk._put_long(18, self.heads)
        blk._put_long(19, self.interleave)
        blk._put_long(20, self.parking_zone)

        blk._put_long(24, self.write_pre_comp)
        blk._put_long(25, self.reduced_write)
        blk._put_long(26, self.step_rate)


class RDBLogicalDrive:
    def __init__(
        self,
        rdb_blk_lo=0,
        rdb_blk_hi=0,
        lo_cyl=0,
        hi_cyl=0,
        cyl_blks=0,
        high_rdsk_blk=0,
        auto_park_secs=0,
    ):
        self.rdb_blk_lo = rdb_blk_lo
        self.rdb_blk_hi = rdb_blk_hi
        self.lo_cyl = lo_cyl
        self.hi_cyl = hi_cyl
        self.cyl_blks = cyl_blks
        self.high_rdsk_blk = high_rdsk_blk
        self.auto_park_secs = auto_park_secs

    def dump(self):
        print("LogicalDrive")
        print(" rdb_blk_lo:     %d" % self.rdb_blk_lo)
        print(" rdb_blk_hi:     %d" % self.rdb_blk_hi)
        print(" lo_cyl:         %d" % self.lo_cyl)
        print(" hi_cyl:         %d" % self.hi_cyl)
        print(" cyl_blks:       %d" % self.cyl_blks)
        print(" high_rdsk_blk:  %d" % self.high_rdsk_blk)
        print(" auto_park_secs: %d" % self.auto_park_secs)

    def read(self, blk):
        self.rdb_blk_lo = blk._get_long(32)
        self.rdb_blk_hi = blk._get_long(33)
        self.lo_cyl = blk._get_long(34)
        self.hi_cyl = blk._get_long(35)
        self.cyl_blks = blk._get_long(36)
        self.auto_park_secs = blk._get_long(37)
        self.high_rdsk_blk = blk._get_long(38)

    def write(self, blk):
        blk._put_long(32, self.rdb_blk_lo)
        blk._put_long(33, self.rdb_blk_hi)
        blk._put_long(34, self.lo_cyl)
        blk._put_long(35, self.hi_cyl)
        blk._put_long(36, self.cyl_blks)
        blk._put_long(37, self.auto_park_secs)
        blk._put_long(38, self.high_rdsk_blk)


class RDBDriveID:
    def __init__(
        self,
        disk_vendor="",
        disk_product="",
        disk_revision="",
        ctrl_vendor="",
        ctrl_product="",
        ctrl_revision="",
    ):
        self.disk_vendor = FSString(disk_vendor)
        self.disk_product = FSString(disk_product)
        self.disk_revision = FSString(disk_revision)
        self.ctrl_vendor = FSString(ctrl_vendor)
        self.ctrl_product = FSString(ctrl_product)
        self.ctrl_revision = FSString(ctrl_revision)

    def dump(self):
        print("DriveID")
        print(" disk_vendor:    '%s'" % self.disk_vendor)
        print(" disk_product:   '%s'" % self.disk_product)
        print(" disk_revision:  '%s'" % self.disk_revision)
        print(" ctrl_vendor:    '%s'" % self.ctrl_vendor)
        print(" ctrl_product:   '%s'" % self.ctrl_product)
        print(" ctrl_revision:  '%s'" % self.ctrl_revision)

    def read(self, blk):
        self.disk_vendor = blk._get_cstr(40, 8)
        self.disk_product = blk._get_cstr(42, 16)
        self.disk_revision = blk._get_cstr(46, 4)
        self.ctrl_vendor = blk._get_cstr(47, 8)
        self.ctrl_product = blk._get_cstr(49, 16)
        self.ctrl_revision = blk._get_cstr(53, 4)

    def write(self, blk):
        blk._put_cstr(40, 8, self.disk_vendor)
        blk._put_cstr(42, 16, self.disk_product)
        blk._put_cstr(46, 4, self.disk_revision)
        blk._put_cstr(47, 8, self.ctrl_vendor)
        blk._put_cstr(49, 16, self.ctrl_product)
        blk._put_cstr(53, 4, self.ctrl_revision)


class RDBlock(Block):
    def __init__(self, blkdev, blk_num=0):
        Block.__init__(self, blkdev, blk_num, chk_loc=2, is_type=Block.RDSK)

    def create(
        self,
        phy_drv,
        log_drv,
        drv_id,
        host_id=7,
        block_size=512,
        flags=0x17,
        badblk_list=Block.no_blk,
        part_list=Block.no_blk,
        fs_list=Block.no_blk,
        init_code=Block.no_blk,
        size=64,
    ):
        Block.create(self)
        self.size = size
        self.host_id = host_id
        self.block_size = block_size
        self.flags = flags

        self.badblk_list = badblk_list
        self.part_list = part_list
        self.fs_list = fs_list
        self.init_code = init_code

        self.phy_drv = phy_drv
        self.log_drv = log_drv
        self.drv_id = drv_id
        self.valid = True

    def write(self):
        self._create_data()

        self._put_long(1, self.size)
        self._put_long(3, self.host_id)
        self._put_long(4, self.block_size)
        self._put_long(5, self.flags)

        self._put_long(6, self.badblk_list)
        self._put_long(7, self.part_list)
        self._put_long(8, self.fs_list)
        self._put_long(9, self.init_code)

        self.phy_drv.write(self)
        self.log_drv.write(self)
        self.drv_id.write(self)

        Block.write(self)

    def read(self):
        Block.read(self)
        if not self.valid:
            return False

        self.size = self._get_long(1)
        self.host_id = self._get_long(3)
        self.block_size = self._get_long(4)
        self.flags = self._get_long(5)

        self.badblk_list = self._get_long(6)
        self.part_list = self._get_long(7)
        self.fs_list = self._get_long(8)
        self.init_code = self._get_long(9)

        self.phy_drv = RDBPhysicalDrive()
        self.phy_drv.read(self)
        self.log_drv = RDBLogicalDrive()
        self.log_drv.read(self)
        self.drv_id = RDBDriveID()
        self.drv_id.read(self)

        return self.valid

    def dump(self):
        Block.dump(self, "RigidDisk")

        print(" size:           %d" % self.size)
        print(" host_id:        %d" % self.host_id)
        print(" block_size:     %d" % self.block_size)
        print(" flags:          0x%08x" % self.flags)
        print(" badblk_list:    %s" % self._dump_ptr(self.badblk_list))
        print(" part_list:      %s" % self._dump_ptr(self.part_list))
        print(" fs_list:        %s" % self._dump_ptr(self.fs_list))
        print(" init_code:      %s" % self._dump_ptr(self.init_code))

        self.phy_drv.dump()
        self.log_drv.dump()
        self.drv_id.dump()
