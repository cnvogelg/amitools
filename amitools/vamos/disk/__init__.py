"""Disk image support for programs running under vamos."""

from .backend import BlockBackend, DiskImage, DiskPartition, HostFileLock
from .session import DiskSession

__all__ = [
    "BlockBackend",
    "DiskImage",
    "DiskPartition",
    "DiskSession",
    "HostFileLock",
]
