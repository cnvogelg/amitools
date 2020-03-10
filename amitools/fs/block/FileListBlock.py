from .Block import Block


class FileListBlock(Block):
    def __init__(self, blkdev, blk_num):
        Block.__init__(
            self, blkdev, blk_num, is_type=Block.T_LIST, is_sub_type=Block.ST_FILE
        )

    def set(self, data):
        self._set_data(data)
        self._read()

    def read(self):
        self._read_data()
        self._read()

    def _read(self):
        Block.read(self)
        if not self.valid:
            return False

        # FileList fields
        self.own_key = self._get_long(1)
        self.block_count = self._get_long(2)

        # read (limited) data blocks
        bc = self.block_count
        mbc = self.blkdev.block_longs - 56
        if bc > mbc:
            bc = mbc
        self.data_blocks = []
        for i in range(bc):
            self.data_blocks.append(self._get_long(-51 - i))

        self.parent = self._get_long(-3)
        self.extension = self._get_long(-2)

        self.valid = self.own_key == self.blk_num
        return self.valid

    def create(self, parent, data_blocks, extension):
        Block.create(self)
        self.own_key = self.blk_num
        self.block_count = len(data_blocks)
        self.data_blocks = data_blocks
        self.parent = parent
        self.extension = extension
        self.valid = True
        return True

    def write(self):
        Block._create_data(self)
        self._put_long(1, self.own_key)
        self._put_long(2, self.block_count)

        # data blocks
        for i in range(len(self.data_blocks)):
            self._put_long(-51 - i, self.data_blocks[i])

        self._put_long(-3, self.parent)
        self._put_long(-2, self.extension)
        Block.write(self)

    def dump(self):
        Block.dump(self, "FileList")
        print(" own_key:    %d" % self.own_key)
        print(" blk_cnt:    %d" % self.block_count)
        print(" data blks:  %s" % self.data_blocks)
        print(" parent:     %d" % self.parent)
        print(" extension:  %d" % self.extension)
