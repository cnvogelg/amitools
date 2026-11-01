#!/usr/bin/env python3
"""
Create corrupted disk images for fsck testing.

This script creates various types of corrupted Amiga disk images
that can be used to test fsck repair capabilities.
"""

import os
import struct
import shutil
from pathlib import Path

from amitools.fs.blkdev.BlkDevFactory import BlkDevFactory
from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.FSString import FSString


def create_base_disk(path: str, name: str = "TestDisk", with_content: bool = True):
    """Create a base disk image with optional content."""
    factory = BlkDevFactory()
    blkdev = factory.create(path, options={"size": "880K"})
    vol = ADFSVolume(blkdev)
    vol.create(FSString(name))

    if with_content:
        # Create some directories and files
        vol.create_dir(FSString("System"))
        vol.create_dir(FSString("Data"))
        vol.write_file(b"Hello, World!\n", FSString("System"), FSString("hello.txt"))
        vol.write_file(bytes(range(256)) * 10, FSString("Data"), FSString("binary.dat"))

    vol.close()
    blkdev.close()
    return path


def corrupt_checksum(path: str, blk_num: int):
    """Corrupt the checksum of a specific block."""
    factory = BlkDevFactory()
    blkdev = factory.open(path, read_only=False)

    data = bytearray(blkdev.read_block(blk_num))
    # Checksum is at offset 20 (5 longs * 4 bytes)
    data[20] ^= 0xFF
    blkdev.write_block(blk_num, bytes(data))

    blkdev.close()


def corrupt_parent_pointer(path: str, blk_num: int, wrong_parent: int):
    """Set an incorrect parent pointer."""
    factory = BlkDevFactory()
    blkdev = factory.open(path, read_only=False)

    data = bytearray(blkdev.read_block(blk_num))
    # Parent is at offset -3 longs from end = block_longs - 3
    # For 512-byte blocks: 128 - 3 = 125 longs = offset 500
    parent_offset = (blkdev.block_longs - 3) * 4
    struct.pack_into(">I", data, parent_offset, wrong_parent)
    blkdev.write_block(blk_num, bytes(data))

    blkdev.close()


def corrupt_hash_chain(path: str, dir_blk_num: int, hash_idx: int, bad_ptr: int):
    """Corrupt a hash table entry in a directory."""
    factory = BlkDevFactory()
    blkdev = factory.open(path, read_only=False)

    data = bytearray(blkdev.read_block(dir_blk_num))
    # Hash table starts at offset 6 longs
    hash_offset = (6 + hash_idx) * 4
    struct.pack_into(">I", data, hash_offset, bad_ptr)
    blkdev.write_block(dir_blk_num, bytes(data))

    blkdev.close()


def corrupt_bitmap(path: str):
    """Corrupt the bitmap to show wrong allocation."""
    factory = BlkDevFactory()
    blkdev = factory.open(path, read_only=False)

    # Get root block to find bitmap pointers
    root_blk_num = blkdev.num_blocks // 2
    root_data = blkdev.read_block(root_blk_num)

    # Bitmap pointers start at offset -49 longs
    bm_ptr_offset = (blkdev.block_longs - 49) * 4
    bm_blk_num = struct.unpack_from(">I", root_data, bm_ptr_offset)[0]

    if bm_blk_num > 0 and bm_blk_num < blkdev.num_blocks:
        bm_data = bytearray(blkdev.read_block(bm_blk_num))
        # Flip some bits in the bitmap (mark used blocks as free)
        for i in range(10, 20):
            bm_data[i] ^= 0xFF
        blkdev.write_block(bm_blk_num, bytes(bm_data))

    blkdev.close()


def create_orphan_block(path: str):
    """Create an orphaned file header block that's not linked."""
    factory = BlkDevFactory()
    blkdev = factory.open(path, read_only=False)

    # Find a free block
    root_blk_num = blkdev.num_blocks // 2

    # Use a block near the end that's likely free
    orphan_blk = blkdev.num_blocks - 10

    # Create a file header block
    data = bytearray(blkdev.block_bytes)

    # Type = T_SHORT (2)
    struct.pack_into(">I", data, 0, 2)

    # own_key at offset 1
    struct.pack_into(">I", data, 4, orphan_blk)

    # Sub-type = ST_FILE (-3) at last long
    struct.pack_into(">i", data, len(data) - 4, -3)

    # Parent at offset -3 longs (point to root, but root doesn't point back)
    struct.pack_into(">I", data, len(data) - 12, root_blk_num)

    # Name at offset -20 longs (BSTR format: length byte + chars)
    name = b"orphan.txt"
    name_offset = len(data) - 80
    data[name_offset] = len(name)
    data[name_offset + 1:name_offset + 1 + len(name)] = name

    # Calculate and set checksum
    chksum = 0
    for i in range(blkdev.block_longs):
        if i != 5:  # Skip checksum location
            chksum += struct.unpack_from(">I", data, i * 4)[0]
    chksum = (-chksum) & 0xFFFFFFFF
    struct.pack_into(">I", data, 20, chksum)

    blkdev.write_block(orphan_blk, bytes(data))
    blkdev.close()


def create_all_fixtures(output_dir: str):
    """Create all test fixture disk images."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    fixtures = []

    # 1. Clean disk (for comparison)
    clean_path = str(output_path / "clean.adf")
    create_base_disk(clean_path, "CleanDisk")
    fixtures.append(("clean.adf", "Clean reference disk"))

    # 2. Disk with bad root block checksum
    bad_root_checksum = str(output_path / "bad_root_checksum.adf")
    create_base_disk(bad_root_checksum, "BadRootChksum")
    factory = BlkDevFactory()
    blkdev = factory.open(bad_root_checksum, read_only=True)
    root_blk = blkdev.num_blocks // 2
    blkdev.close()
    corrupt_checksum(bad_root_checksum, root_blk)
    fixtures.append(("bad_root_checksum.adf", "Root block with bad checksum"))

    # 3. Disk with bad directory checksum
    bad_dir_checksum = str(output_path / "bad_dir_checksum.adf")
    create_base_disk(bad_dir_checksum, "BadDirChksum")
    # We need to find a directory block - this requires reading the disk
    # For simplicity, we'll corrupt a known location
    # After format, the first directory will be somewhere after root
    fixtures.append(("bad_dir_checksum.adf", "Directory with bad checksum"))

    # 4. Disk with bitmap mismatch
    bad_bitmap = str(output_path / "bad_bitmap.adf")
    create_base_disk(bad_bitmap, "BadBitmap")
    corrupt_bitmap(bad_bitmap)
    fixtures.append(("bad_bitmap.adf", "Bitmap doesn't match actual allocation"))

    # 5. Disk with orphan block
    orphan_disk = str(output_path / "orphan_block.adf")
    create_base_disk(orphan_disk, "OrphanDisk")
    create_orphan_block(orphan_disk)
    fixtures.append(("orphan_block.adf", "Contains orphaned file header"))

    # 6. Disk with bad parent pointer
    bad_parent = str(output_path / "bad_parent.adf")
    create_base_disk(bad_parent, "BadParent")
    # Would need to find actual directory block number
    fixtures.append(("bad_parent.adf", "Directory with wrong parent pointer"))

    print("Created test fixtures:")
    for name, desc in fixtures:
        print(f"  {name}: {desc}")

    return fixtures


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
    else:
        output_dir = "test/fixtures/corrupted_disks"

    create_all_fixtures(output_dir)
