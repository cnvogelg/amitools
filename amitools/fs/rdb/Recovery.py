from amitools.fs.block.rdb.RDBlock import *
from .FileSystem import FileSystem
from .Partition import Partition

class Recovery:
    def __init__(self, rawblk, block_bytes, cyl_blks, reserved_cyls):
        self.rawblk = rawblk
        self.max_blks = cyl_blks * reserved_cyls
        self.block_bytes = block_bytes
        self.cyl_blks = cyl_blks
        self.pnum = 0
        self.fnum = 0

    def get_block_map(self):
        res = []
        for i in range(self.max_blks):
            blk = self.try_block_read(i)
            res.append(blk)
        return res

    def try_block_read(self, i):
        p = Partition(self.rawblk, i, self.pnum, self.cyl_blks, self.block_bytes)
        if p.read():
            return BlockRecord(p, [i], p.get_next_partition_blk())
        f = FileSystem(self.rawblk, i, self.fnum)
        if f.read():
            return BlockRecord(f, f.get_blk_nums(), f.get_next_fs_blk())
        r = RDBlock(self.rawblk, i)
        if r.read():
            return BlockRecord(r, [i], Block.no_blk)
        return BlockRecord(None, [i], Block.no_blk)

class BlockRecord:
    def __init__(self, block, blocks, next):
        self.block = block
        self.blocks = blocks
        self.next = next
