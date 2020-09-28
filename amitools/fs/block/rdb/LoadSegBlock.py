from ..Block import Block


class LoadSegBlock(Block):
    def __init__(self, blkdev, blk_num=0):
        Block.__init__(self, blkdev, blk_num, chk_loc=2, is_type=Block.LSEG)

    def create(self, host_id=0, next=Block.no_blk, size=128):
        Block.create(self)
        self.size = size
        self.host_id = host_id
        self.next = next

    def write(self):
        if self.data == None:
            self._create_data()

        self._put_long(1, self.size)
        self._put_long(3, self.host_id)
        self._put_long(4, self.next)

        Block.write(self)

    def set_data(self, data):
        if self.data == None:
            self._create_data()
        self.data[20 : 20 + len(data)] = data
        self.size = (20 + len(data)) // 4

    def get_data(self):
        return self.data[20 : 20 + (self.size - 5) * 4]

    def read(self):
        Block.read(self)
        if not self.valid:
            return False

        self.size = self._get_long(1)
        self.host_id = self._get_long(3)
        self.next = self._get_long(4)

        return self.valid

    def dump(self):
        Block.dump(self, "RDBlock")

        print(" size:           %d" % self.size)
        print(" host_id:        %d" % self.host_id)
        print(" next:           %s" % self._dump_ptr(self.next))
