"""Professional File System 3 (PFS3) volumes, as written by pfs3aio."""

import struct

from .Const import DISK_TYPES


def is_pfs3_blkdev(blkdev):
    """does the block device hold a PFS3 volume? Looks at its boot block,
    where PFS3 has it: at the start of the partition aligned to its block
    size"""
    from .BlockIO import PFS3BlockIO

    try:
        data = PFS3BlockIO(blkdev).read(0)
    except (IOError, ValueError, AttributeError):
        return False
    if data is None or len(data) < 4:
        return False
    return struct.unpack_from(">I", data, 0)[0] in DISK_TYPES
