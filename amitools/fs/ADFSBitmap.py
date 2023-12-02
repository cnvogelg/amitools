import struct

from .block.BitmapBlock import BitmapBlock
from .block.BitmapExtBlock import BitmapExtBlock
from .DosType import *
from .FSError import *


class ADFSBitmap:
    def __init__(self, root_blk):
        self.root_blk = root_blk
        self.blkdev = self.root_blk.blkdev
        # state
        self.ext_blks = []
        self.bitmap_blks = []
        self.bitmap_data = None
        self.valid = False
        # bitmap block entries
        self.bitmap_blk_bytes = root_blk.blkdev.block_bytes - 4
        self.bitmap_blk_longs = root_blk.blkdev.block_longs - 1
        # calc size of bitmap
        self.bitmap_bits = self.blkdev.num_blocks - self.blkdev.reserved
        self.bitmap_longs = (self.bitmap_bits + 31) // 32
        self.bitmap_bytes = (self.bitmap_bits + 7) // 8
        # number of bits in last bitmap long
        last_long_bits = self.bitmap_bits % 32
        if last_long_bits == 0:
            last_long_bits = 32
        self.bitmap_last_long_bits = last_long_bits
        # number of blocks required for bitmap (and bytes consumed there)
        self.bitmap_num_blks = (
            self.bitmap_longs + self.bitmap_blk_longs - 1
        ) // self.bitmap_blk_longs
        self.bitmap_all_blk_bytes = self.bitmap_num_blks * self.bitmap_blk_bytes
        # blocks stored in root and in every ext block
        self.num_blks_in_root = len(self.root_blk.bitmap_ptrs)
        self.num_blks_in_ext = self.blkdev.block_longs - 1
        # number of ext blocks required
        self.num_ext = (
            self.bitmap_num_blks - self.num_blks_in_root + self.num_blks_in_ext - 1
        ) // (self.num_blks_in_ext)
        # start position for free bitmap searches (as long offset in bitmap)
        self.find_start_off = (root_blk.blk_num - self.blkdev.reserved) // 32
        # was bitmap modified?
        self.dirty = False
        # for DOS6/7 track used blocks
        self.num_used = 0

    def create(self):
        # clear local count
        self.num_used = 0

        # create data and preset with 0xff
        self.bitmap_data = bytearray([0xFF] * self.bitmap_all_blk_bytes)

        # clear bit for root block
        blk_pos = self.root_blk.blk_num
        self.clr_bit(blk_pos)
        blk_pos += 1

        # create ext blocks
        for i in range(self.num_ext):
            bm_ext = BitmapExtBlock(self.blkdev, blk_pos)
            bm_ext.create()
            self.clr_bit(blk_pos)
            blk_pos += 1
            self.ext_blks.append(bm_ext)

        # create bitmap blocks
        for i in range(self.bitmap_num_blks):
            bm = BitmapBlock(self.blkdev, blk_pos)
            bm.create()
            self.clr_bit(blk_pos)
            blk_pos += 1
            self.bitmap_blks.append(bm)

        # set pointers to ext blocks
        if self.num_ext > 0:
            self.root_blk.bitmap_ext_blk = self.ext_blks[0].blk_num
            for i in range(self.num_ext - 1):
                bm_ext = self.ext_blks[i]
                bm_ext_next = self.ext_blks[i + 1]
                bm_ext.bitmap_ext_blk = bm_ext_next.blk_num

        # set pointers to bitmap blocks
        cur_ext_index = 0
        cur_ext_pos = 0
        for i in range(self.bitmap_num_blks):
            blk_num = self.bitmap_blks[i].blk_num
            if i < self.num_blks_in_root:
                # pointers in root block
                self.root_blk.bitmap_ptrs[i] = blk_num
            else:
                # pointers in ext block
                self.ext_blks[cur_ext_index].bitmap_ptrs[cur_ext_pos] = blk_num
                cur_ext_pos += 1
                if cur_ext_pos == self.num_blks_in_ext:
                    cur_ext_pos = 0
                    cur_ext_index += 1
        self.valid = True
        self.dirty = True

    def write(self):
        if self.dirty:
            self.dirty = False
            # update bitmap
            self._write_ext_blks()
            self._write_bitmap_blks()
            # in DOS6/DOS7 update root block stats
            if rootblock_tracks_used_blocks(self.root_blk.fstype):
                self.root_blk.blocks_used = self.num_used
            # always write root (bitmap pointers)
            self.root_blk.write()

    def _write_ext_blks(self):
        # write ext blocks
        for ext_blk in self.ext_blks:
            ext_blk.write()

    def _write_bitmap_blks(self):
        # write bitmap blocks
        off = 0
        for blk in self.bitmap_blks:
            blk.set_bitmap_data(self.bitmap_data[off : off + self.bitmap_blk_bytes])
            blk.write()
            off += self.bitmap_blk_bytes

    def read(self):
        self.bitmap_blks = []
        bitmap_data = bytearray()

        # DOS6/7: update num used
        if rootblock_tracks_used_blocks(self.root_blk.fstype):
            self.num_used = self.root_blk.blocks_used

        # get bitmap blocks from root block
        blocks = self.root_blk.bitmap_ptrs
        for blk in blocks:
            if blk == 0:
                break
            bm = BitmapBlock(self.blkdev, blk)
            bm.read()
            if not bm.valid:
                raise FSError(INVALID_BITMAP_BLOCK, block=bm)
            self.bitmap_blks.append(bm)
            bitmap_data += bm.get_bitmap_data()

        # now check extended bitmap blocks
        ext_blk = self.root_blk.bitmap_ext_blk
        while ext_blk != 0:
            bm_ext = BitmapExtBlock(self.blkdev, ext_blk)
            bm_ext.read()
            self.ext_blks.append(bm_ext)
            blocks = bm_ext.bitmap_ptrs
            for blk in blocks:
                if blk == 0:
                    break
                bm = BitmapBlock(self.blkdev, blk)
                bm.read()
                if not bm.valid:
                    raise FSError(INVALID_BITMAP_BLOCK, block=bm)
                bitmap_data += bm.get_bitmap_data()
                self.bitmap_blks.append(bm)
            ext_blk = bm_ext.bitmap_ext_blk

        # check bitmap data
        num_bm_blks = len(self.bitmap_blks)
        num_bytes = self.bitmap_blk_bytes * num_bm_blks
        if num_bytes != len(bitmap_data):
            raise FSError(
                BITMAP_SIZE_MISMATCH,
                node=self,
                extra="got=%d want=%d" % (len(bitmap_data), num_bytes),
            )
        if num_bm_blks != self.bitmap_num_blks:
            raise FSError(
                BITMAP_BLOCK_COUNT_MISMATCH,
                node=self,
                extra="got=%d want=%d" % (self.bitmap_num_blks, num_bm_blks),
            )

        self.bitmap_data = bitmap_data
        self.valid = True

    def find_free(self):
        result = self.find_n_free(1)
        if result:
            return result[0]

    def find_n_free(self, num):
        result = []
        long_off = self.find_start_off
        last_long = self.bitmap_longs - 1
        # run through all longs of bitmap if needed
        for n in range(self.bitmap_longs):
            # read bitmap long
            val = struct.unpack_from(">I", self.bitmap_data, long_off * 4)[0]
            # some bits are free in here.. find em
            if val != 0:
                # last long has less bits
                if long_off == last_long:
                    max_bits = self.bitmap_last_long_bits
                else:
                    max_bits = 32

                base_blk_num = self.blkdev.reserved + long_off * 32

                # walk through bits and collect free ones
                for bit in range(max_bits):
                    mask = 1 << bit
                    if (val & mask) == mask:
                        blk_num = base_blk_num + bit
                        result.append(blk_num)
                        # got all free blocks?
                        if len(result) == num:
                            # keep as start offset for the next time
                            self.find_start_off = long_off
                            return result

            # next long
            long_off += 1
            if long_off == self.bitmap_longs:
                long_off = 0

    def get_num_free(self):
        num = 0
        res = self.blkdev.reserved
        for i in range(self.bitmap_bits):
            if self.get_bit(i + res):
                num += 1
        return num

    def get_num_used(self):
        num = 0
        res = self.blkdev.reserved
        for i in range(self.bitmap_bits):
            if not self.get_bit(i + res):
                num += 1
        return num

    def alloc_n(self, num):
        free_blks = self.find_n_free(num)
        if free_blks == None:
            return None
        for b in free_blks:
            self.clr_bit(b)
        return free_blks

    def dealloc_n(self, blks):
        for b in blks:
            self.set_bit(b)

    def get_bit(self, off):
        if off < self.blkdev.reserved or off >= self.blkdev.num_blocks:
            return None
        off = off - self.blkdev.reserved
        long_off = off // 32
        bit_off = off % 32
        val = struct.unpack_from(">I", self.bitmap_data, long_off * 4)[0]
        mask = 1 << bit_off
        return (val & mask) == mask

    # mark as free
    def set_bit(self, off):
        if off < self.blkdev.reserved or off >= self.blkdev.num_blocks:
            return False
        off = off - self.blkdev.reserved
        long_off = off // 32
        bit_off = off % 32
        val = struct.unpack_from(">I", self.bitmap_data, long_off * 4)[0]
        mask = 1 << bit_off
        if val & mask == 0:
            val = val | mask
            struct.pack_into(">I", self.bitmap_data, long_off * 4, val)
            self.dirty = True
            self.num_used -= 1

    # mark as used
    def clr_bit(self, off):
        if off < self.blkdev.reserved or off >= self.blkdev.num_blocks:
            return False
        off = off - self.blkdev.reserved
        long_off = off // 32
        bit_off = off % 32
        val = struct.unpack_from(">I", self.bitmap_data, long_off * 4)[0]
        mask = 1 << bit_off
        if val & mask == mask:
            val = val & ~mask
            struct.pack_into(">I", self.bitmap_data, long_off * 4, val)
            self.dirty = True
            self.num_used += 1

    def dump(self):
        print("Bitmap:")
        print("  ext: ", self.ext_blks)
        print("  blks:", len(self.bitmap_blks))
        print("  bits:", len(self.bitmap_data) * 8, self.blkdev.num_blocks)

    def print_info(self):
        num_free = self.get_num_free()
        num_used = self.get_num_used()
        print("num free:", num_free)
        print("num used:", num_used)
        if rootblock_tracks_used_blocks(self.root_blk.fstype):
            print("num used:", self.num_used, "(cached in root)")
        print("sum:     ", num_free + num_used)
        print("total:   ", self.bitmap_bits)

    def create_draw_bitmap(self):
        bm = bytearray(self.blkdev.num_blocks)
        return bm

    def print_free(self, brief=False):
        bm = self.create_draw_bitmap()
        res = self.blkdev.reserved
        for i in range(self.blkdev.num_blocks):
            if i >= res and self.get_bit(i):
                bm[i] = ord("F")
        self.print_draw_bitmap(bm, brief)

    def print_used(self, brief=False):
        bm = self.create_draw_bitmap()
        res = self.blkdev.reserved
        for i in range(self.blkdev.num_blocks):
            if i >= res and not self.get_bit(i):
                bm[i] = ord("#")
        self.print_draw_bitmap(bm, brief)

    def draw_on_bitmap(self, bm):
        # show reserved blocks
        res = self.blkdev.reserved
        bm[0:res] = b"x" * res
        # root block
        bm[self.root_blk.blk_num] = ord("R")
        # bitmap blocks
        for bm_blk in self.bitmap_blks:
            bm[bm_blk.blk_num] = ord("b")
        # bitmap ext blocks
        for ext_blk in self.ext_blks:
            bm[ext_blk.blk_num] = ord("B")

    def print_draw_bitmap(self, bm, brief=False):
        line = bytearray()
        blk = 0
        blk_cyl = self.blkdev.sectors * self.blkdev.heads
        found = False
        for i in range(self.blkdev.num_blocks):
            c = bm[i]
            if c == 0:
                c = ord(".")
            else:
                found = True
            line.append(c)
            if i % self.blkdev.sectors == self.blkdev.sectors - 1:
                line.append(ord(" "))
            if i % blk_cyl == blk_cyl - 1:
                if not brief or found:
                    print("%8d: %s" % (blk, line.decode("utf-8")))
                blk += blk_cyl
                line = bytearray()
                found = False
