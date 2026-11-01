"""Orphan block detection and recovery."""

from dataclasses import dataclass
from typing import List, Optional, Set, TYPE_CHECKING

from amitools.fs.validate.BlockScan import BlockScan
from amitools.fs.FSString import FSString

if TYPE_CHECKING:
    from .Repairer import Repairer


@dataclass
class OrphanInfo:
    """Information about an orphaned block."""

    blk_num: int
    blk_type: int
    name: Optional[FSString] = None
    byte_size: int = 0
    recoverable: bool = True
    recovery_name: Optional[str] = None  # Generated name if original unknown


class OrphanRecovery:
    """Detect and recover orphaned blocks (valid structures not linked in tree)."""

    def __init__(self, block_scan: BlockScan, validator, aggressive: bool = False):
        """Initialize orphan recovery.

        Args:
            block_scan: BlockScan with classified blocks
            validator: Validator with directory/file scan results
            aggressive: If True, attempt recovery of blocks with bad checksums
        """
        self.block_scan = block_scan
        self.validator = validator
        self.aggressive = aggressive

        # Blocks that are properly linked in the directory tree
        self.linked_blocks: Set[int] = set()

        # Build set of linked blocks
        self._build_linked_set()

    def _build_linked_set(self) -> None:
        """Build set of all blocks that are properly linked."""
        # Reserved blocks
        for i in range(self.block_scan.blkdev.reserved):
            self.linked_blocks.add(i)

        # Root block
        if self.validator.root:
            self.linked_blocks.add(self.validator.root.blk_num)

        # All blocks from directory scan
        if self.validator.dir_scan:
            for dir_info in self.validator.dir_scan.get_all_dir_infos():
                self.linked_blocks.add(dir_info.blk_info.blk_num)
                for hash_val, chain in dir_info.get_chains().items():
                    for entry in chain.get_entries():
                        self.linked_blocks.add(entry.blk_info.blk_num)

        # All file data and extension blocks from file scan
        if hasattr(self.validator, 'file_scan') and self.validator.file_scan:
            # File extension blocks and data blocks are tracked during file scan
            pass  # These are already marked as used in block_scan

        # Bitmap blocks
        if self.validator.root:
            for ptr in self.validator.root.bitmap_ptrs:
                if ptr != 0 and ptr != 0xFFFFFFFF:
                    self.linked_blocks.add(ptr)

    def find_orphans(self) -> List[OrphanInfo]:
        """Find all orphaned blocks.

        Orphans are valid file/directory headers that aren't linked
        in the directory tree.

        Returns:
            List of OrphanInfo for each orphaned block
        """
        orphans = []
        orphan_count = 0

        for blk_num, bi in enumerate(self.block_scan.block_map):
            if bi is None:
                continue

            # Skip if already linked
            if blk_num in self.linked_blocks:
                continue

            # Only recover file headers and directories
            if bi.blk_type not in (BlockScan.BT_FILE_HDR, BlockScan.BT_DIR):
                continue

            # Skip if not valid (unless aggressive mode)
            if bi.blk_status != BlockScan.BS_TYPE:
                if not self.aggressive:
                    continue

            # Create orphan info
            orphan = OrphanInfo(
                blk_num=blk_num,
                blk_type=bi.blk_type,
                name=getattr(bi, 'name', None),
                byte_size=getattr(bi, 'byte_size', 0),
            )

            # Generate recovery name if needed
            if orphan.name is None or str(orphan.name) == "":
                orphan_count += 1
                type_prefix = "file" if bi.blk_type == BlockScan.BT_FILE_HDR else "dir"
                orphan.recovery_name = f"orphan_{type_prefix}_{orphan_count:04d}"
            else:
                # Use original name but ensure uniqueness
                base_name = str(orphan.name)
                orphan_count += 1
                orphan.recovery_name = f"{base_name}_{orphan_count:04d}"

            orphans.append(orphan)

        return orphans

    def recover_orphan(self, orphan: OrphanInfo, lost_found_blk: int,
                       repairer: "Repairer") -> bool:
        """Recover an orphan by linking it into lost+found.

        Args:
            orphan: OrphanInfo to recover
            lost_found_blk: Block number of lost+found directory
            repairer: Repairer instance for making changes

        Returns:
            True if recovery succeeded
        """
        if orphan.recovery_name is None:
            return False

        return repairer.link_orphan_to_lost_found(
            orphan.blk_num,
            orphan.recovery_name
        )

    def get_orphan_summary(self, orphans: List[OrphanInfo]) -> str:
        """Get a summary of found orphans.

        Args:
            orphans: List of orphans

        Returns:
            Human-readable summary
        """
        if not orphans:
            return "No orphaned blocks found"

        file_count = sum(1 for o in orphans if o.blk_type == BlockScan.BT_FILE_HDR)
        dir_count = sum(1 for o in orphans if o.blk_type == BlockScan.BT_DIR)
        total_size = sum(o.byte_size for o in orphans)

        parts = []
        if file_count:
            parts.append(f"{file_count} file(s)")
        if dir_count:
            parts.append(f"{dir_count} directory(ies)")

        summary = f"Found {len(orphans)} orphan(s): " + ", ".join(parts)
        if total_size > 0:
            summary += f" (total size: {total_size} bytes)"

        return summary
