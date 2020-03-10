from .Block import Block


class BitmapBlock(Block):
    def __init__(self, blkdev, blk_num):
        Block.__init__(self, blkdev, blk_num, chk_loc=0)

    def set(self, data):
        self._set_data(data)
        self._read()

    def create(self):
        self._create_data()

    def read(self):
        self._read_data()
        self._read()

    def _read(self):
        Block.read(self)
        if not self.valid:
            return False
        self.valid = True
        return True

    def get_bitmap_data(self):
        return self.data[4:]

    def set_bitmap_data(self, data):
        self.data[4:] = data

    def dump(self):
        Block.dump(self, "Bitmap")
