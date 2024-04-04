from amitools.fs.block.rdb.RDBlock import *
from .FileSystem import FileSystem
from .Partition import Partition
from .RDisk import RDisk

class Recovery:
    def __init__(self, rawblk, block_bytes, cyl_blks, reserved_cyls):
        self.rawblk = rawblk
        self.max_blks = cyl_blks * reserved_cyls
        self.block_bytes = block_bytes
        self.cyl_blks = cyl_blks
        self.pnum = 0
        self.fnum = 0

    def read(self):
        res = []
        for i in range(self.max_blks):
            blk = self.try_block_read(i)
            if blk is not None:
                res.append(blk)
        self.block_map = res

    def try_block_read(self, i):
        p = Partition(self.rawblk, i, self.pnum, self.cyl_blks, self.block_bytes)
        if p.read():
            self.pnum += 1
            return p
        f = FileSystem(self.rawblk, i, self.fnum)
        if f.read():
            self.fnum += 1
            return f
        r = RDBlock(self.rawblk, i)
        if r.read():
            return r
        return None

    def dump(self):
        for i in self.block_map:
            print(i.dump())

    def build_rdisk(self):
        blkdev = self.rawblk
        rdb = None
        parts = []
        fs = []
        for i in self.block_map:
            t = type(i)
            if t is RDBlock:
                rdb = i
            if t is Partition:
                parts.append(i)
            if t is FileSystem:
                fs.append(i)
            pass

        if rdb == None:
            rdb = RDBlock(blkdev)

        rdisk = RDisk(blkdev)
        rdisk.create(blkdev.geo, rdb_cyls=self.cyl_blks, blk_num=rdb.blk_num)

        for i in parts:
            rdisk.parts.append(i)
        for i in fs:
            rdisk.fs.append(i)

        return rdisk
