"""Block repair operations for fsck."""

from typing import Dict, List, Optional, Set, Tuple

from amitools.fs.block.Block import Block
from amitools.fs.block.RootBlock import RootBlock
from amitools.fs.block.UserDirBlock import UserDirBlock
from amitools.fs.block.FileHeaderBlock import FileHeaderBlock
from amitools.fs.block.FileListBlock import FileListBlock
from amitools.fs.block.BitmapBlock import BitmapBlock
from amitools.fs.validate.BlockScan import BlockScan
from amitools.fs.FSString import FSString
from amitools.fs.FileName import FileName
from amitools.fs.TimeStamp import TimeStamp
import amitools.fs.DosType as DosType


class Repairer:
    """Handles repair operations on filesystem blocks."""

    def __init__(self, blkdev, validator):
        """Initialize repairer.

        Args:
            blkdev: Block device to repair
            validator: Validator instance with scan results
        """
        self.blkdev = blkdev
        self.validator = validator
        self.block_scan = validator.block_scan
        self.dos_type = validator.dos_type
        self.root = validator.root
        self.is_intl = DosType.is_intl(self.dos_type) if self.dos_type else False
        self.is_longname = DosType.is_longname(self.dos_type) if self.dos_type else False

        # Cache of modified blocks pending write
        self.modified_blocks: Dict[int, Block] = {}

        # Track blocks we've repaired
        self.repaired_blocks: Set[int] = set()

        # Lost+found directory block number (if created)
        self.lost_found_blk: Optional[int] = None

        # Track allocated blocks during repair
        self.newly_allocated: Set[int] = set()

    def fix_checksum(self, blk_num: int) -> bool:
        """Recalculate and fix the checksum for a block.

        Args:
            blk_num: Block number to fix

        Returns:
            True if checksum was fixed, False otherwise
        """
        if blk_num < 0 or blk_num >= self.blkdev.num_blocks:
            return False

        try:
            # Read block
            blk = self._get_block(blk_num)
            if blk is None:
                return False

            # Recalculate checksum
            blk._put_chksum()

            # Mark as modified
            self.modified_blocks[blk_num] = blk
            self.repaired_blocks.add(blk_num)
            return True

        except Exception:
            return False

    def fix_parent_pointer(self, blk_num: int) -> bool:
        """Fix the parent pointer for a block.

        Args:
            blk_num: Block number to fix

        Returns:
            True if parent pointer was fixed, False otherwise
        """
        if blk_num < 0 or blk_num >= self.blkdev.num_blocks:
            return False

        # Get block info from scan
        bi = self.block_scan.get_block(blk_num)
        if bi is None:
            return False

        # Find correct parent by looking at directory scan
        correct_parent = self._find_correct_parent(blk_num)
        if correct_parent is None:
            return False

        try:
            # Read the block based on its type
            if bi.blk_type == BlockScan.BT_DIR:
                blk = UserDirBlock(self.blkdev, blk_num, self.is_longname)
            elif bi.blk_type == BlockScan.BT_FILE_HDR:
                blk = FileHeaderBlock(self.blkdev, blk_num, self.is_longname)
            elif bi.blk_type == BlockScan.BT_FILE_LIST:
                blk = FileListBlock(self.blkdev, blk_num)
            else:
                return False

            blk.read()

            # Fix parent pointer
            blk.parent = correct_parent
            blk._put_chksum()

            self.modified_blocks[blk_num] = blk
            self.repaired_blocks.add(blk_num)
            return True

        except Exception:
            return False

    def _find_correct_parent(self, blk_num: int) -> Optional[int]:
        """Find the correct parent block for a given block.

        Searches the directory scan results for the block's actual parent.
        """
        if self.validator.dir_scan is None:
            return None

        # Search through directory infos to find where this block is referenced
        for dir_info in self.validator.dir_scan.get_all_dir_infos():
            dir_blk_num = dir_info.blk_info.blk_num
            for hash_val, chain in dir_info.get_chains().items():
                for entry in chain.get_entries():
                    if entry.blk_info.blk_num == blk_num:
                        return dir_blk_num

        return None

    def fix_hash_chain(self, dir_blk_num: int, hash_val: int,
                       entries: List[int]) -> bool:
        """Fix a hash chain in a directory.

        Args:
            dir_blk_num: Directory block number
            hash_val: Hash table index
            entries: List of block numbers that should be in this chain (in order)

        Returns:
            True if chain was fixed
        """
        if not entries:
            return False

        try:
            # Read the directory block
            if dir_blk_num == self.root.blk_num:
                dir_blk = RootBlock(self.blkdev, dir_blk_num)
            else:
                dir_blk = UserDirBlock(self.blkdev, dir_blk_num, self.is_longname)
            dir_blk.read()

            # Update hash table entry to point to first block in chain
            dir_blk.hash_table[hash_val] = entries[0]

            # Fix chain links in each entry
            for i, entry_blk_num in enumerate(entries):
                bi = self.block_scan.get_block(entry_blk_num)
                if bi is None:
                    continue

                # Read the entry block
                if bi.blk_type == BlockScan.BT_DIR:
                    entry_blk = UserDirBlock(self.blkdev, entry_blk_num, self.is_longname)
                elif bi.blk_type == BlockScan.BT_FILE_HDR:
                    entry_blk = FileHeaderBlock(self.blkdev, entry_blk_num, self.is_longname)
                else:
                    continue
                entry_blk.read()

                # Set next pointer
                if i + 1 < len(entries):
                    entry_blk.hash_chain = entries[i + 1]
                else:
                    entry_blk.hash_chain = 0  # End of chain

                # Fix parent pointer
                entry_blk.parent = dir_blk_num

                # Update checksum
                entry_blk._put_chksum()
                self.modified_blocks[entry_blk_num] = entry_blk
                self.repaired_blocks.add(entry_blk_num)

            # Update directory block checksum
            dir_blk._put_chksum()
            self.modified_blocks[dir_blk_num] = dir_blk
            self.repaired_blocks.add(dir_blk_num)

            return True

        except Exception:
            return False

    def rebuild_bitmap(self) -> bool:
        """Rebuild the entire bitmap from block scan data.

        Returns:
            True if bitmap was rebuilt successfully
        """
        if self.block_scan is None or self.root is None:
            return False

        try:
            # Collect all used blocks
            used_blocks = self._collect_used_blocks()

            # Calculate bitmap parameters
            reserved = self.blkdev.reserved
            num_blocks = self.blkdev.num_blocks
            bitmap_bits = num_blocks - reserved

            # Calculate bytes needed for bitmap
            bitmap_longs = (bitmap_bits + 31) // 32
            bitmap_bytes = bitmap_longs * 4

            # Build new bitmap data
            # Bit = 1 means free, bit = 0 means used
            bitmap_data = bytearray(bitmap_bytes)

            # Initialize all as free (all 1s)
            for i in range(len(bitmap_data)):
                bitmap_data[i] = 0xFF

            # Mark used blocks
            for blk_num in used_blocks:
                if blk_num >= reserved:
                    bit_offset = blk_num - reserved
                    byte_idx = bit_offset // 8
                    bit_idx = bit_offset % 8
                    if byte_idx < len(bitmap_data):
                        bitmap_data[byte_idx] &= ~(1 << bit_idx)

            # Write bitmap blocks
            return self._write_bitmap_blocks(bitmap_data)

        except Exception:
            return False

    def _collect_used_blocks(self) -> Set[int]:
        """Collect all blocks that are in use."""
        used = set()

        # Reserved blocks are always used
        for i in range(self.blkdev.reserved):
            used.add(i)

        # Root block
        if self.root:
            used.add(self.root.blk_num)

        # All blocks that were scanned and are valid
        for blk_num, bi in enumerate(self.block_scan.block_map):
            if bi is not None and bi.used:
                used.add(blk_num)
            # Also mark blocks that are typed (valid structure)
            if bi is not None and bi.blk_status == BlockScan.BS_TYPE:
                used.add(blk_num)

        # Bitmap blocks themselves
        if self.root:
            for ptr in self.root.bitmap_ptrs:
                if ptr != 0 and ptr != Block.no_blk:
                    used.add(ptr)

        # Newly allocated blocks during repair
        used.update(self.newly_allocated)

        return used

    def _write_bitmap_blocks(self, bitmap_data: bytearray) -> bool:
        """Write bitmap data to bitmap blocks."""
        if self.root is None:
            return False

        # Get bitmap block size (block_bytes - 4 for checksum)
        bm_block_bytes = self.blkdev.block_bytes - 4

        # Calculate number of bitmap blocks needed
        num_bm_blocks = (len(bitmap_data) + bm_block_bytes - 1) // bm_block_bytes

        # Get existing bitmap block pointers
        bm_ptrs = [p for p in self.root.bitmap_ptrs if p != 0 and p != Block.no_blk]

        if len(bm_ptrs) < num_bm_blocks:
            return False

        # Write to each bitmap block
        offset = 0
        for i, bm_blk_num in enumerate(bm_ptrs[:num_bm_blocks]):
            chunk = bitmap_data[offset:offset + bm_block_bytes]
            if len(chunk) < bm_block_bytes:
                chunk = chunk + bytes([0xFF] * (bm_block_bytes - len(chunk)))

            bm_blk = BitmapBlock(self.blkdev, bm_blk_num)
            bm_blk.read()
            bm_blk.set_bitmap_data(chunk)
            bm_blk.write()

            offset += bm_block_bytes

        return True

    def _find_free_block(self) -> Optional[int]:
        """Find a single free block.

        Returns:
            Block number or None if no free block available
        """
        used_blocks = self._collect_used_blocks()

        # Search for free block starting from after reserved
        for blk_num in range(self.blkdev.reserved, self.blkdev.num_blocks):
            if blk_num not in used_blocks:
                return blk_num

        return None

    def ensure_lost_found(self) -> Optional[int]:
        """Ensure a lost+found directory exists.

        Creates it if necessary.

        Returns:
            Block number of lost+found directory, or None if failed
        """
        if self.lost_found_blk is not None:
            return self.lost_found_blk

        # Check if lost+found already exists
        if self.validator.dir_scan and self.validator.dir_scan.root_di:
            root_info = self.validator.dir_scan.root_di
            for hash_val, chain in root_info.get_chains().items():
                for entry in chain.get_entries():
                    name = entry.blk_info.name
                    if name and str(name).lower() == "lost+found":
                        self.lost_found_blk = entry.blk_info.blk_num
                        return self.lost_found_blk

        # Create lost+found directory
        return self._create_lost_found()

    def _create_lost_found(self) -> Optional[int]:
        """Create a new lost+found directory in the root.

        Returns:
            Block number of new directory, or None if failed
        """
        if self.root is None:
            return None

        try:
            # Find a free block
            new_blk_num = self._find_free_block()
            if new_blk_num is None:
                return None

            # Mark as allocated
            self.newly_allocated.add(new_blk_num)

            # Create the directory block
            name = FSString("lost+found")
            dir_blk = UserDirBlock(self.blkdev, new_blk_num, self.is_longname)

            # Calculate hash for the name
            fn = FileName(name, is_intl=self.is_intl, is_longname=self.is_longname)
            hash_size = self.blkdev.block_longs - 56
            fn_hash = fn.hash(hash_size=hash_size)

            # Get current hash chain
            current_chain = self.root.hash_table[fn_hash]

            # Create directory with proper links
            dir_blk.create(
                parent=self.root.blk_num,
                name=name,
                protect=0,
                comment=FSString("Recovered files"),
                mod_ts=TimeStamp(),
                hash_chain=current_chain,  # Link to existing chain
                extension=0,
            )
            dir_blk.write()

            # Update root's hash table
            root_blk = RootBlock(self.blkdev, self.root.blk_num)
            root_blk.read()
            root_blk.hash_table[fn_hash] = new_blk_num
            root_blk._put_chksum()
            root_blk.write()

            self.lost_found_blk = new_blk_num
            self.repaired_blocks.add(new_blk_num)
            self.repaired_blocks.add(self.root.blk_num)

            return new_blk_num

        except Exception:
            return None

    def link_orphan_to_lost_found(self, orphan_blk_num: int,
                                   orphan_name: str) -> bool:
        """Link an orphaned file or directory to lost+found.

        Args:
            orphan_blk_num: Block number of orphaned entry
            orphan_name: Name to use for the orphan (may be generated)

        Returns:
            True if orphan was successfully linked
        """
        if self.lost_found_blk is None:
            return False

        bi = self.block_scan.get_block(orphan_blk_num)
        if bi is None:
            return False

        try:
            # Read lost+found directory
            lf_blk = UserDirBlock(self.blkdev, self.lost_found_blk, self.is_longname)
            lf_blk.read()

            # Calculate hash for orphan name
            name = FSString(orphan_name)
            fn = FileName(name, is_intl=self.is_intl, is_longname=self.is_longname)
            hash_size = lf_blk.hash_size
            fn_hash = fn.hash(hash_size=hash_size)

            # Get current chain at this hash
            current_chain = lf_blk.hash_table[fn_hash]

            # Read and update the orphan block
            if bi.blk_type == BlockScan.BT_DIR:
                orphan_blk = UserDirBlock(self.blkdev, orphan_blk_num, self.is_longname)
            elif bi.blk_type == BlockScan.BT_FILE_HDR:
                orphan_blk = FileHeaderBlock(self.blkdev, orphan_blk_num, self.is_longname)
            else:
                return False

            orphan_blk.read()

            # Update orphan's parent and hash chain
            orphan_blk.parent = self.lost_found_blk
            orphan_blk.hash_chain = current_chain
            orphan_blk.name = name
            orphan_blk._put_chksum()
            orphan_blk.write()

            # Update lost+found's hash table
            lf_blk.hash_table[fn_hash] = orphan_blk_num
            lf_blk._put_chksum()
            lf_blk.write()

            self.repaired_blocks.add(orphan_blk_num)
            self.repaired_blocks.add(self.lost_found_blk)

            return True

        except Exception:
            return False

    def _get_block(self, blk_num: int) -> Optional[Block]:
        """Get a block, preferring cached modified version."""
        if blk_num in self.modified_blocks:
            return self.modified_blocks[blk_num]

        try:
            blk = Block(self.blkdev, blk_num)
            blk.read()
            return blk
        except Exception:
            return None

    def flush(self) -> None:
        """Write all modified blocks to disk."""
        for blk_num, blk in self.modified_blocks.items():
            try:
                blk.write()
            except Exception:
                pass

        self.modified_blocks.clear()
