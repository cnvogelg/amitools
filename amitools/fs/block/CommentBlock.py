import time
from .Block import Block


class CommentBlock(Block):
    def __init__(self, blkdev, blk_num):
        Block.__init__(self, blkdev, blk_num, is_type=Block.T_COMMENT)
        self.comment = ""

    def create(self, header_key, comment=""):
        Block.create(self)
        self.own_key = self.blk_num
        self.header_key = header_key
        self.comment = comment

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

        # Comment fields
        self.own_key = self._get_long(1)
        self.header_key = self._get_long(2)
        self.checksum = self._get_long(5)
        self.comment = self._get_bstr(6, 79)
        self.valid = self.own_key == self.blk_num
        return self.valid

    def write(self):
        Block._create_data(self)
        self._put_long(1, self.own_key)
        self._put_long(2, self.header_key)
        self._put_bstr(6, 79, self.comment)
        Block.write(self)

    def dump(self):
        Block.dump(self, "Comment")
        print(" own_key:    %d" % (self.own_key))
        print(" header_key: %d" % (self.header_key))
        print(" comment:    '%s'" % self.comment)
