from .BlockDevice import BlockDevice


class PartBlockDevice(BlockDevice):
    def __init__(self, raw_blkdev, part_blk, auto_close=False):
        self.raw_blkdev = raw_blkdev
        self.part_blk = part_blk
        self.blk_off = 0
        self.sec_per_blk = 1
        self.auto_close = auto_close

    def open(self):
        # extract geometry from partition block
        dos_env = self.part_blk.dos_env
        # from dos env: num cylinders
        lo_cyl = dos_env.low_cyl
        hi_cyl = dos_env.high_cyl
        cyls = hi_cyl - lo_cyl + 1
        # heads and secs
        heads = dos_env.surfaces
        secs = dos_env.blk_per_trk
        block_bytes = dos_env.block_size * 4
        # calc block offset of partition
        self.blk_off = heads * secs * lo_cyl
        # adjust block size and reduce secs
        self.sec_per_blk = dos_env.sec_per_blk
        secs //= self.sec_per_blk
        block_bytes *= self.sec_per_blk
        # extra blocks
        reserved = dos_env.reserved
        boot_blocks = dos_env.boot_blocks
        if boot_blocks == 0:
            boot_blocks = 2
        self._set_geometry(cyls, heads, secs, block_bytes, reserved, boot_blocks)
        return True

    def flush(self):
        self.raw_blkdev.flush()

    def close(self):
        # auto close containing rdisk
        if self.auto_close:
            self.raw_blkdev.close()

    def read_block(self, blk_num):
        if blk_num >= self.num_blocks:
            raise ValueError(
                "Invalid Part block num: got %d but max is %d"
                % (blk_num, self.num_blocks)
            )
        num_blks = self.sec_per_blk
        off = self.blk_off + (blk_num * num_blks)
        return self.raw_blkdev.read_block(off, num_blks=num_blks)

    def write_block(self, blk_num, data):
        if blk_num >= self.num_blocks:
            raise ValueError(
                "Invalid Part block num: got %d but max is %d"
                % (blk_num, self.num_blocks)
            )
        if len(data) != self.block_bytes:
            raise ValueError(
                "Invalid Part block size written: got %d but size is %d"
                % (len(data), self.block_bytes)
            )
        num_blks = self.sec_per_blk
        off = self.blk_off + (blk_num * num_blks)
        self.raw_blkdev.write_block(off, data, num_blks=num_blks)
