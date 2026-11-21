"""ADFS hard link tests.

A hard link (``ST_LINKFILE``) is its own file header block whose ``real_entry``
(long ``-11``) points at the file it names and whose ``next_link`` (long ``-10``)
chains the file's links newest first. The link shares the real file's data and
metadata; a lookup follows it, and deleting the link frees only its own block.
"""

import struct

import pytest

from amitools.fs import DosType
from amitools.fs.ADFSHardLink import ADFSHardLink
from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.FSError import (
    DELETE_NOT_ALLOWED,
    LINK_NOT_ALLOWED,
    NAME_ALREADY_EXISTS,
    FSError,
)
from amitools.fs.FSString import FSString
from amitools.fs.MetaInfo import MetaInfo
from amitools.fs.blkdev.ADFBlockDevice import ADFBlockDevice
from amitools.fs.block.Block import Block


def make_volume(tmp_path, dos_type=DosType.DOS0):
    blkdev = ADFBlockDevice(str(tmp_path / "v.adf"))
    blkdev.create()
    volume = ADFSVolume(blkdev)
    volume.create(FSString("work"), dos_type=dos_type)
    return volume, blkdev


def reopen(blkdev):
    volume = ADFSVolume(blkdev)
    volume.open()
    return volume


def raw_link_fields(blkdev, blk_num):
    """the sec_type, real_entry and next_link of a link block on disk"""
    data = blkdev.read_block(blk_num)
    longs = blkdev.block_longs
    sub_type = struct.unpack_from(">I", data, (longs - 1) * 4)[0]
    real = struct.unpack_from(">I", data, (longs - 11) * 4)[0]
    nxt = struct.unpack_from(">I", data, (longs - 10) * 4)[0]
    return sub_type, real, nxt


def entries(volume):
    return {e.name.get_unicode_name(): e for e in volume.root_dir.get_entries()}


@pytest.mark.parametrize(
    "dos_type", [DosType.DOS0, DosType.DOS5, DosType.DOS6], ids=["DOS0", "DOS5", "DOS6"]
)
def create_read_reopen_test(tmp_path, dos_type):
    volume, blkdev = make_volume(tmp_path, dos_type)
    volume.write_file(b"data", FSString("target"))
    target = volume.get_file_path_name(FSString("target"))
    link = volume.create_hard_link(FSString("link"), target)
    assert isinstance(link, ADFSHardLink)
    # both names are listed and see the same data
    es = entries(volume)
    assert set(es) == {"target", "link"}
    assert volume.read_file(FSString("link")) == b"data"
    assert volume.read_file(FSString("target")) == b"data"
    # get_link_path_name returns the link itself, not the target
    node = volume.get_link_path_name(FSString("link"))
    assert isinstance(node, ADFSHardLink)
    assert node.get_real_node().block.blk_num == target.block.blk_num
    # the real file chains the link; the link points back at the real file
    assert target.block.next_link == link.block.blk_num
    link_num = link.block.blk_num
    target_num = target.block.blk_num
    volume.close()

    # reopen: the link is read back and still resolves
    check = reopen(blkdev)
    node = check.get_link_path_name(FSString("link"))
    assert isinstance(node, ADFSHardLink)
    assert node.get_real_node().block.blk_num == target_num
    assert check.read_file(FSString("link")) == b"data"
    # on disk the block is a T_SHORT header with sec_type ST_LINKFILE,
    # real_entry = target block and next_link = 0 (only link)
    sub_type, real, nxt = raw_link_fields(blkdev, link_num)
    assert sub_type == Block.ST_LINKFILE
    assert real == target_num
    assert nxt == 0
    # the real file keeps its data and the link in its chain
    assert check.get_file_path_name(FSString("target")).block.next_link == link_num

    # deleting the link keeps the target and its data
    check.delete(FSString("link"))
    assert set(entries(check)) == {"target"}
    assert check.read_file(FSString("target")) == b"data"
    assert check.get_file_path_name(FSString("target")).block.next_link == 0
    blkdev.close()


def link_chain_newest_first_test(tmp_path):
    volume, blkdev = make_volume(tmp_path)
    volume.write_file(b"x", FSString("t"))
    target = volume.get_file_path_name(FSString("t"))
    first = volume.create_hard_link(FSString("l1"), target)
    second = volume.create_hard_link(FSString("l2"), target)
    # the real file points at the newest link; the older link is at its tail
    assert target.block.next_link == second.block.blk_num
    assert second.block.next_link == first.block.blk_num
    assert first.block.next_link == 0
    volume.close()

    # deleting the oldest link relinks the middle one to its tail
    check = reopen(blkdev)
    check.delete(FSString("l1"))
    t = check.get_file_path_name(FSString("t"))
    l2 = check.get_link_path_name(FSString("l2"))
    assert t.block.next_link == l2.block.blk_num
    assert l2.block.next_link == 0
    # deleting the last link clears the real file's chain
    check.delete(FSString("l2"))
    t = check.get_file_path_name(FSString("t"))
    assert t.block.next_link == 0
    check.delete(FSString("t"))
    assert entries(check) == {}
    blkdev.close()


def real_file_delete_refused_while_linked_test(tmp_path):
    volume, blkdev = make_volume(tmp_path)
    volume.write_file(b"x", FSString("t"))
    target = volume.get_file_path_name(FSString("t"))
    volume.create_hard_link(FSString("l"), target)
    with pytest.raises(FSError) as exc:
        volume.delete(FSString("t"))
    assert exc.value.code == DELETE_NOT_ALLOWED
    # the link is gone but the real file stays while a link names it
    volume.delete(FSString("l"))
    volume.delete(FSString("t"))
    assert entries(volume) == {}
    volume.close()
    blkdev.close()


def link_into_other_dir_test(tmp_path):
    volume, blkdev = make_volume(tmp_path)
    volume.create_dir(FSString("dir"))
    volume.write_file(b"data", FSString("dir/target"))
    target = volume.get_file_path_name(FSString("dir/target"))
    volume.create_hard_link(FSString("rootlink"), target)
    assert volume.read_file(FSString("rootlink")) == b"data"
    assert set(entries(volume)) == {"dir", "rootlink"}
    # the link is deleted from its own directory; the target stays
    volume.delete(FSString("rootlink"))
    assert volume.read_file(FSString("dir/target")) == b"data"
    volume.close()
    blkdev.close()


def link_to_dir_refused_test(tmp_path):
    volume, blkdev = make_volume(tmp_path)
    volume.create_dir(FSString("dir"))
    with pytest.raises(FSError) as exc:
        volume.create_hard_link(
            FSString("dlink"), volume.get_dir_path_name(FSString("dir"))
        )
    assert exc.value.code == LINK_NOT_ALLOWED
    assert set(entries(volume)) == {"dir"}
    volume.close()
    blkdev.close()


def link_name_taken_test(tmp_path):
    volume, blkdev = make_volume(tmp_path)
    volume.write_file(b"x", FSString("t"))
    volume.write_file(b"y", FSString("l"))
    target = volume.get_file_path_name(FSString("t"))
    with pytest.raises(FSError) as exc:
        volume.create_hard_link(FSString("l"), target)
    assert exc.value.code == NAME_ALREADY_EXISTS
    volume.close()
    blkdev.close()


def stale_real_node_write_keeps_chain_test(tmp_path):
    """a node holding the chain as it was read must not write it back after
    the chain changed: only a real chain change writes the link fields"""
    volume, blkdev = make_volume(tmp_path)
    volume.write_file(b"data", FSString("t"))
    target = volume.get_file_path_name(FSString("t"))
    link = volume.create_hard_link(FSString("l"), target)
    link_num = link.block.blk_num
    volume.close()

    check = reopen(blkdev)
    # the real file through the link is a second instance of the directory's
    # entry, holding the chain (l) as it was when the link was read
    stale = check.get_link_path_name(FSString("l")).get_real_node()
    assert stale.block.next_link == link_num
    check.delete(FSString("l"))
    # a write through the stale instance must not put the deleted link back
    stale.change_meta_info(MetaInfo(protect=0, comment=FSString("changed")))
    _, _, nxt = raw_link_fields(blkdev, stale.block.blk_num)
    assert nxt == 0
    assert check.get_file_path_name(FSString("t")).block.next_link == 0
    check.close()
    blkdev.close()


def plain_file_has_no_link_fields_test(tmp_path):
    volume, blkdev = make_volume(tmp_path)
    volume.write_file(b"x", FSString("t"))
    node = volume.get_file_path_name(FSString("t"))
    assert node.block.real_entry == 0
    assert node.block.next_link == 0
    volume.close()
    blkdev.close()
