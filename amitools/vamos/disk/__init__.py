"""Disk image support for programs running under vamos."""

from .backend import (
    BlockBackend,
    DiskImage,
    DiskPartition,
    DosDevice,
    HostFileLock,
    RawDiskImage,
    open_disk_backend,
)
from .session import DiskSession
from .spec import DiskSpec
from .locking import PartitionFileLock

__all__ = [
    "BlockBackend",
    "DiskImage",
    "DiskPartition",
    "DiskSession",
    "DiskSpec",
    "DosDevice",
    "HostFileLock",
    "PartitionFileLock",
    "RawDiskImage",
    "open_disk_backend",
]
