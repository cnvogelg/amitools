import time

from amitools.fs.block.Block import Block
from amitools.fs.block.UserDirBlock import UserDirBlock
from amitools.fs.block.RootBlock import RootBlock
from amitools.fs.block.FileHeaderBlock import FileHeaderBlock
from amitools.fs.block.FileListBlock import FileListBlock
from amitools.fs.block.FileDataBlock import FileDataBlock
from amitools.fs.block.BitmapBlock import BitmapBlock
from amitools.fs.block.BitmapExtBlock import BitmapExtBlock
from amitools.fs.block.CommentBlock import CommentBlock
from amitools.fs.FSString import FSString
import amitools.fs.DosType as DosType

from amitools.fs.validate.Log import Log


class BlockInfo:
    """Store essential info of a block"""

    def __init__(self, blk_num):
        self.blk_num = blk_num
        self.blk_status = BlockScan.BS_UNKNOWN
        self.blk_type = BlockScan.BT_UNKNOWN
        self.used = False
        self.own_key = None

    def __str__(self):
        return str(self.__dict__)


class BlockScan:
    """Scan a full volume and classify the blocks"""

    # block status
    BS_UNKNOWN = 0  # undecided or unchecked
    BS_READ_ERROR = 1  # error reading block
    BS_INVALID = 2  # not a detected AmigaDOS block
    BS_VALID = 3  # is a AmigaDOS block structure but type was not detected
    BS_TYPE = 4  # detected block type
    NUM_BS = 5

    # block type
    BT_UNKNOWN = 0
    BT_ROOT = 1
    BT_DIR = 2
    BT_FILE_HDR = 3
    BT_FILE_LIST = 4
    BT_FILE_DATA = 5
    BT_BITMAP = 6
    BT_BITMAP_EXT = 7
    BT_COMMENT = 8
    NUM_BT = 9

    def __init__(self, blkdev, log, dos_type):
        self.blkdev = blkdev
        self.log = log
        self.dos_type = dos_type

        self.map_status = None
        self.map_type = None
        self.block_map = [None] * self.blkdev.num_blocks
        self.map_status = [[] for i in range(self.NUM_BS)]
        self.map_type = [[] for i in range(self.NUM_BT)]

    def scan_all(self, progress=lambda x: x):
        """Scan all blocks of the given block device
        Return True if there is a chance that a file system will be found there
        """
        # range to scan
        begin_blk = self.blkdev.reserved
        num_blk = self.blkdev.num_blocks - self.blkdev.reserved
        self.log.msg(
            Log.DEBUG, "block: checking range: +%d num=%d" % (begin_blk, num_blk)
        )

        # scan all blocks
        for n in range(num_blk):
            blk_num = n + begin_blk

            # read/get block
            bi = self.get_block(blk_num)

            # own key ok?
            if bi != None:
                if bi.blk_status == self.BS_TYPE:
                    if bi.own_key != None and bi.own_key != blk_num:
                        self.log.msg(
                            Log.ERROR,
                            "Own key is invalid: %d type: %d"
                            % (bi.own_key, bi.blk_type),
                            blk_num,
                        )

            # first summary after block scan
            num_error_blocks = len(self.map_status[self.BS_READ_ERROR])
            if num_error_blocks > 0:
                self.log.msg(
                    Log.ERROR, "%d unreadable error blocks found" % num_error_blocks
                )
            num_valid_blocks = len(self.map_status[self.BS_VALID])
            if num_valid_blocks > 0:
                self.log.msg(
                    Log.INFO, "%d valid but unknown blocks found" % num_valid_blocks
                )
            num_invalid_blocks = len(self.map_status[self.BS_INVALID])
            if num_invalid_blocks > 0:
                self.log.msg(Log.INFO, "%d invalid blocks found" % num_invalid_blocks)

    def read_block(self, blk_num, is_bm=False, is_bm_ext=False):
        """read block from device, decode it, and return block info instance"""
        try:
            # read block from device
            if is_bm:
                blk = BitmapBlock(self.blkdev, blk_num)
            elif is_bm_ext:
                blk = BitmapExtBlock(self.blkdev, blk_num)
            else:
                blk = Block(self.blkdev, blk_num)
            blk.read()
            data = blk.data
            # create block info
            bi = BlockInfo(blk_num)
            # --- classify block ---
            if blk.valid:
                # block is valid AmigaDOS
                bi.blk_status = self.BS_VALID
                # --- bitmap block ---
                if is_bm:
                    bi.blk_type = self.BT_BITMAP
                    bi.blk_status = self.BS_TYPE
                    bi.bitmap = blk.get_bitmap_data()
                # --- bitmap ext block ---
                elif is_bm_ext:
                    bi.blk_type = self.BT_BITMAP_EXT
                    bi.blk_status = self.BS_TYPE
                    bi.bitmap_ptrs = blk.bitmap_ptrs
                    bi.next_blk = blk.bitmap_ext_blk
                # --- root block ---
                elif blk.is_root_block():
                    bi.blk_type = self.BT_ROOT
                    bi.blk_status = self.BS_TYPE
                    root = RootBlock(self.blkdev, blk_num)
                    root.set(data)
                    bi.name = root.name
                    bi.hash_table = root.hash_table
                    bi.parent_blk = 0
                    self.log.msg(Log.DEBUG, "Found Root: '%s'" % bi.name, blk_num)
                    # chech hash size
                    nht = len(root.hash_table)
                    if root.hash_size != nht:
                        self.log.msg(
                            Log.ERROR, "Root block hash table size mismatch", blk_num
                        )
                    eht = self.blkdev.block_longs - 56
                    if nht != eht:
                        self.log.msg(
                            Log.WARN,
                            "Root block does not have normal hash size: %d != %d"
                            % (nht, eht),
                            blk_num,
                        )
                # --- user dir block ---
                elif blk.is_user_dir_block():
                    bi.blk_type = self.BT_DIR
                    bi.blk_status = self.BS_TYPE
                    user = UserDirBlock(
                        self.blkdev, blk_num, DosType.is_longname(self.dos_type)
                    )
                    user.set(data)
                    bi.name = user.name
                    bi.parent_blk = user.parent
                    bi.next_blk = user.hash_chain
                    bi.hash_table = user.hash_table
                    bi.own_key = user.own_key
                    self.log.msg(Log.DEBUG, "Found Dir : '%s'" % bi.name, blk_num)
                # --- filter header block ---
                elif blk.is_file_header_block():
                    bi.blk_type = self.BT_FILE_HDR
                    bi.blk_status = self.BS_TYPE
                    fh = FileHeaderBlock(
                        self.blkdev, blk_num, DosType.is_longname(self.dos_type)
                    )
                    fh.set(data)
                    bi.name = fh.name
                    bi.parent_blk = fh.parent
                    bi.next_blk = fh.hash_chain
                    bi.own_key = fh.own_key
                    bi.byte_size = fh.byte_size
                    bi.data_blocks = fh.data_blocks
                    bi.extension = fh.extension
                    self.log.msg(Log.DEBUG, "Found File: '%s'" % bi.name, blk_num)
                # --- file list block ---
                elif blk.is_file_list_block():
                    bi.blk_type = self.BT_FILE_LIST
                    fl = FileListBlock(self.blkdev, blk_num)
                    fl.set(data)
                    bi.blk_status = self.BS_TYPE
                    bi.ext_blk = fl.extension
                    bi.blk_list = fl.data_blocks
                    bi.own_key = fl.own_key
                    bi.data_blocks = fl.data_blocks
                    bi.extension = fl.extension
                    bi.parent_blk = fl.parent
                # --- file data block (OFS) ---
                elif blk.is_file_data_block():
                    bi.blk_type = self.BT_FILE_DATA
                    bi.blk_status = self.BS_TYPE
                    fd = FileDataBlock(self.blkdev, blk_num)
                    fd.set(data)
                    bi.data_size = fd.data_size
                    bi.hdr_key = fd.hdr_key
                    bi.seq_num = fd.seq_num
                elif blk.is_comment_block():
                    bi.blk_type = self.BT_COMMENT
                    bi.blk_status = self.BS_TYPE
                    cblk = CommentBlock(self.blkdev, blk_num)
                    bi.hdr_key = cblk.hdr_key
                    bi.own_key = cblk.own_key

        except IOError as e:
            self.log.msg(Log.ERROR, "Can't read block", blk_num)
            bi = BlockInfo(blk_num)
            bi.blk_status = BS_READ_ERROR

        # sort block info into map and arrays assigned by status/type
        self.block_map[blk_num] = bi
        self.map_status[bi.blk_status].append(bi)
        self.map_type[bi.blk_type].append(bi)
        return bi

    def any_chance_of_fs(self):
        """is there any chance to find a FS on this block device?"""
        num_dirs = len(self.map_type[self.BT_DIR])
        num_files = len(self.map_type[self.BT_FILE_HDR])
        num_roots = len(self.map_type[self.BT_ROOT])
        return (num_files > 0) or ((num_roots + num_dirs) > 0)

    def get_blocks_of_type(self, t):
        return self.map_type[t]

    def get_blocks_with_key_value(self, key, value):
        res = []
        for bi in self.block_map:
            if hasattr(bi, key):
                v = getattr(bi, key)
                if v == value:
                    res.append(bi)
        return res

    def is_block_available(self, num):
        if num >= 0 and num < len(self.block_map):
            return self.block_map[num] != None
        else:
            return False

    def get_block(self, num):
        if num >= 0 and num < len(self.block_map):
            bi = self.block_map[num]
            if bi == None:
                bi = self.read_block(num)
            return bi
        else:
            return None

    def dump(self):
        for b in self.block_map:
            if b != None:
                print(b)
