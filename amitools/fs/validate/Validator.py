from amitools.fs.block.BootBlock import BootBlock
from amitools.fs.block.RootBlock import RootBlock

from amitools.fs.validate.Log import Log
from amitools.fs.validate.BlockScan import BlockScan
from amitools.fs.validate.DirScan import DirScan
from amitools.fs.validate.FileScan import FileScan
from amitools.fs.validate.BitmapScan import BitmapScan
import amitools.fs.DosType as DosType


class Validator:
    """Validate an AmigaDOS file system"""

    def __init__(self, blkdev, min_level, debug=False, progress=None):
        self.log = Log(min_level)
        self.debug = debug
        self.blkdev = blkdev
        self.dos_type = None
        self.boot = None
        self.root = None
        self.block_scan = None
        self.progress = progress

    def scan_boot(self):
        """Step 1: scan boot block.
        Returns (True, x) if boot block has a valid dos type.
        Returns (x, True) if boot block is bootable
        Invalid checksum of the block is tolerated but remarked.
        """
        # check boot block
        boot = BootBlock(self.blkdev)
        boot.read()
        if boot.valid:
            # dos type is valid
            self.boot = boot
            self.dos_type = boot.dos_type
            # give a warning if checksum is not correct
            if not boot.valid_chksum:
                self.log.msg(Log.INFO, "invalid boot block checksum", 0)
            self.log.msg(
                Log.INFO, "dos type is '%s'" % DosType.get_dos_type_str(self.dos_type)
            )
            return (True, boot.valid_chksum)
        else:
            self.log.msg(Log.ERROR, "invalid boot block dos type", 0)
            return (False, False)

    def scan_root(self):
        """Step 2: scan root block.
        Try to determine root block from boot block or guess number.
        Returns True if the root block could be decoded.
        """
        if self.boot != None:
            # retrieve root block number from boot block
            root_blk_num = self.boot.got_root_blk
            # guessed root
            new_root = self.blkdev.num_blocks // 2
            # check root block number
            if root_blk_num == 0:
                self.log.msg(
                    Log.INFO,
                    "Boot contains not Root blk. Using default: %d" % new_root,
                    root_blk_num,
                )
                root_blk_num = new_root
            # HD boot disks have invalid root of 880
            if root_blk_num == 880 and new_root == 880 * 2:
                self.log.msg(
                    Log.INFO,
                    "Boot contains invalid HD Root blk. Using default: %d" % new_root,
                    root_blk_num,
                )
                root_blk_num = new_root
            elif (
                root_blk_num < self.blkdev.reserved
                or root_blk_num > self.blkdev.num_blocks
            ):
                self.log.msg(
                    Log.INFO,
                    "Invalid root block number: given %d using guess %d"
                    % (root_blk_num, new_root),
                    root_blk_num,
                )
                root_blk_num = new_root
        else:
            # guess root block number
            root_blk_num = self.blkdev.num_blocks // 2
            self.log.msg(Log.INFO, "Guessed root block number", root_blk_num)
        # read root block
        root = RootBlock(self.blkdev, root_blk_num)
        root.read()
        if not root.valid:
            self.log.msg(
                Log.INFO, "Root block is not valid -> No file system", root_blk_num
            )
            self.root = None  # mode without root
            return False
        else:
            self.root = root
            return True

    def scan_dir_tree(self):
        """Step 3: scan directory structure
        Return false if structure is not healthy"""
        self.block_scan = BlockScan(self.blkdev, self.log, self.dos_type)
        self.dir_scan = DirScan(self.block_scan, self.log)
        ok = self.dir_scan.scan_tree(self.root.blk_num, progress=self.progress)
        self.log.msg(
            Log.INFO, "Scanned %d directories" % len(self.dir_scan.get_all_dir_infos())
        )
        if self.debug:
            self.dir_scan.dump()

    def scan_files(self):
        """Step 4: scan through all found files"""
        self.file_scan = FileScan(self.block_scan, self.log, self.dos_type)
        all_files = self.dir_scan.get_all_file_hdr_blk_infos()
        self.log.msg(Log.INFO, "Scanning %d files" % len(all_files))
        self.file_scan.scan_all_files(all_files, progress=self.progress)
        if self.debug:
            self.file_scan.dump()

    def scan_bitmap(self):
        """Step 5: validate block bitmap"""
        self.bitmap_scan = BitmapScan(self.block_scan, self.log)
        self.bitmap_scan.scan_bitmap(self.root)

    def get_summary(self):
        """Return (errors, warnings) of log"""
        num_errors = self.log.get_num_level(Log.ERROR)
        num_warns = self.log.get_num_level(Log.WARN)
        return (num_errors, num_warns)
