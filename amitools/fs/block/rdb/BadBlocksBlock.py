from ..Block import Block


class BadBlockBlock(Block):
    def __init__(self, blkdev, blk_num=0):
        Block.__init__(self, blkdev, blk_num, chk_loc=2, is_type=Block.BADB)

    def create(self, block_pairs, host_id, size=128, next=0):
        Block.create(self)
        self.size = size
        self.host_id = host_id
        self.next = next
        self.block_pairs = block_pairs

    def write(self):
        self._create_data()

        self._put_long(1, self.size)
        self._put_long(3, self.host_id)
        self._put_long(4, self.next)

        # block_pairs: bad, good, bad, good ...
        off = 6
        for b in self.block_pairs:
            self._put_long(off, b)
            off += 1

        Block.write(self)

    def read(self):
        Block.read(self)
        if not self.valid:
            return False

        self.size = self._get_long(1)
        self.host_id = self._get_long(3)
        self.next = self._get_long(4)

        self.block_pairs = []
        off = 6
        while off < self.block_longs:
            b = self._get_long(off)
            if b == 0 or b == 0xFFFFFFFF:
                break
            self.block_pairs.append(b)

        return self.valid

    def dump(self):
        Block.dump(self, "RDBlock")

        print(" size:           %d" % self.size)
        print(" host_id:        %d" % self.host_id)
        print(" next:           %s" % self._dump_ptr(self.next))
        n = len(self.block_pairs) // 2
        o = 0
        for i in range(n):
            print(" bad=%d good=%d" % (self.block_pairs[o], self.block_pairs[o + 1]))
            o += 2
