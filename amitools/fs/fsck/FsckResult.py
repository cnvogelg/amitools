"""Result tracking for fsck operations."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional


class Severity(Enum):
    """Issue severity levels."""

    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3


class IssueType(Enum):
    """Types of filesystem issues that can be detected."""

    # Structural issues
    BAD_BOOT_BLOCK = auto()
    BAD_ROOT_BLOCK = auto()
    BAD_CHECKSUM = auto()
    INVALID_OWN_KEY = auto()
    INVALID_PARENT_PTR = auto()
    INVALID_HASH_CHAIN = auto()
    CIRCULAR_CHAIN = auto()
    BLOCK_OUT_OF_RANGE = auto()
    BLOCK_ALREADY_USED = auto()

    # File issues
    BAD_FILE_HEADER = auto()
    BAD_EXTENSION_CHAIN = auto()
    BAD_DATA_BLOCK = auto()
    WRONG_SEQ_NUM = auto()
    SIZE_MISMATCH = auto()

    # Bitmap issues
    BITMAP_MISMATCH = auto()
    BITMAP_INVALID_FLAG = auto()
    BITMAP_BLOCK_ERROR = auto()

    # Orphan issues
    ORPHAN_BLOCK = auto()
    ORPHAN_FILE = auto()
    ORPHAN_DIR = auto()

    # Directory issues
    DUPLICATE_NAME = auto()
    INVALID_HASH_SLOT = auto()
    INVALID_DIR_BLOCK = auto()

    # Other
    READ_ERROR = auto()
    UNKNOWN = auto()


@dataclass
class FsckIssue:
    """Represents a single filesystem issue."""

    issue_type: IssueType
    severity: Severity
    block_num: int
    message: str
    repairable: bool = False
    repaired: bool = False
    repair_action: Optional[str] = None

    def __str__(self) -> str:
        prefix = "@%06d" % self.block_num if self.block_num >= 0 else " " * 7
        status = ""
        if self.repaired:
            status = " [FIXED]"
        elif self.repairable:
            status = " [REPAIRABLE]"
        return f"{prefix}:{self.severity.name}:{self.message}{status}"


@dataclass
class FsckResult:
    """Results of a filesystem check/repair operation."""

    issues: List[FsckIssue] = field(default_factory=list)
    orphans_found: int = 0
    orphans_recovered: int = 0

    @property
    def is_clean(self) -> bool:
        """Return True if no errors were found."""
        return self.error_count == 0

    @property
    def error_count(self) -> int:
        """Count of ERROR severity issues."""
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        """Count of WARN severity issues."""
        return sum(1 for i in self.issues if i.severity == Severity.WARN)

    @property
    def fixed_count(self) -> int:
        """Count of issues that were repaired."""
        return sum(1 for i in self.issues if i.repaired)

    @property
    def unfixed_count(self) -> int:
        """Count of repairable issues that were not repaired."""
        return sum(1 for i in self.issues if i.repairable and not i.repaired)

    def add_issue(
        self,
        issue_type: IssueType,
        severity: Severity,
        block_num: int,
        message: str,
        repairable: bool = False,
    ) -> FsckIssue:
        """Add a new issue to the results."""
        issue = FsckIssue(
            issue_type=issue_type,
            severity=severity,
            block_num=block_num,
            message=message,
            repairable=repairable,
        )
        self.issues.append(issue)
        return issue

    def get_issues_by_type(self, issue_type: IssueType) -> List[FsckIssue]:
        """Get all issues of a specific type."""
        return [i for i in self.issues if i.issue_type == issue_type]

    def get_issues_by_severity(self, severity: Severity) -> List[FsckIssue]:
        """Get all issues of a specific severity."""
        return [i for i in self.issues if i.severity == severity]

    def get_repairable_issues(self) -> List[FsckIssue]:
        """Get all issues that can be repaired."""
        return [i for i in self.issues if i.repairable and not i.repaired]

    def dump(self, min_severity: Severity = Severity.WARN) -> None:
        """Print all issues at or above the given severity."""
        for issue in self.issues:
            if issue.severity.value >= min_severity.value:
                print(issue)

    def summary(self) -> str:
        """Return a summary string."""
        parts = []
        if self.error_count > 0:
            parts.append(f"{self.error_count} error(s)")
        if self.warning_count > 0:
            parts.append(f"{self.warning_count} warning(s)")
        if self.fixed_count > 0:
            parts.append(f"{self.fixed_count} fixed")
        if self.orphans_recovered > 0:
            parts.append(f"{self.orphans_recovered} orphan(s) recovered")

        if not parts:
            return "Filesystem is clean"
        return ", ".join(parts)
