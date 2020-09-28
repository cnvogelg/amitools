import time

from .Block import Block
from ..TimeStamp import *


class RootBlock(Block):
    def __init__(self, blkdev, blk_num):
        Block.__init__(
            self, blkdev, blk_num, is_type=Block.T_SHORT, is_sub_type=Block.ST_ROOT
        )

    def create(
        self, name, create_ts=None, disk_ts=None, mod_ts=None, extension=0, fstype=0
    ):
        Block.create(self)
        # init fresh hash table
        self.hash_size = self.blkdev.block_longs - 56
        self.hash_table = []
        for i in range(self.hash_size):
            self.hash_table.append(0)

        # timestamps
        self.mod_ts = mod_ts
        self.disk_ts = disk_ts
        self.create_ts = create_ts

        # name
        self.name = name

        # bitmap: blank
        self.bitmap_flag = 0xFFFFFFFF
        self.bitmap_ptrs = []
        for i in range(25):
            self.bitmap_ptrs.append(0)
        self.bitmap_ext_blk = 0

        # new stuff for DOS6 and DOS7
        self.fstype = fstype
        self.blocks_used = 0

        self.extension = extension

    def write(self):
        self._create_data()

        # hash table
        self._put_long(3, self.hash_size)
        for i in range(self.hash_size):
            self._put_long(6 + i, self.hash_table[i])

        # bitmap
        self._put_long(-50, self.bitmap_flag)
        for i in range(25):
            self._put_long(-49 + i, self.bitmap_ptrs[i])
        self._put_long(-24, self.bitmap_ext_blk)

        # timestamps
        self._put_timestamp(-23, self.mod_ts)
        self._put_timestamp(-10, self.disk_ts)
        self._put_timestamp(-7, self.create_ts)

        # name
        self._put_bstr(-20, 30, self.name)
        self._put_long(-2, self.extension)

        # DOS6 and DOS7 stuff
        self._put_long(-11, self.blocks_used)
        self._put_long(-4, self.fstype)

        Block.write(self)

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

        # name hash (limit to max size)
        self.hash_size = self._get_long(3)

        # read (limited) hash
        hs = self.hash_size
        mhs = self.blkdev.block_longs - 56
        if hs > mhs:
            hs = mhs
        self.hash_table = []
        for i in range(hs):
            self.hash_table.append(self._get_long(6 + i))

        # bitmap
        self.bitmap_flag = self._get_long(-50)
        self.bitmap_ptrs = []
        for i in range(25):
            bm_blk = self._get_long(-49 + i)
            self.bitmap_ptrs.append(bm_blk)
        self.bitmap_ext_blk = self._get_long(-24)

        # timestamps
        self.mod_ts = self._get_timestamp(-23)
        self.disk_ts = self._get_timestamp(-10)
        self.create_ts = self._get_timestamp(-7)

        # name
        self.name = self._get_bstr(-20, 30)
        self.extension = self._get_long(-2)

        # Number of used blocks (new in DOS6 and DOS7)
        self.blocks_used = self._get_long(-11)
        # filesystem type (new in DOS6 and DOS7, 0 in others)
        self.fstype = self._get_long(-4)

        # check validity
        self.valid = True
        # self.valid = (self.bitmap_flag == 0xffffffff)
        return self.valid

    def dump(self):
        Block.dump(self, "Root")
        print(" hash size: %d" % self.hash_size)
        print(" hash table:%s" % self.hash_table)
        print(" bmp flag:  0x%08x" % self.bitmap_flag)
        print(" bmp ptrs:  %s" % self.bitmap_ptrs)
        print(" bmp ext:   %d" % self.bitmap_ext_blk)
        print(" mod_ts:    %s" % self.mod_ts)
        print(" disk_ts:   %s" % self.disk_ts)
        print(" create_ts: %s" % self.create_ts)
        print(" disk name: %s" % self.name)
        print(" extension: %s" % self.extension)
