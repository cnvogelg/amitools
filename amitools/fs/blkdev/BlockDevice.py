# a block device defines a set of blocks used by a file system
from .DiskGeometry import DiskGeometry


class BlockDevice:
    def _set_geometry(
        self, cyls=80, heads=2, sectors=11, block_bytes=512, reserved=2, bootblocks=2
    ):
        self.cyls = cyls
        self.heads = heads
        self.sectors = sectors
        self.block_bytes = block_bytes
        self.reserved = reserved
        self.bootblocks = bootblocks
        # derived values
        self.num_tracks = self.cyls * self.heads
        self.num_blocks = self.num_tracks * self.sectors
        self.num_bytes = self.num_blocks * self.block_bytes
        self.block_longs = self.block_bytes // 4
        self.num_longs = self.num_blocks * self.block_longs

    def dump(self):
        print("cylinders:  ", self.cyls)
        print("heads:      ", self.heads)
        print("sectors:    ", self.sectors)
        print("block_bytes:", self.block_bytes)
        print("reserved:   ", self.reserved)
        print("bootblocks: ", self.bootblocks)

    def _blk_to_offset(self, blk_num):
        return self.block_bytes * blk_num

    # ----- API -----
    def create(self, **args):
        pass

    def open(self):
        pass

    def close(self):
        pass

    def flush(self):
        pass

    def read_block(self, blk_num):
        pass

    def write_block(self, blk_num, data):
        pass

    def get_geometry(self):
        return DiskGeometry(self.cyls, self.heads, self.sectors)

    def get_chs_str(self):
        return "chs=%d,%d,%d" % (self.cyls, self.heads, self.sectors)

    def get_options(self):
        return {
            "chs": "%d,%d,%d" % (self.cyls, self.heads, self.sectors),
            "bs": self.block_bytes,
        }

    def get_block_size_str(self):
        return "bs=%d" % self.block_bytes
