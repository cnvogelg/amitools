import pytest

from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.FSString import FSString
from amitools.fs.MetaInfo import MetaInfo
from amitools.fs.blkdev.ADFBlockDevice import ADFBlockDevice
from amitools.fs.block.CommentBlock import CommentBlock
import amitools.fs.DosType as DosType

DOS_TYPES = [DosType.DOS0 + n for n in range(8)]
DIRCACHE_DOS_TYPES = [DosType.DOS4, DosType.DOS5]
LONGNAME_DOS_TYPES = [DosType.DOS6, DosType.DOS7]


def dos_id(dos_type):
    return "DOS%d" % (dos_type - DosType.DOS0)


def create_volume(path, dos_type):
    blkdev = ADFBlockDevice(str(path))
    blkdev.create()
    volume = ADFSVolume(blkdev)
    volume.create(FSString("Test"), dos_type=dos_type)
    return blkdev, volume


def open_volume(path):
    blkdev = ADFBlockDevice(str(path))
    blkdev.open()
    volume = ADFSVolume(blkdev)
    volume.open()
    return blkdev, volume


def close_volume(blkdev, volume):
    volume.close()
    blkdev.close()


def get_comment(volume, path):
    return volume.get_path_name(FSString(path)).get_meta_info().get_comment()


def dircache_records(volume, path):
    node = volume.get_path_name(FSString(path))
    node.read()
    return [r for dcb in node.dcache_blks for r in dcb.records]


def entry_names(volume, path):
    node = volume.get_path_name(FSString(path))
    node.read()
    return sorted(e.name.get_unicode_name() for e in node.entries)


@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_comment_change_test(tmp_path, dos_type):
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    volume.write_file(b"data", FSString("file"))
    volume.create_dir(FSString("dir"))
    volume.get_path_name(FSString("file")).change_comment(FSString("file comment"))
    volume.get_path_name(FSString("dir")).change_comment(FSString("dir comment"))
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    assert get_comment(volume, "file") == FSString("file comment")
    assert get_comment(volume, "dir") == FSString("dir comment")
    close_volume(blkdev, volume)


@pytest.mark.parametrize("dos_type", DIRCACHE_DOS_TYPES, ids=dos_id)
def fs_comment_grow_dircache_test(tmp_path, dos_type):
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    volume.write_file(b"data", FSString("file"))
    node = volume.get_path_name(FSString("file"))
    node.change_comment(FSString("short"))
    node.change_comment(FSString("a much longer comment"))
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    assert get_comment(volume, "file") == FSString("a much longer comment")
    records = dircache_records(volume, "")
    assert [r.comment for r in records] == [FSString("a much longer comment")]
    close_volume(blkdev, volume)


def fill_dir(volume, count):
    for n in range(count):
        volume.write_file(b"x", FSString("dir/f%02d" % n))


def check_dircache(volume, path, comments):
    records = dircache_records(volume, path)
    assert sorted(r.name.get_unicode() for r in records) == entry_names(volume, path)
    for r in records:
        want = comments.get(r.name.get_unicode(), "")
        assert r.comment == FSString(want)
    # every linked dircache block is still allocated
    for dcb in volume.get_path_name(FSString(path)).dcache_blks:
        assert not volume.bitmap.get_bit(dcb.blk_num)


@pytest.mark.parametrize("dos_type", DIRCACHE_DOS_TYPES, ids=dos_id)
def fs_comment_grow_last_dircache_block_test(tmp_path, dos_type):
    # 17 records fill the first dircache block, the 18th starts a second one.
    # Growing that lone record must not lose it when its block is released.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    volume.create_dir(FSString("dir"))
    fill_dir(volume, 18)
    assert len(volume.get_path_name(FSString("dir")).dcache_blks) == 2
    comment = "c" * 79
    volume.get_path_name(FSString("dir/f17")).change_comment(FSString(comment))
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    assert get_comment(volume, "dir/f17") == FSString(comment)
    check_dircache(volume, "dir", {"f17": comment})
    close_volume(blkdev, volume)


@pytest.mark.parametrize("dos_type", DIRCACHE_DOS_TYPES, ids=dos_id)
def fs_comment_grow_first_dircache_block_test(tmp_path, dos_type):
    # Leave one record in the first of two dircache blocks, then grow it: the
    # directory's link to its first dircache block has to follow the move.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    volume.create_dir(FSString("dir"))
    fill_dir(volume, 18)
    for n in range(1, 17):
        volume.delete(FSString("dir/f%02d" % n))
    assert len(volume.get_path_name(FSString("dir")).dcache_blks) == 2
    volume.get_path_name(FSString("dir/f00")).change_comment(FSString("grown"))
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    assert get_comment(volume, "dir/f00") == FSString("grown")
    check_dircache(volume, "dir", {"f00": "grown"})
    close_volume(blkdev, volume)


@pytest.mark.parametrize("dos_type", DIRCACHE_DOS_TYPES, ids=dos_id)
def fs_dircache_delete_then_create_test(tmp_path, dos_type):
    # Deleting the only entry of the last dircache block releases that block;
    # a record created afterwards must land in a block that is still linked.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    volume.create_dir(FSString("dir"))
    fill_dir(volume, 18)
    volume.delete(FSString("dir/f17"))
    volume.write_file(b"x", FSString("dir/new_file_name"))
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    check_dircache(volume, "dir", {})
    close_volume(blkdev, volume)


@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_longname_empty_test(tmp_path, dos_type):
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    volume.write_file(b"data", FSString("file"))
    volume.create_dir(FSString("dir"))
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    assert get_comment(volume, "file") == FSString()
    assert get_comment(volume, "dir") == FSString()
    # on disk: name BSTR followed by an empty comment BSTR
    blk_num = volume.get_path_name(FSString("file")).block.blk_num
    data = blkdev.read_block(blk_num)
    nac = data[blkdev.block_bytes - 184 :]
    assert nac[:6] == b"\x04file\x00"
    close_volume(blkdev, volume)


@pytest.mark.parametrize(
    "name,comment",
    [("file", "given at creation"), ("n" * 60, "c" * 79)],
    ids=["inline", "comment_block"],
)
@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_longname_create_test(tmp_path, dos_type, name, comment):
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    meta_info = MetaInfo(protect=0, comment=FSString(comment))
    meta_info.set_current_as_mod_time()
    root = volume.get_root_dir()
    root.create_file(FSString(name), b"data", meta_info)
    root.create_dir(FSString(name + "_dir"), meta_info)
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    for path in (name, name + "_dir"):
        assert get_comment(volume, path) == FSString(comment)
        # the name and comment field must not spill past its 112 bytes
        data = blkdev.read_block(volume.get_path_name(FSString(path)).block.blk_num)
        end = blkdev.block_bytes - 72 + 4
        assert data[end : end + 8] == bytes(8)
    close_volume(blkdev, volume)


@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_longname_block_test(tmp_path, dos_type):
    # A 60 character name leaves no room for a 79 character comment in the
    # header, so the comment moves to a comment block, and back again.
    image = tmp_path / "test.adf"
    name = "n" * 60
    comment = "c" * 79
    blkdev, volume = create_volume(image, dos_type)
    volume.write_file(b"data", FSString(name))
    free = volume.get_free_blocks()
    volume.get_path_name(FSString(name)).change_comment(FSString(comment))
    assert volume.get_free_blocks() == free - 1
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    node = volume.get_path_name(FSString(name))
    assert get_comment(volume, name) == FSString(comment)
    cblk = CommentBlock(blkdev, node.block.comment_block_id)
    cblk.read()
    assert cblk.valid
    assert cblk.header_key == node.block.blk_num
    assert cblk.comment == FSString(comment)
    node.change_comment(FSString("short"))
    assert volume.get_free_blocks() == free
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    node = volume.get_path_name(FSString(name))
    assert node.block.comment_block_id == 0
    assert get_comment(volume, name) == FSString("short")
    close_volume(blkdev, volume)


@pytest.mark.parametrize(
    "comment_len,extra_blocks", [(60, 0), (61, 1)], ids=["fits", "comment_block"]
)
@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_longname_boundary_test(tmp_path, dos_type, comment_len, extra_blocks):
    # A 50 character name and a 60 character comment fill the 112 byte name
    # and comment field exactly; one more character needs a comment block.
    image = tmp_path / "test.adf"
    name = "n" * 50
    comment = "c" * comment_len
    blkdev, volume = create_volume(image, dos_type)
    volume.write_file(b"data", FSString(name))
    free = volume.get_free_blocks()
    volume.get_path_name(FSString(name)).change_comment(FSString(comment))
    assert volume.get_free_blocks() == free - extra_blocks
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    node = volume.get_path_name(FSString(name))
    assert (node.block.comment_block_id != 0) == bool(extra_blocks)
    assert get_comment(volume, name) == FSString(comment)
    close_volume(blkdev, volume)


@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_longname_block_delete_test(tmp_path, dos_type):
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    free = volume.get_free_blocks()
    volume.write_file(b"data", FSString("f" * 60))
    volume.create_dir(FSString("d" * 60))
    for name in ("f" * 60, "d" * 60):
        volume.get_path_name(FSString(name)).change_comment(FSString("c" * 79))
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    for name in ("f" * 60, "d" * 60):
        volume.delete(FSString(name))
    assert volume.get_free_blocks() == free
    close_volume(blkdev, volume)


@pytest.mark.parametrize("dos_type", [DosType.DOS0, DosType.DOS1], ids=dos_id)
def fs_comment_no_block_without_longname_test(tmp_path, dos_type):
    # Classic headers have a fixed 79 character comment field; never allocate
    # a long-name comment block for them, even for an oversized comment.
    image = tmp_path / "test.adf"
    name = "n" * 30
    comment = "c" * 81
    blkdev, volume = create_volume(image, dos_type)
    volume.write_file(b"data", FSString(name))
    free = volume.get_free_blocks()
    volume.get_path_name(FSString(name)).change_comment(FSString(comment))
    assert volume.get_free_blocks() == free
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    assert get_comment(volume, name) == FSString(comment[:79])
    close_volume(blkdev, volume)
