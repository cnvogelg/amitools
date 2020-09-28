from .Block import Block


class FileDataBlock(Block):
    def __init__(self, blkdev, blk_num):
        Block.__init__(self, blkdev, blk_num, is_type=Block.T_DATA)

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

        # FileData fields
        self.hdr_key = self._get_long(1)
        self.seq_num = self._get_long(2)
        self.data_size = self._get_long(3)
        self.next_data = self._get_long(4)

        self.valid = True
        return self.valid

    def create(self, hdr_key, seq_num, data, next_data):
        Block.create(self)
        self.hdr_key = hdr_key
        self.seq_num = seq_num
        self.data_size = len(data)
        self.next_data = next_data
        self.contents = data

    def write(self):
        Block._create_data(self)
        self._put_long(1, self.hdr_key)
        self._put_long(2, self.seq_num)
        self._put_long(3, self.data_size)
        self._put_long(4, self.next_data)
        if self.contents != None:
            self.data[24 : 24 + self.data_size] = self.contents
        Block.write(self)

    def get_block_data(self):
        return self.data[24 : 24 + self.data_size]

    def dump(self):
        Block.dump(self, "FileData")
        print(" hdr_key:    %d" % self.hdr_key)
        print(" seq_num:    %d" % self.seq_num)
        print(" data size:  %d" % self.data_size)
        print(" next_data:  %d" % self.next_data)
