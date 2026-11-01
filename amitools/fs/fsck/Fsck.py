"""Main filesystem check and repair orchestrator."""

import shutil
from typing import Optional

from amitools.fs.validate.Validator import Validator
from amitools.fs.validate.Log import Log
from amitools.fs.blkdev.BlkDevFactory import BlkDevFactory

from .FsckConfig import FsckConfig
from .FsckResult import FsckResult, FsckIssue, IssueType, Severity


class Fsck:
    """Filesystem check and repair for Amiga disk images.

    Wraps the existing Validator for detection and adds repair capabilities.
    """

    def __init__(self, blkdev, config: Optional[FsckConfig] = None):
        """Initialize fsck with a block device and configuration.

        Args:
            blkdev: Block device to check/repair
            config: Configuration options (defaults to check-only mode)
        """
        self.blkdev = blkdev
        self.config = config or FsckConfig()
        self.result = FsckResult()
        self.validator = None

        # Determine log level based on config
        if self.config.quiet:
            self.min_level = Log.ERROR
        elif self.config.verbose >= 2:
            self.min_level = Log.DEBUG
        elif self.config.verbose >= 1:
            self.min_level = Log.INFO
        else:
            self.min_level = Log.WARN

    def run(self) -> FsckResult:
        """Run the filesystem check (and repair if configured).

        Returns:
            FsckResult containing all detected issues and repair status
        """
        # Phase 1: Detection using Validator
        self._run_validation()

        # Phase 2: Repair if requested
        if self.config.repair and not self.result.is_clean:
            self._run_repairs()

        return self.result

    def check(self) -> FsckResult:
        """Run check-only mode (no repairs)."""
        self._run_validation()
        return self.result

    def _run_validation(self) -> None:
        """Run the 5-phase validation and convert results to FsckIssues."""
        self.validator = Validator(
            self.blkdev, min_level=self.min_level, debug=(self.config.verbose >= 2)
        )

        # Step 1: Boot block
        boot_valid, bootable = self.validator.scan_boot()

        if not boot_valid:
            self.result.add_issue(
                IssueType.BAD_BOOT_BLOCK,
                Severity.ERROR,
                0,
                "Invalid boot block DOS type",
                repairable=False,
            )
            # Cannot continue without valid boot block
            return

        # Log boot block checksum issue if present
        if not bootable:
            self.result.add_issue(
                IssueType.BAD_CHECKSUM,
                Severity.INFO,
                0,
                "Invalid boot block checksum (disk not bootable)",
                repairable=True,
            )

        # Step 2: Root block
        root_valid = self.validator.scan_root()

        if not root_valid:
            self.result.add_issue(
                IssueType.BAD_ROOT_BLOCK,
                Severity.ERROR,
                self.blkdev.num_blocks // 2,
                "Invalid root block",
                repairable=False,
            )
            # Cannot continue without valid root block
            return

        # Step 3: Directory tree
        self.validator.scan_dir_tree()

        # Step 4: Files
        self.validator.scan_files()

        # Step 5: Bitmap
        self.validator.scan_bitmap()

        # Convert log entries to FsckIssues
        self._convert_log_to_issues()

    def _convert_log_to_issues(self) -> None:
        """Convert Validator log entries to FsckIssues."""
        for entry in self.validator.log.entries:
            issue_type, repairable = self._classify_log_entry(entry)

            severity = {
                Log.DEBUG: Severity.DEBUG,
                Log.INFO: Severity.INFO,
                Log.WARN: Severity.WARN,
                Log.ERROR: Severity.ERROR,
            }.get(entry.level, Severity.ERROR)

            # Skip if we already have this issue (from boot/root checks)
            if self._is_duplicate_issue(entry.blk_num, issue_type):
                continue

            self.result.add_issue(
                issue_type=issue_type,
                severity=severity,
                block_num=entry.blk_num,
                message=entry.msg,
                repairable=repairable,
            )

    def _classify_log_entry(self, entry) -> tuple:
        """Classify a log entry into an IssueType and determine if repairable.

        Returns:
            Tuple of (IssueType, repairable: bool)
        """
        msg = entry.msg.lower()

        # Checksum issues
        if "checksum" in msg:
            return (IssueType.BAD_CHECKSUM, True)

        # Own key issues
        if "own key" in msg:
            return (IssueType.INVALID_OWN_KEY, True)

        # Parent pointer issues
        if "parent" in msg and "invalid" in msg:
            return (IssueType.INVALID_PARENT_PTR, True)

        # Hash chain issues
        if "hash" in msg:
            if "chain" in msg:
                return (IssueType.INVALID_HASH_CHAIN, True)
            if "name hash" in msg:
                return (IssueType.INVALID_HASH_SLOT, True)

        # Circular references
        if "already used" in msg or "in its own chain" in msg:
            return (IssueType.CIRCULAR_CHAIN, True)

        # Block range issues
        if "out of range" in msg or "reserved" in msg:
            return (IssueType.BLOCK_OUT_OF_RANGE, False)

        # Bitmap issues
        if "bitmap" in msg:
            if "mismatch" in msg or "free" in msg or "used" in msg:
                return (IssueType.BITMAP_MISMATCH, True)
            if "flag" in msg:
                return (IssueType.BITMAP_INVALID_FLAG, True)
            return (IssueType.BITMAP_BLOCK_ERROR, True)

        # File data issues
        if "sequence" in msg or "seq" in msg:
            return (IssueType.WRONG_SEQ_NUM, False)
        if "byte size" in msg or "block count" in msg:
            return (IssueType.SIZE_MISMATCH, False)
        if "data block" in msg:
            return (IssueType.BAD_DATA_BLOCK, False)
        if "extension" in msg or "file list" in msg:
            return (IssueType.BAD_EXTENSION_CHAIN, False)

        # Directory issues
        if "dir" in msg:
            if "block" in msg:
                return (IssueType.INVALID_DIR_BLOCK, False)

        # Read errors
        if "read" in msg and "error" in msg:
            return (IssueType.READ_ERROR, False)
        if "can't read" in msg:
            return (IssueType.READ_ERROR, False)

        # Unknown
        return (IssueType.UNKNOWN, False)

    def _is_duplicate_issue(self, blk_num: int, issue_type: IssueType) -> bool:
        """Check if we already have this issue recorded."""
        for issue in self.result.issues:
            if issue.block_num == blk_num and issue.issue_type == issue_type:
                return True
        return False

    def _run_repairs(self) -> None:
        """Execute repair operations for detected issues."""
        from .Repairer import Repairer

        repairer = Repairer(self.blkdev, self.validator)

        # Get repairable issues sorted by priority
        repairable = self.result.get_repairable_issues()

        # Repair order:
        # 1. Checksums (can be fixed independently)
        # 2. Parent pointers
        # 3. Hash chains
        # 4. Bitmap (must be last)

        checksum_issues = [i for i in repairable if i.issue_type == IssueType.BAD_CHECKSUM]
        parent_issues = [i for i in repairable if i.issue_type == IssueType.INVALID_PARENT_PTR]
        bitmap_issues = [i for i in repairable if i.issue_type in (
            IssueType.BITMAP_MISMATCH, IssueType.BITMAP_INVALID_FLAG, IssueType.BITMAP_BLOCK_ERROR
        )]

        # Fix checksums
        for issue in checksum_issues:
            if repairer.fix_checksum(issue.block_num):
                issue.repaired = True
                issue.repair_action = "Recalculated checksum"

        # Fix parent pointers
        for issue in parent_issues:
            if repairer.fix_parent_pointer(issue.block_num):
                issue.repaired = True
                issue.repair_action = "Fixed parent pointer"

        # Rebuild bitmap (if any bitmap issues)
        if bitmap_issues and repairer.rebuild_bitmap():
            for issue in bitmap_issues:
                issue.repaired = True
                issue.repair_action = "Rebuilt bitmap"

        # Orphan recovery if salvage mode
        if self.config.salvage:
            self._run_orphan_recovery(repairer)

        # Flush all pending writes
        repairer.flush()

    def _run_orphan_recovery(self, repairer) -> None:
        """Attempt to recover orphaned blocks."""
        from .OrphanRecovery import OrphanRecovery

        recovery = OrphanRecovery(
            self.validator.block_scan,
            self.validator,
            aggressive=self.config.salvage,
        )

        orphans = recovery.find_orphans()
        self.result.orphans_found = len(orphans)

        if not orphans:
            return

        # Create lost+found directory if needed
        lost_found_blk = repairer.ensure_lost_found()
        if lost_found_blk is None:
            self.result.add_issue(
                IssueType.ORPHAN_BLOCK,
                Severity.WARN,
                -1,
                f"Found {len(orphans)} orphan(s) but could not create lost+found",
                repairable=False,
            )
            return

        # Recover each orphan
        for orphan in orphans:
            if recovery.recover_orphan(orphan, lost_found_blk, repairer):
                self.result.orphans_recovered += 1


def fsck_image(
    image_path: str,
    config: Optional[FsckConfig] = None,
    output_path: Optional[str] = None,
) -> FsckResult:
    """Convenience function to fsck an image file.

    Args:
        image_path: Path to the disk image
        config: Configuration options
        output_path: If set, create repaired copy instead of in-place repair

    Returns:
        FsckResult with all detected issues and repair status
    """
    factory = BlkDevFactory()

    # Determine if we need write access
    config = config or FsckConfig()
    read_only = config.check_only

    # Handle output copy mode
    if output_path or config.output_path:
        target_path = output_path or config.output_path
        shutil.copy2(image_path, target_path)
        image_path = target_path
        read_only = False

    # Open block device
    blkdev = factory.open(image_path, read_only=read_only)

    try:
        fsck = Fsck(blkdev, config)
        result = fsck.run()
    finally:
        blkdev.close()

    return result
