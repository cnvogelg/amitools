from .BlockDevice import BlockDevice
from .ImageFile import ImageFile


class RawBlockDevice(BlockDevice):
    def __init__(self, raw_file, read_only=False, block_bytes=512, fobj=None):
        self.img_file = ImageFile(raw_file, read_only, block_bytes, fobj)

    def create(self, num_blocks):
        self.img_file.create(num_blocks)
        self.open()

    def resize(self, new_blocks):
        self.img_file.resize(new_blocks)
        self.open()

    def open(self):
        self.img_file.open()
        # calc block longs
        self.block_bytes = self.img_file.block_bytes
        self.block_longs = self.block_bytes // 4
        self.num_blocks = self.img_file.num_blocks

    def flush(self):
        self.img_file.flush()

    def close(self):
        self.img_file.close()

    def read_block(self, blk_num, num_blks=1):
        return self.img_file.read_blk(blk_num, num_blks)

    def write_block(self, blk_num, data, num_blks=1):
        self.img_file.write_blk(blk_num, data, num_blks)
