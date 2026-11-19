import time
from .Block import Block
from .EntryBlock import EntryBlock
from .CommentBlock import CommentBlock
from ..ProtectFlags import ProtectFlags
from ..TimeStamp import *
from ..FSString import FSString


# A soft link (``ST_SOFTLINK``) is a file header whose data-block pointer
# table is unused: instead its target is a NUL-terminated C string that spans
# long 6 up to ``BLKO_SYMBOLICNAME_END`` (``(block_longs - 56) * 4`` bytes).
BLK_SYMBOLICNAME_START = 6
BLKO_SYMBOLICNAME_END = -51


class FileHeaderBlock(EntryBlock):
    def __init__(self, blkdev, blk_num, is_longname, sub_type=Block.ST_FILE):
        EntryBlock.__init__(
            self,
            blkdev,
            blk_num,
            is_type=Block.T_SHORT,
            is_sub_type=sub_type,
            is_longname=is_longname,
        )

    def _symbolic_name_size(self):
        """number of bytes available for a soft link target"""
        return (self.blkdev.block_longs - 56) * 4

    def _read_symbolic_name(self):
        return self._get_cstr(BLK_SYMBOLICNAME_START, self._symbolic_name_size())

    def _put_symbolic_name(self, fs_str):
        # clear the region first so a shorter target leaves no stale bytes
        # behind its terminating NUL
        self._put_bytes(BLK_SYMBOLICNAME_START, b"\0" * self._symbolic_name_size())
        self._put_cstr(BLK_SYMBOLICNAME_START, self._symbolic_name_size(), fs_str)

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

        # FileHeader fields
        self.own_key = self._get_long(1)
        self.block_count = self._get_long(2)
        self.first_data = self._get_long(4)

        # a soft link keeps its target where a file header holds the start of
        # its data-block pointer table; a file's table must stay untouched
        self.symbolic_name = None
        self.data_blocks = []
        if self.sub_type == Block.ST_SOFTLINK:
            self.symbolic_name = self._read_symbolic_name()
        else:
            # read (limited) data blocks table
            bc = self.block_count
            mbc = self.blkdev.block_longs - 56
            if bc > mbc:
                bc = mbc
            for i in range(bc):
                self.data_blocks.append(self._get_long(-51 - i))

        self.protect = self._get_long(-48)
        self.protect_flags = ProtectFlags(self.protect)
        self.byte_size = self._get_long(-47)
        self._read_nac_modts()
        self.hash_chain = self._get_long(-4)
        self.parent = self._get_long(-3)
        self.extension = self._get_long(-2)

        self.valid = self.own_key == self.blk_num
        return self.valid

    def write(self):
        Block._create_data(self)
        self._put_long(1, self.own_key)
        self._put_long(2, self.block_count)
        self._put_long(4, self.first_data)

        if self.sub_type == Block.ST_SOFTLINK:
            self._put_symbolic_name(self.symbolic_name)
        else:
            # data blocks
            for i in range(len(self.data_blocks)):
                self._put_long(-51 - i, self.data_blocks[i])

        self._put_long(-48, self.protect)
        self._put_long(-47, self.byte_size)

        self._write_nac_modts()

        self._put_long(-4, self.hash_chain)
        self._put_long(-3, self.parent)
        self._put_long(-2, self.extension)
        Block.write(self)

    def create(
        self,
        parent,
        name,
        data_blocks,
        extension,
        byte_size=0,
        protect=0,
        comment=None,
        mod_ts=None,
        hash_chain=0,
        symbolic_name=None,
    ):
        Block.create(self)
        self.own_key = self.blk_num
        self.symbolic_name = symbolic_name
        n = len(data_blocks)
        self.block_count = n
        if n == 0:
            self.first_data = 0
        else:
            self.first_data = data_blocks[0]

        self.data_blocks = data_blocks
        self.protect = protect
        self.protect_flags = ProtectFlags(self.protect)
        self.byte_size = byte_size
        if comment is None:
            self.comment = FSString()
        else:
            assert isinstance(comment, FSString)
            self.comment = comment
        self.mod_ts = mod_ts
        assert isinstance(name, FSString)
        self.name = name
        self.hash_chain = hash_chain
        self.parent = parent
        self.extension = extension
        self.valid = True
        return True

    def dump(self):
        Block.dump(self, "FileHeader")
        print(" own_key:    %d" % self.own_key)
        print(" blk_cnt:    %d" % self.block_count)
        print(" first_data: %d" % self.first_data)
        if self.data_blocks != None:
            print(" data blks:  %s #%d" % (self.data_blocks, len(self.data_blocks)))
        pf = ProtectFlags(self.protect)
        print(" protect:    0x%x 0b%s %s" % (self.protect, pf.bin_str(), pf))
        print(" byte_size:  %d" % self.byte_size)
        print(" comment:    '%s'" % self.comment)
        print(" mod_ts:     %s" % self.mod_ts)
        print(" name:       '%s'" % self.name)
        print(" hash_chain: %d" % self.hash_chain)
        print(" parent:     %d" % self.parent)
        print(" extension:  %d" % self.extension)
