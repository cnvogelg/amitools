"""ADFS directory hard link (``ST_LINKDIR``) tests.

A directory hard link is stored as its own directory block whose
``real_entry`` points at the directory it names. amitools reads one written by
another tool and follows it on lookup, but never creates one (AmigaDOS does
not let ``MakeLink`` link a directory).
"""

import pytest

from amitools.fs import DosType
from amitools.fs.ADFSHardLinkDir import ADFSHardLinkDir
from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.FSError import DELETE_NOT_ALLOWED, LINK_NOT_ALLOWED, FSError
from amitools.fs.FSString import FSString
from amitools.fs.FileName import FileName
from amitools.fs.block.Block import Block
from amitools.fs.block.UserDirBlock import UserDirBlock
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


def add_dir_link(volume, blkdev, name, target_dir):
    """write a ``ST_LINKDIR`` block by hand and put it in the root's hash chain"""
    root = volume.root_dir
    root.ensure_entries()
    fn = FileName(name, is_intl=volume.is_intl, is_longname=volume.is_longname)
    hash_idx = fn.hash(hash_size=root.hash_size)
    old_head = root.block.hash_table[hash_idx]
    blk_num = volume.bitmap.alloc_n(1)[0]
    ud = UserDirBlock(blkdev, blk_num, volume.is_longname, sub_type=Block.ST_LINKDIR)
    ud.create(
        root.block.blk_num,
        name,
        hash_chain=old_head,
        real_entry=target_dir.block.blk_num,
    )
    ud.write()
    root.block.hash_table[hash_idx] = blk_num
    root.block.write()
    volume.bitmap.write()
    return blk_num


def fs_linkdir_read_test(tmp_path):
    volume, blkdev = make_volume(tmp_path)
    volume.create_dir(FSString("realdir"))
    volume.write_file(b"hi", FSString("realdir/inner"))
    real = volume.get_path_name(FSString("realdir"))
    add_dir_link(volume, blkdev, FSString("dirlink"), real)
    volume.close()

    check = reopen(blkdev)
    # the parent directory stays readable: the link is a real entry
    assert check.root_dir.valid
    entries = {e.name.get_unicode_name(): e for e in check.root_dir.get_entries()}
    assert isinstance(entries["dirlink"], ADFSHardLinkDir)
    # a lookup follows the link to the real directory
    node = check.get_path_name(FSString("dirlink"))
    assert node is not None
    assert node.is_dir()
    assert node.block.blk_num == real.block.blk_num
    # and further path components resolve through it
    assert check.read_file(FSString("dirlink/inner")) == b"hi"
    # the link itself is reachable without following it
    link = check.get_link_path_name(FSString("dirlink"))
    assert isinstance(link, ADFSHardLinkDir)
    assert link.get_real_node().block.name.get_unicode() == "realdir"
    assert link.get_detail_str() == "linkdir=#%d" % real.block.blk_num
    assert "linkdir=#" in link.get_list_str(detail=True)


@pytest.mark.parametrize("dos_type", [DosType.DOS0, DosType.DOS5])
def fs_linkdir_read_dos_type_test(tmp_path, dos_type):
    volume, blkdev = make_volume(tmp_path, dos_type=dos_type)
    volume.create_dir(FSString("realdir"))
    real = volume.get_path_name(FSString("realdir"))
    add_dir_link(volume, blkdev, FSString("dirlink"), real)
    volume.close()
    check = reopen(blkdev)
    node = check.get_path_name(FSString("dirlink"))
    assert node is not None and node.is_dir()


def fs_linkdir_create_refused_test(tmp_path):
    volume, _ = make_volume(tmp_path)
    volume.create_dir(FSString("realdir"))
    real = volume.get_path_name(FSString("realdir"))
    with pytest.raises(FSError) as exc:
        volume.create_hard_link(FSString("dirlink"), real)
    assert exc.value.code == LINK_NOT_ALLOWED


def fs_linkdir_delete_refused_test(tmp_path):
    volume, blkdev = make_volume(tmp_path)
    volume.create_dir(FSString("realdir"))
    real = volume.get_path_name(FSString("realdir"))
    add_dir_link(volume, blkdev, FSString("dirlink"), real)
    volume.close()
    check = reopen(blkdev)
    link = check.get_link_path_name(FSString("dirlink"))
    with pytest.raises(FSError) as exc:
        link.delete()
    assert exc.value.code == DELETE_NOT_ALLOWED
