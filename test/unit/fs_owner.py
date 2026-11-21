"""ADFS entry owner (UID/GID) tests.

Every entry block stores a user id and a group id packed into the long at
``-49`` (uid in the high 16 bits, gid in the low 16). The FS layer reads and
writes it, keeps it in the directory cache record, and exposes it through
``ADFSNode.change_owner`` / ``MetaInfo``.
"""

import struct

import pytest

from amitools.fs import DosType
from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.FSString import FSString
from amitools.fs.blkdev.ADFBlockDevice import ADFBlockDevice


def make_volume(tmp_path, name="work", dos_type=DosType.DOS0):
    blkdev = ADFBlockDevice(str(tmp_path / "v.adf"))
    blkdev.create()
    volume = ADFSVolume(blkdev)
    volume.create(FSString(name), dos_type=dos_type)
    return volume, blkdev


def reopen(blkdev):
    volume = ADFSVolume(blkdev)
    volume.open()
    return volume


def owner_of(node):
    return node.meta_info.get_owner_uid(), node.meta_info.get_owner_gid()


def fs_owner_default_test(tmp_path):
    volume, _ = make_volume(tmp_path)
    volume.write_file(b"x", FSString("f"))
    volume.create_dir(FSString("d"))
    assert owner_of(volume.get_path_name(FSString("f"))) == (0, 0)
    assert owner_of(volume.get_path_name(FSString("d"))) == (0, 0)


@pytest.mark.parametrize(
    "dos_type",
    [DosType.DOS0, DosType.DOS3, DosType.DOS5, DosType.DOS7],
    ids=["ofs", "ffs", "dircache", "longname"],
)
def fs_owner_roundtrip_test(tmp_path, dos_type):
    volume, blkdev = make_volume(tmp_path, dos_type=dos_type)
    volume.write_file(b"hello", FSString("f"))
    volume.create_dir(FSString("d"))
    node = volume.get_path_name(FSString("f"))
    node.change_owner(0x1234, 0x5678)
    volume.get_path_name(FSString("d")).change_owner(1, 2)
    check = reopen(blkdev)
    assert owner_of(check.get_path_name(FSString("f"))) == (0x1234, 0x5678)
    assert owner_of(check.get_path_name(FSString("d"))) == (1, 2)


def fs_owner_hand_written_test(tmp_path):
    """a value written by hand at long -49 is read back"""
    volume, blkdev = make_volume(tmp_path)
    volume.write_file(b"x", FSString("f"))
    node = volume.get_path_name(FSString("f"))
    blk_num = node.block.blk_num
    longs = blkdev.block_longs
    data = bytearray(blkdev.read_block(blk_num))
    # uid high 16, gid low 16
    struct.pack_into(">I", data, (longs - 49) * 4, 0xABCD_1234)
    # recompute the block checksum (long 5), which the patch invalidated
    chksum = 0
    for i in range(longs):
        if i != 5:
            chksum = (chksum + struct.unpack_from(">I", data, i * 4)[0]) & 0xFFFFFFFF
    struct.pack_into(">I", data, 5 * 4, (-chksum) & 0xFFFFFFFF)
    blkdev.write_block(blk_num, bytes(data))
    check = reopen(blkdev)
    assert owner_of(check.get_path_name(FSString("f"))) == (0xABCD, 0x1234)


def fs_owner_dircache_record_test(tmp_path):
    volume, blkdev = make_volume(tmp_path, dos_type=DosType.DOS5)
    volume.write_file(b"hello", FSString("f"))
    node = volume.get_path_name(FSString("f"))
    node.change_owner(7, 8)
    check = reopen(blkdev)
    node = check.get_path_name(FSString("f"))
    record = check.root_dir.get_dircache_record(node)
    assert record is not None
    assert (record.owner_uid, record.owner_gid) == (7, 8)
    # the cached listing shows the same ids as the header
    assert owner_of(node) == (7, 8)


def fs_owner_change_keeps_other_meta_test(tmp_path):
    """a comment or protection change must not reset the owner"""
    volume, _ = make_volume(tmp_path)
    volume.write_file(b"x", FSString("f"))
    node = volume.get_path_name(FSString("f"))
    node.change_owner(11, 22)
    node.change_comment(FSString("hello"))
    node.change_protect(0x123)
    assert owner_of(node) == (11, 22)
    node.change_owner(0, 0)
    assert owner_of(node) == (0, 0)
    # the comment and protection are still the ones that were set
    assert node.meta_info.get_comment().get_unicode() == "hello"
    assert node.meta_info.get_protect() == 0x123


def fs_owner_display_test(tmp_path):
    volume, _ = make_volume(tmp_path)
    volume.write_file(b"x", FSString("f"))
    node = volume.get_path_name(FSString("f"))
    # a 0/0 owner is not shown, so plain listings stay unchanged
    assert node.meta_info.get_owner_str() == ""
    assert "0 0" not in node.get_list_str(detail=True)
    node.change_owner(3, 4)
    assert node.meta_info.get_owner_str() == "3 4"
    assert "3 4" in node.get_list_str(detail=True)
    assert "3 4" in node.get_list_str()
