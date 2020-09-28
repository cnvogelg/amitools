from amitools.fs.validate.Log import Log
import struct


class BitmapScan:
    """Validate the bitmap of a file system"""

    def __init__(self, block_scan, log):
        self.block_scan = block_scan
        self.log = log
        self.bm_blocks = None

    def scan_bitmap(self, root):
        """scan the file system bitmap"""
        # first check bitmap flag
        bm_flag = root.bitmap_flag
        if bm_flag != 0xFFFFFFFF:
            self.log.msg(Log.WARN, "Root bitmap flag not valid (-1)", root.blk_num)
        # now calculate the size of the bitmap
        num_blks = self.block_scan.blkdev.num_blocks - self.block_scan.blkdev.reserved
        block_longs = (
            self.block_scan.blkdev.block_longs - 1
        )  # all longs are available for bitmap
        self.num_bm_lwords = int((num_blks + 31) // 32)  # 32 blocks fit in a long word
        self.num_bm_blocks = int((self.num_bm_lwords + block_longs - 1) // block_longs)
        self.log.msg(
            Log.DEBUG,
            "Total Bitmap DWORDs: %d  (block %d)" % (self.num_bm_lwords, block_longs),
        )
        self.log.msg(Log.DEBUG, "Number of Bitmap Blocks: %d" % self.num_bm_blocks)
        # calc the bitmask in the last word
        last_filled_bits = self.num_bm_lwords * 32 - num_blks
        if last_filled_bits == 32:
            self.last_mask = 0xFFFFFFFF
        else:
            self.last_mask = (1 << last_filled_bits) - 1
        self.log.msg(Log.DEBUG, "Last DWORD mask: %08x" % self.last_mask)
        # now scan bitmap blocks and build list of all bitmap blocks
        self.read_bitmap_ptrs_and_blocks(root)
        found_blocks = len(self.bm_blocks)
        self.log.msg(Log.DEBUG, "Found Bitmap Blocks: %d" % found_blocks)
        # check number of blocks
        if found_blocks != self.num_bm_blocks:
            self.log.msg(
                Log.ERROR,
                "Invalid number of Bitmap Blocks: found=%d expected=%d"
                % (found_blocks, self.num_bm_blocks),
                root.blk_num,
            )
        else:
            # check bits in bitmap
            self.check_bits()

    def check_bits(self):
        """calculate allocation bits and verify with stored ones"""
        # block range
        blkdev = self.block_scan.blkdev
        # first bitmap data
        cur_pos = 0
        bm_blk = 0
        cur_data = self.bm_blocks[0].bitmap
        blk_size = len(cur_data)
        # loop throug all bitmap longwords
        lw = 0
        blk_num = blkdev.reserved
        max_lw = self.num_bm_lwords - 1
        while lw < max_lw:
            got = struct.unpack_from(">I", cur_data, cur_pos)[0]
            expect = self.calc_lword(blk_num)
            if got != expect:
                self.log.msg(
                    Log.ERROR,
                    "Invalid bitmap allocation (@%d: #%d+%d) blks [%d...%d] got=%08x expect=%08x"
                    % (lw, bm_blk, cur_pos / 4, blk_num, blk_num + 31, got, expect),
                )
            lw += 1
            blk_num += 32
            # fetch next bitmap data block
            cur_pos += 4
            if cur_pos == blk_size:
                bm_blk += 1
                cur_data = self.bm_blocks[bm_blk].bitmap
                cur_pos = 0
        # the last long word
        got = struct.unpack_from(">I", cur_data, cur_pos)[0] & self.last_mask
        expect = self.calc_lword(blk_num) & self.last_mask
        if got != expect:
            self.log.msg(
                Log.ERROR,
                "Invalid bitmap allocation (last) (@%d: #%d+%d) blks [%d...%d] got=%08x expect=%08x"
                % (
                    lw,
                    bm_blk,
                    cur_pos / 4,
                    blk_num,
                    blkdev.num_blocks - 1,
                    got,
                    expect,
                ),
            )

    def calc_lword(self, blk_num):
        """calcuate the bitmap lword"""
        value = 0
        for i in range(32):
            # set bit in lword if block is available
            if not self.block_scan.is_block_available(blk_num + i):
                mask = 1 << i
                value |= mask
        return value

    def read_bitmap_ptrs_and_blocks(self, root):
        """build the list of all file system bitmap blocks"""
        self.bm_blocks = []
        # scan list embedded in root block
        self.read_bm_list(root.bitmap_ptrs, root.blk_num)
        # now follow bitmap extension blocks
        cur_blk_num = root.blk_num
        bm_ext = root.bitmap_ext_blk
        while bm_ext != 0:
            # check ext block
            if self.block_scan.is_block_available(bm_ext):
                self.log.msg(
                    Log.ERROR,
                    "Bitmap ext block @%d already used?" % bm_block,
                    cur_blk_num,
                )
            else:
                bi = self.block_scan.read_block(bm_ext, is_bm_ext=True)
                if bi == None:
                    self.log.msg(
                        Log.ERROR,
                        "Error reading bitmap ext block @%d" % bm_ext,
                        cur_blk_num,
                    )
                    break
                else:
                    self.read_bm_list(bi.bitmap_ptrs, bm_ext)
                    cur_blk_num = bm_ext
                    bm_ext = bi.next_blk

    def read_bm_list(self, ptrs, blk_num):
        list_end = False
        for bm_block in ptrs:
            # still inside the pointer list
            if list_end == False:
                # add a normal block
                if bm_block != 0:
                    # make sure bitmap block was not used already
                    if self.block_scan.is_block_available(bm_block):
                        self.log.msg(
                            Log.ERROR,
                            "Bitmap block @%d already used?" % bm_block,
                            blk_num,
                        )
                    else:
                        # read bitmap block
                        bi = self.block_scan.read_block(bm_block, is_bm=True)
                        if bi == None:
                            self.log.msg(
                                Log.ERROR,
                                "Error reading bitmap block @%d" % bm_block,
                                blk_num,
                            )
                        else:
                            self.bm_blocks.append(bi)
                else:
                    list_end = True
            else:
                # make sure no blocks are referenced
                if bm_block != 0:
                    self.log.msg(
                        Log.ERROR,
                        "Referenced bitmap block @%d beyond end of list" % bm_block,
                        blk_num,
                    )
