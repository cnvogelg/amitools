"""ADFS soft link tests.

A soft link (``ST_SOFTLINK``) is a file header block with no data blocks
whose target is a NUL-terminated C string at long 6.
``ADFSVolume.create_soft_link`` writes one and ``get_path_name`` follows it
transparently, while ``get_link_path_name`` returns the link itself.
"""

import struct

import pytest

from amitools.fs import DosType
from amitools.fs.ADFSSoftLink import ADFSSoftLink
from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.FSError import TOO_MANY_LEVELS, FSError
from amitools.fs.FSString import FSString
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
    """the sec_type and the long-6 C string of a link block on disk"""
    data = blkdev.read_block(blk_num)
    sub_type = struct.unpack_from(">I", data, (blkdev.block_longs - 1) * 4)[0]
    target = data[24:].split(b"\0", 1)[0]
    return sub_type, target


@pytest.mark.parametrize(
    "dos_type", [DosType.DOS0, DosType.DOS5, DosType.DOS6], ids=["DOS0", "DOS5", "DOS6"]
)
def test_create_read_reopen(tmp_path, dos_type):
    volume, blkdev = make_volume(tmp_path, dos_type)
    volume.write_file(b"data", FSString("target"))
    volume.create_soft_link(FSString("link"), FSString("target"))
    # the link is listed as a soft link node and keeps its target
    node = volume.get_link_path_name(FSString("link"))
    assert isinstance(node, ADFSSoftLink)
    assert node.get_target().get_unicode() == "target"
    entries = volume.root_dir.get_entries()
    assert any(
        isinstance(e, ADFSSoftLink) and e.name.get_unicode_name() == "link"
        for e in entries
    )
    # a normal lookup follows the link to the target file
    assert volume.read_file(FSString("link")) == b"data"
    blk_num = node.block.blk_num
    volume.close()
    # reopen: the target is preserved
    check = reopen(blkdev)
    node = check.get_link_path_name(FSString("link"))
    assert isinstance(node, ADFSSoftLink)
    assert node.get_target().get_unicode() == "target"
    assert check.read_file(FSString("link")) == b"data"
    # on disk the block is a T_SHORT header with sec_type ST_SOFTLINK and
    # the target as a NUL-terminated C string at long 6
    sub_type, target = raw_link_fields(blkdev, blk_num)
    assert sub_type == Block.ST_SOFTLINK
    assert target == b"target"
    blkdev.close()


def test_link_to_dir(tmp_path):
    volume, blkdev = make_volume(tmp_path)
    volume.create_dir(FSString("dir"))
    volume.write_file(b"x", FSString("dir/target"))
    volume.create_soft_link(FSString("link"), FSString("dir"))
    # a path through the link resolves inside the target directory
    assert volume.read_file(FSString("link/target")) == b"x"
    assert volume.get_dir_path_name(FSString("link")) is not None
    # the link itself is still returned by get_link_path_name
    assert isinstance(volume.get_link_path_name(FSString("link")), ADFSSoftLink)
    volume.close()
    blkdev.close()


def test_relative_parent_target(tmp_path):
    volume, blkdev = make_volume(tmp_path)
    volume.create_dir(FSString("dir"))
    volume.write_file(b"up", FSString("target"))
    # a relative target is resolved from the link's own directory
    volume.create_soft_link(FSString("dir/up"), FSString("../target"))
    assert volume.read_file(FSString("dir/up")) == b"up"
    volume.close()
    blkdev.close()


def test_absolute_target(tmp_path):
    volume, blkdev = make_volume(tmp_path)
    volume.create_dir(FSString("dir"))
    volume.write_file(b"abs", FSString("target"))
    # a target that starts with '/' is volume-absolute
    volume.create_soft_link(FSString("dir/abs"), FSString("/target"))
    assert volume.read_file(FSString("dir/abs")) == b"abs"
    volume.close()
    blkdev.close()


def test_link_depth_cap(tmp_path):
    volume, blkdev = make_volume(tmp_path)
    volume.write_file(b"end", FSString("target"))
    # 15 links in a row still resolve
    for i in range(15):
        nxt = "m%d" % (i + 1) if i < 14 else "target"
        volume.create_soft_link(FSString("m%d" % i), FSString(nxt))
    assert volume.read_file(FSString("m0")) == b"end"
    # a 16th link in the chain exceeds the dos.library cap
    volume.create_soft_link(FSString("m15"), FSString("m0"))
    with pytest.raises(FSError) as exc:
        volume.get_path_name(FSString("m15"))
    assert exc.value.code == TOO_MANY_LEVELS
    volume.close()
    blkdev.close()
