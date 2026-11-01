"""Configuration options for fsck operations."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FsckConfig:
    """Configuration for filesystem check and repair operations.

    Attributes:
        check_only: If True, only report issues without modifying (default).
        repair: If True, attempt to repair detected issues.
        salvage: If True, use aggressive orphan recovery (implies repair).
        output_path: If set, create repaired copy at this path instead of in-place.
        verbose: Verbosity level (0=normal, 1=verbose, 2+=debug).
        quiet: If True, only show errors.
    """

    check_only: bool = True
    repair: bool = False
    salvage: bool = False
    output_path: Optional[str] = None
    verbose: int = 0
    quiet: bool = False

    def __post_init__(self):
        # salvage implies repair
        if self.salvage:
            self.repair = True
        # repair disables check_only
        if self.repair:
            self.check_only = False

    @classmethod
    def from_opts(cls, opts: list) -> "FsckConfig":
        """Parse configuration from xdftool option list.

        Supports multiple formats:
        - Simple keywords: check, repair, salvage, verbose, quiet
        - Key=value: output=/path/to/file

        Args:
            opts: List of option strings

        Returns:
            FsckConfig instance
        """
        config = cls()

        for opt in opts:
            opt_lower = opt.lower()

            # Simple keywords
            if opt_lower == "check":
                config.check_only = True
                config.repair = False
            elif opt_lower == "repair":
                config.repair = True
                config.check_only = False
            elif opt_lower == "salvage":
                config.salvage = True
                config.repair = True
                config.check_only = False
            elif opt_lower == "verbose":
                config.verbose += 1
            elif opt_lower == "quiet":
                config.quiet = True

            # Key=value format for output path
            elif opt_lower.startswith("output="):
                config.output_path = opt[7:]  # Use original case for path

        return config
