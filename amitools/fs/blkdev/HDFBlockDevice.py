from .BlockDevice import BlockDevice
from .ImageFile import ImageFile


class HDFBlockDevice(BlockDevice):
    def __init__(self, hdf_file, read_only=False, block_size=512, fobj=None):
        self.img_file = ImageFile(hdf_file, read_only, block_size, fobj)

    def create(self, geo, reserved=2):
        self._set_geometry(
            geo.cyls,
            geo.heads,
            geo.secs,
            reserved=reserved,
            block_bytes=self.img_file.block_bytes,
        )
        self.img_file.create(geo.get_num_blocks())
        self.img_file.open()

    def open(self, geo, reserved=2):
        self._set_geometry(
            geo.cyls,
            geo.heads,
            geo.secs,
            reserved=reserved,
            block_bytes=self.img_file.block_bytes,
        )
        self.img_file.open()

    def flush(self):
        pass

    def close(self):
        self.img_file.close()

    def read_block(self, blk_num):
        return self.img_file.read_blk(blk_num)

    def write_block(self, blk_num, data):
        return self.img_file.write_blk(blk_num, data)
