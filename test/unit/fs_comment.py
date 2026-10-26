import struct

import pytest

from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.FSError import FSError, INVALID_COMMENT, NO_FREE_BLOCKS
from amitools.fs.FSString import FSString
from amitools.fs.FileName import FileName
from amitools.fs.Imager import Imager
from amitools.fs.MetaInfo import MetaInfo
from amitools.fs.blkdev.ADFBlockDevice import ADFBlockDevice
from amitools.fs.block.Block import Block
from amitools.fs.block.CommentBlock import CommentBlock
from amitools.fs.block.FileHeaderBlock import FileHeaderBlock
from amitools.fs.block.RootBlock import RootBlock
from amitools.fs.block.UserDirBlock import UserDirBlock
from amitools.fs.validate.Log import Log
from amitools.fs.validate.Validator import Validator
import amitools.fs.DosType as DosType
from amitools.tools.xdftool import main as xdftool_main

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


def validate(path):
    blkdev = ADFBlockDevice(str(path), read_only=True)
    blkdev.open()
    validator = Validator(blkdev, Log.WARN)
    assert validator.scan_boot()[0]
    assert validator.scan_root()
    validator.scan_dir_tree()
    validator.scan_files()
    validator.scan_bitmap()
    blkdev.close()
    return [str(e) for e in validator.log.entries]


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


def fill_disk(volume, keep=0):
    """use up all free blocks of a volume but keep of them"""
    # a file takes a header, its data blocks and a file list block for
    # every further ptrs data blocks; the largest one that fits leaves at
    # most one block over, which an empty file takes
    avail = volume.get_free_blocks() - keep
    ptrs = volume.blkdev.block_longs - 56
    num = avail - 1
    while 1 + num + (num - 1) // ptrs > avail:
        num -= 1
    data_bytes = volume.blkdev.block_bytes
    if not volume.is_ffs:
        data_bytes -= 24
    volume.write_file(bytes(num * data_bytes), FSString("filler"))
    if volume.get_free_blocks() > keep:
        volume.write_file(b"", FSString("empty"))
    assert volume.get_free_blocks() == keep


@pytest.mark.parametrize("disk_full", [False, True], ids=["room", "full"])
@pytest.mark.parametrize("dos_type", DIRCACHE_DOS_TYPES, ids=dos_id)
def fs_comment_grow_dircache_disk_full_test(tmp_path, dos_type, disk_full):
    # 17 records fill a dircache block, so a record that grows moves to a
    # new one. Without a free block the change has to fail as a whole and
    # keep the record: FastFileSystem lists only the entries it caches.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    volume.create_dir(FSString("dir"))
    fill_dir(volume, 17)
    assert len(volume.get_path_name(FSString("dir")).dcache_blks) == 1
    fill_disk(volume, keep=0 if disk_full else 1)
    node = volume.get_path_name(FSString("dir/f00"))
    comment = "c" * 79
    if disk_full:
        with pytest.raises(FSError) as error:
            node.change_comment(FSString(comment))
        assert error.value.code == NO_FREE_BLOCKS
        comment = ""
    else:
        node.change_comment(FSString(comment))
    assert node.get_meta_info().get_comment() == FSString(comment)
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    assert get_comment(volume, "dir/f00") == FSString(comment)
    check_dircache(volume, "dir", {"f00": comment})
    close_volume(blkdev, volume)
    assert validate(image) == []


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


@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_longname_block_usage_test(tmp_path, dos_type):
    # Block usage, block lists and the bitmap drawing include comment blocks.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    volume.write_file(b"data", FSString("f" * 60))
    volume.create_dir(FSString("d" * 60))
    root = volume.get_root_dir()
    root_usage = root.get_block_usage(all=True)
    for name in ("f" * 60, "d" * 60):
        node = volume.get_path_name(FSString(name))
        data, fs = node.get_block_usage()
        node.change_comment(FSString("c" * 79))
        blk_num = node.block.comment_block_id
        assert node.get_block_usage() == (data, fs + 1)
        assert blk_num in [b.blk_num for b in node.get_blocks()]
        bm = volume.bitmap.create_draw_bitmap()
        node.draw_on_bitmap(bm)
        assert bm[blk_num] == ord("c")
    assert root.get_block_usage(all=True) == (root_usage[0], root_usage[1] + 2)
    close_volume(blkdev, volume)


@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_root_dir_block_nums_test(tmp_path, dos_type):
    # The root block has no comment block. The root directory lists its own
    # block and, on DOS4/5, its dircache block.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    root = volume.get_root_dir()
    want = [880, 866] if dos_type in DIRCACHE_DOS_TYPES else [880]
    assert root.get_block_nums() == want
    assert [b.blk_num for b in root.get_blocks()] == want
    assert root.get_block_usage() == (0, len(want))
    close_volume(blkdev, volume)


@pytest.mark.parametrize("keep", [2, 3], ids=["no_room", "room"])
@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_longname_create_disk_full_test(tmp_path, dos_type, keep):
    # A one block file whose comment needs a comment block takes three
    # blocks. With only two left, nothing may be created.
    image = tmp_path / "test.adf"
    name = "n" * 60
    comment = "c" * 79
    blkdev, volume = create_volume(image, dos_type)
    fill_disk(volume, keep)
    meta_info = MetaInfo(protect=0, comment=FSString(comment))
    meta_info.set_current_as_mod_time()
    root = volume.get_root_dir()
    if keep == 2:
        with pytest.raises(FSError) as error:
            root.create_file(FSString(name), b"data", meta_info)
        assert error.value.code == NO_FREE_BLOCKS
        assert volume.get_free_blocks() == 2
    else:
        root.create_file(FSString(name), b"data", meta_info)
        assert volume.get_free_blocks() == 0
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    if keep == 2:
        assert volume.get_path_name(FSString(name)) is None
    else:
        assert get_comment(volume, name) == FSString(comment)
    close_volume(blkdev, volume)
    assert validate(image) == []


def fail_write(self):
    raise IOError("write failed")


@pytest.mark.parametrize("old_comment", ["", "o" * 79], ids=["new_block", "own_block"])
@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_block_write_fails_test(tmp_path, dos_type, old_comment, monkeypatch):
    # The header may point to a comment block only once that is written. A
    # block allocated for the comment is released again when the write
    # fails, while a comment block the entry already has stays its own.
    image = tmp_path / "test.adf"
    name = "n" * 60
    blkdev, volume = create_volume(image, dos_type)
    volume.write_file(b"data", FSString(name))
    node = volume.get_path_name(FSString(name))
    if old_comment:
        node.change_comment(FSString(old_comment))
    blk_num = node.block.comment_block_id
    free = volume.get_free_blocks()

    with monkeypatch.context() as patch:
        patch.setattr(CommentBlock, "write", fail_write)
        with pytest.raises(IOError):
            node.change_comment(FSString("c" * 79))
    assert node.block.comment_block_id == blk_num
    assert node.get_meta_info().get_comment() == FSString(old_comment)
    assert volume.get_free_blocks() == free
    node.change_protect(0x0F)
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    assert get_comment(volume, name) == FSString(old_comment)
    close_volume(blkdev, volume)
    assert validate(image) == []


@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_block_create_write_fails_test(tmp_path, dos_type, monkeypatch):
    # An entry whose comment block cannot be written is not created, and
    # the blocks allocated for it are released again.
    image = tmp_path / "test.adf"
    name = "n" * 60
    blkdev, volume = create_volume(image, dos_type)
    free = volume.get_free_blocks()
    meta_info = MetaInfo(protect=0, comment=FSString("c" * 79))
    meta_info.set_current_as_mod_time()
    root = volume.get_root_dir()

    with monkeypatch.context() as patch:
        patch.setattr(CommentBlock, "write", fail_write)
        with pytest.raises(IOError):
            root.create_file(FSString(name), b"data", meta_info)
        with pytest.raises(IOError):
            root.create_dir(FSString(name + "_dir"), meta_info)
    assert volume.get_free_blocks() == free
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    assert volume.get_path_name(FSString(name)) is None
    assert volume.get_path_name(FSString(name + "_dir")) is None
    close_volume(blkdev, volume)
    assert validate(image) == []


KEEPER = "k" * 60
VICTIM = "v" * 60


FOREIGN_POINTERS = [
    "other_entry",
    "file_header",
    "out_of_range",
    "free_block",
    "data_block",
]


def make_foreign_comment_pointer(image, dos_type, kind):
    """a long name volume whose VICTIM points to a comment block that is
    not its own; returns the block number it points to"""
    blkdev, volume = create_volume(image, dos_type)
    volume.write_file(b"keep", FSString(KEEPER))
    keeper = volume.get_path_name(FSString(KEEPER))
    keeper.change_comment(FSString("k" * 79))
    volume.write_file(b"data", FSString(VICTIM))
    victim = volume.get_path_name(FSString(VICTIM))
    target = {
        "other_entry": keeper.block.comment_block_id,
        "file_header": keeper.block.blk_num,
        "out_of_range": blkdev.num_blocks + 1,
        "free_block": blkdev.num_blocks - 1,
        "data_block": keeper.data_blk_nums[0],
    }[kind]
    if kind == "free_block":
        assert volume.bitmap.get_bit(target)
    victim_num = victim.block.blk_num
    close_volume(blkdev, volume)

    blkdev = ADFBlockDevice(str(image))
    blkdev.open()
    if kind == "free_block":
        # data left over in a free block, not a valid block
        blkdev.write_block(target, b"\xa5" * blkdev.block_bytes)
    hdr = FileHeaderBlock(blkdev, victim_num, is_longname=True)
    hdr.read()
    hdr.comment_block_id = target
    hdr.write()
    blkdev.close()
    return target


@pytest.mark.parametrize("op", ["delete", "shrink", "grow"])
@pytest.mark.parametrize("kind", FOREIGN_POINTERS)
@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_block_not_owned_test(tmp_path, dos_type, kind, op):
    # An entry frees or rewrites only its own comment block. Any other
    # pointer counts as no comment block.
    image = tmp_path / "test.adf"
    target = make_foreign_comment_pointer(image, dos_type, kind)
    blkdev, volume = open_volume(image)
    in_range = target < blkdev.num_blocks
    if in_range:
        before = (volume.bitmap.get_bit(target), bytes(blkdev.read_block(target)))
    assert get_comment(volume, VICTIM) == FSString()
    node = volume.get_path_name(FSString(VICTIM))
    if op == "delete":
        volume.delete(FSString(VICTIM))
    elif op == "shrink":
        node.change_comment(FSString("short"))
    else:
        node.change_comment(FSString("g" * 79))
        assert node.block.comment_block_id not in (0, target)
    if in_range:
        after = (volume.bitmap.get_bit(target), bytes(blkdev.read_block(target)))
        assert after == before
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    assert get_comment(volume, KEEPER) == FSString("k" * 79)
    assert volume.read_file(FSString(KEEPER)) == b"keep"
    if op == "delete":
        assert volume.get_path_name(FSString(VICTIM)) is None
    else:
        want = "short" if op == "shrink" else "g" * 79
        assert get_comment(volume, VICTIM) == FSString(want)
    close_volume(blkdev, volume)
    assert validate(image) == []


@pytest.mark.parametrize("kind", FOREIGN_POINTERS)
@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_block_not_owned_kept_test(tmp_path, dos_type, kind):
    # A change that leaves the comment alone writes the header back without
    # a pointer to a block that is not the entry's comment block: that
    # block is, or may become, another entry's, as when the next file takes
    # the blocks of KEEPER once it is deleted.
    image = tmp_path / "test.adf"
    make_foreign_comment_pointer(image, dos_type, kind)
    blkdev, volume = open_volume(image)
    free = volume.get_free_blocks()
    node = volume.get_path_name(FSString(VICTIM))
    assert node.get_block_nums() == [node.block.blk_num] + node.data_blk_nums
    assert node.get_block_usage() == (1, 1)
    node.change_protect(0x0F)
    assert volume.get_free_blocks() == free
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    node = volume.get_path_name(FSString(VICTIM))
    assert node.block.comment_block_id == 0
    volume.delete(FSString(KEEPER))
    volume.write_file(b"g" * 3000, FSString("g"))
    close_volume(blkdev, volume)
    assert validate(image) == []


def make_victim_comment_block(image, dos_type):
    """a long name volume whose VICTIM has a comment in a comment block;
    returns the block numbers of its header and comment block"""
    blkdev, volume = create_volume(image, dos_type)
    volume.write_file(b"data", FSString(VICTIM))
    victim = volume.get_path_name(FSString(VICTIM))
    victim.change_comment(FSString("v" * 79))
    nums = victim.block.blk_num, victim.block.comment_block_id
    close_volume(blkdev, volume)
    return nums


def flip_comment_byte(image, blk_num):
    """invert a byte of the comment in comment block blk_num, which makes
    its checksum bad: twice restores it"""
    blkdev = ADFBlockDevice(str(image))
    blkdev.open()
    data = bytearray(blkdev.read_block(blk_num))
    data[30] ^= 0xFF
    blkdev.write_block(blk_num, data)
    blkdev.close()


@pytest.mark.parametrize("op", ["protect", "delete", "shrink", "grow"])
@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_block_bad_checksum_test(tmp_path, dos_type, op):
    # A comment block that reads as the entry's own apart from its checksum
    # is still the entry's. Its comment cannot be read, but a protection
    # change keeps the pointer, so that the comment is back once the block
    # is repaired; a delete frees the block, a comment that needs a comment
    # block rewrites it, and a shorter comment frees it.
    image = tmp_path / "test.adf"
    hdr_num, target = make_victim_comment_block(image, dos_type)
    flip_comment_byte(image, target)

    blkdev, volume = open_volume(image)
    free = volume.get_free_blocks()
    assert get_comment(volume, VICTIM) == FSString()
    node = volume.get_path_name(FSString(VICTIM))
    assert node.get_block_nums() == [hdr_num, target] + node.data_blk_nums
    assert node.get_block_usage() == (1, 2)
    # but it cannot be decoded, so get_blocks() leaves it out
    assert [b.blk_num for b in node.get_blocks(with_data=False)] == [hdr_num]
    if op == "protect":
        node.change_protect(0x0F)
    elif op == "delete":
        volume.delete(FSString(VICTIM))
    elif op == "shrink":
        node.change_comment(FSString("short"))
    else:
        node.change_comment(FSString("g" * 79))
    freed = {"protect": 0, "delete": 3, "shrink": 1, "grow": 0}[op]
    assert volume.get_free_blocks() == free + freed
    assert volume.bitmap.get_bit(target) == (op in ("delete", "shrink"))
    close_volume(blkdev, volume)

    if op == "protect":
        flip_comment_byte(image, target)
    blkdev, volume = open_volume(image)
    if op == "delete":
        assert volume.get_path_name(FSString(VICTIM)) is None
    else:
        want = {"protect": "v" * 79, "shrink": "short", "grow": "g" * 79}[op]
        assert get_comment(volume, VICTIM) == FSString(want)
        node = volume.get_path_name(FSString(VICTIM))
        assert node.block.comment_block_id == (0 if op == "shrink" else target)
    close_volume(blkdev, volume)
    assert validate(image) == []


@pytest.mark.parametrize("op", ["protect", "delete", "shrink", "grow"])
@pytest.mark.parametrize("taken", [False, True], ids=["free", "taken"])
@pytest.mark.parametrize("damaged", [False, True], ids=["valid", "bad_checksum"])
@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_block_free_test(tmp_path, dos_type, damaged, taken, op):
    # A comment block that the bitmap marks free, as when the bitmap was
    # not written after a change, is not the entry's, whatever it reads
    # as, and the next file may take it. The entry never frees, rewrites
    # or counts it, and allocates no block for the comment it read from
    # it, which it keeps. The header keeps pointing to the block until a
    # comment change of the entry writes the comment anew, in a block that
    # the bitmap gives it or beside the name.
    image = tmp_path / "test.adf"
    hdr_num, target = make_victim_comment_block(image, dos_type)
    blkdev, volume = open_volume(image)
    volume.bitmap.dealloc_n([target])
    close_volume(blkdev, volume)
    if damaged:
        flip_comment_byte(image, target)
    stale = validate(image)

    blkdev, volume = open_volume(image)
    kept = "" if damaged else "v" * 79
    assert get_comment(volume, VICTIM) == FSString(kept)
    node = volume.get_path_name(FSString(VICTIM))
    assert node.get_block_usage() == (1, 1)
    assert node.get_block_nums() == [hdr_num] + node.data_blk_nums
    if taken:
        volume.write_file(b"n" * 2000, FSString("new"))
        assert target in volume.get_path_name(FSString("new")).get_block_nums()
    data = bytes(blkdev.read_block(target))
    free = volume.get_free_blocks()
    if op == "protect":
        node.change_protect(0x0F)
    elif op == "delete":
        volume.delete(FSString(VICTIM))
    elif op == "shrink":
        node.change_comment(FSString("short"))
    else:
        node.change_comment(FSString("g" * 79))
    freed = {"protect": 0, "delete": 2, "shrink": 0, "grow": -1}[op]
    assert volume.get_free_blocks() == free + freed
    if op != "grow" or taken:
        # a block that is still free may be the one the bitmap gives
        assert volume.bitmap.get_bit(target) != taken
        assert bytes(blkdev.read_block(target)) == data
    want = {"protect": kept, "shrink": "short", "grow": "g" * 79}.get(op)
    if want is not None:
        assert get_comment(volume, VICTIM) == FSString(want)
    close_volume(blkdev, volume)

    pointer = {"protect": target, "shrink": 0}.get(op)
    if pointer is not None:
        assert header_comment_block_id(image, hdr_num) == pointer
    if op == "grow" and taken:
        assert header_comment_block_id(image, hdr_num) not in (0, target)
    if op == "protect" and taken:
        # the next file wrote over the comment
        check_comment_pointer_dropped(image, hdr_num, b"n" * 2000)
        return
    blkdev, volume = open_volume(image)
    if taken:
        assert volume.read_file(FSString("new")) == b"n" * 2000
    if op == "delete":
        assert volume.get_path_name(FSString(VICTIM)) is None
    else:
        assert get_comment(volume, VICTIM) == FSString(want)
    close_volume(blkdev, volume)
    # a header that still points to a block that the bitmap marks free
    # keeps the finding that the stale bitmap left
    assert validate(image) == (stale if op == "protect" else [])


def fs_comment_block_free_copy_test(tmp_path):
    # A comment block that the bitmap marks free when the volume is opened
    # is not the entry's again once a file takes it, even if that file
    # fills it with a copy of what it held: deleting the entry leaves it.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, DosType.DOS7)
    # a free block in front, for the header of the next file
    volume.write_file(b"", FSString("pad"))
    volume.write_file(b"data", FSString(VICTIM))
    victim = volume.get_path_name(FSString(VICTIM))
    victim.change_comment(FSString("v" * 79))
    target = victim.block.comment_block_id
    volume.delete(FSString("pad"))
    data = bytes(blkdev.read_block(target)) * 4
    volume.bitmap.dealloc_n([target])
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    volume.write_file(data, FSString("new"))
    assert target in volume.get_path_name(FSString("new")).data_blk_nums
    volume.delete(FSString(VICTIM))
    assert not volume.bitmap.get_bit(target)
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    assert volume.read_file(FSString("new")) == data
    close_volume(blkdev, volume)
    assert validate(image) == []


@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_block_free_read_only_test(tmp_path, dos_type, capsys):
    # A volume whose bitmap was not written after a change, as after a
    # crash, is opened read-only to rescue its files: a comment in a block
    # that the bitmap marks free still reads, lists and unpacks.
    image = tmp_path / "test.adf"
    hdr_num, target = make_victim_comment_block(image, dos_type)
    blkdev, volume = open_volume(image)
    volume.bitmap.dealloc_n([target])
    root_num = volume.root.blk_num
    close_volume(blkdev, volume)
    blkdev = ADFBlockDevice(str(image))
    blkdev.open()
    root = RootBlock(blkdev, root_num)
    root.read()
    root.bitmap_flag = 0
    root.write()
    blkdev.close()

    blkdev = ADFBlockDevice(str(image), read_only=True)
    blkdev.open()
    volume = ADFSVolume(blkdev)
    volume.open()
    assert get_comment(volume, VICTIM) == FSString("v" * 79)
    out = tmp_path / "out"
    Imager().unpack(volume, str(out))
    close_volume(blkdev, volume)
    meta = (tmp_path / "out.xdfmeta").read_text()
    assert "%s:" % VICTIM in meta and "v" * 79 in meta
    capsys.readouterr()
    assert xdftool_main([str(image), "list"]) == 0
    assert "v" * 79 in capsys.readouterr().out


@pytest.mark.parametrize("op", ["protect", "delete_in"])
@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_block_free_read_only_change_test(tmp_path, dos_type, op):
    # On a volume opened read-only, a protection change of a directory
    # whose comment block the bitmap marks free, or a delete in it, fails
    # at its first write and allocates nothing: the comment still reads,
    # and the volume closes without a write.
    image = tmp_path / "test.adf"
    mate, victim_num, target = make_free_comment_block(image, dos_type, "dir")
    before = image.read_bytes()
    blkdev = ADFBlockDevice(str(image), read_only=True)
    blkdev.open()
    volume = ADFSVolume(blkdev)
    volume.open()
    with pytest.raises(IOError):
        if op == "protect":
            volume.get_path_name(FSString(VICTIM)).change_protect(0x0F)
        else:
            volume.delete(FSString(VICTIM + "/e"))
    assert get_comment(volume, VICTIM) == FSString("v" * 79)
    assert not volume.bitmap.dirty
    close_volume(blkdev, volume)
    assert image.read_bytes() == before


def make_free_comment_block(image, dos_type, kind):
    """a long name volume whose VICTIM, a directory holding "e" or a file in
    front of another in its hash chain, has its comment in a comment block
    that the bitmap marks free, as when the bitmap was not written after a
    change. Returns the name of that other file, or None, and the numbers
    of the header of VICTIM and of its comment block"""
    blkdev, volume = create_volume(image, dos_type)
    mate = None
    if kind == "file":
        mate = hash_mate(volume, VICTIM, "t")
        volume.write_file(b"t", FSString(mate))
        volume.write_file(b"data", FSString(VICTIM))
    else:
        volume.create_dir(FSString(VICTIM))
        volume.write_file(b"e", FSString(VICTIM + "/e"))
    victim = volume.get_path_name(FSString(VICTIM))
    victim.change_comment(FSString("v" * 79))
    victim_num, target = victim.block.blk_num, victim.block.comment_block_id
    volume.bitmap.dealloc_n([target])
    close_volume(blkdev, volume)
    return mate, victim_num, target


def check_comment_pointer_dropped(image, victim_num, new_data):
    """the file "new" took the block that the header of VICTIM points to:
    once the volume is reopened, VICTIM no longer reads its comment there,
    and its next header write drops the pointer. Then "new" reads back and
    the volume validates"""
    blkdev, volume = open_volume(image)
    assert volume.read_file(FSString("new")) == new_data
    assert get_comment(volume, VICTIM) == FSString()
    volume.get_path_name(FSString(VICTIM)).change_protect(0x0F)
    close_volume(blkdev, volume)
    assert header_comment_block_id(image, victim_num) == 0
    assert validate(image) == []


@pytest.mark.parametrize("op", ["create_in", "delete_in", "delete_next"])
@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_block_free_header_write_test(tmp_path, dos_type, op):
    # A create or delete that writes the header of the directory, or of the
    # entry in front of the deleted one, whose comment block the bitmap
    # marks free and the next file took, keeps the pointer as it was read,
    # and the comment in memory, and takes no block but its own, also
    # without the time stamp change that follows.
    image = tmp_path / "test.adf"
    kind = "file" if op == "delete_next" else "dir"
    mate, victim_num, target = make_free_comment_block(image, dos_type, kind)
    blkdev, volume = open_volume(image)
    volume.write_file(b"n" * 2000, FSString("new"))
    assert target in volume.get_path_name(FSString("new")).get_block_nums()
    free = volume.get_free_blocks()
    if op == "create_in":
        node = volume.get_path_name(FSString(VICTIM))
        node.create_file(FSString("x"), b"x", update_ts=False)
    elif op == "delete_in":
        volume.get_path_name(FSString(VICTIM + "/e")).delete(update_ts=False)
    else:
        volume.get_path_name(FSString(mate)).delete(update_ts=False)
    assert volume.get_free_blocks() == free + (-2 if op == "create_in" else 2)
    assert get_comment(volume, VICTIM) == FSString("v" * 79)
    close_volume(blkdev, volume)

    assert header_comment_block_id(image, victim_num) == target
    check_comment_pointer_dropped(image, victim_num, b"n" * 2000)


@pytest.mark.parametrize("op", ["protect", "delete_in", "delete_next", "delete_all"])
@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_block_free_disk_full_test(tmp_path, dos_type, op):
    # Neither a delete nor a protection change needs a free block: on a
    # full disk they succeed beside a comment block that the bitmap marks
    # free and the next file took, and so does deleting the directory that
    # points to it with all its entries. The header keeps its pointer, and
    # the comment stays in memory.
    image = tmp_path / "test.adf"
    kind = "file" if op == "delete_next" else "dir"
    mate, victim_num, target = make_free_comment_block(image, dos_type, kind)
    blkdev, volume = open_volume(image)
    volume.write_file(b"n" * 2000, FSString("new"))
    assert target in volume.get_path_name(FSString("new")).get_block_nums()
    fill_disk(volume)
    assert volume.get_free_blocks() == 0
    if op == "protect":
        volume.get_path_name(FSString(VICTIM)).change_protect(0x0F)
    elif op == "delete_in":
        volume.delete(FSString(VICTIM + "/e"))
    elif op == "delete_next":
        volume.delete(FSString(mate))
    else:
        volume.delete(FSString(VICTIM), all=True)
    freed = {"protect": 0, "delete_in": 2, "delete_next": 2, "delete_all": 3}[op]
    assert volume.get_free_blocks() == freed
    if op != "delete_all":
        assert get_comment(volume, VICTIM) == FSString("v" * 79)
    close_volume(blkdev, volume)

    if op == "delete_all":
        blkdev, volume = open_volume(image)
        assert volume.read_file(FSString("new")) == b"n" * 2000
        close_volume(blkdev, volume)
        assert validate(image) == []
    else:
        assert header_comment_block_id(image, victim_num) == target
        check_comment_pointer_dropped(image, victim_num, b"n" * 2000)


@pytest.mark.parametrize("op", ["protect", "delete_in"])
@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_block_free_live_file_test(tmp_path, dos_type, op):
    # A crash before close() leaves the blocks written in that session
    # marked free: here those of B and the comment block of VICTIM, written
    # after B. A protection change of VICTIM, or a delete in it, allocates
    # no block for the comment, so it does not write over B.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    if op == "delete_in":
        volume.create_dir(FSString(VICTIM))
        volume.write_file(b"e", FSString(VICTIM + "/e"))
    else:
        volume.write_file(b"data", FSString(VICTIM))
    data = bytes(range(250)) * 6
    volume.write_file(data, FSString("B"))
    victim = volume.get_path_name(FSString(VICTIM))
    victim.change_comment(FSString("v" * 79))
    lost = volume.get_path_name(FSString("B")).get_block_nums()
    volume.bitmap.dealloc_n(lost + [victim.block.comment_block_id])
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    if op == "protect":
        volume.get_path_name(FSString(VICTIM)).change_protect_by_string("r")
    else:
        volume.delete(FSString(VICTIM + "/e"))
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    assert volume.read_file(FSString("B")) == data
    assert get_comment(volume, VICTIM) == FSString("v" * 79)
    close_volume(blkdev, volume)


@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_block_free_delete_fails_test(tmp_path, dos_type, monkeypatch):
    # A delete in a directory whose comment block the bitmap marks free
    # writes nothing for the comment: when the unlink fails, the free block
    # count is unchanged, and so is the directory with its comment.
    image = tmp_path / "test.adf"
    mate, victim_num, target = make_free_comment_block(image, dos_type, "dir")
    stale = validate(image)
    blkdev, volume = open_volume(image)
    free = volume.get_free_blocks()
    e_num = volume.get_path_name(FSString(VICTIM + "/e")).block.blk_num
    write = UserDirBlock.write

    def failing_write(self):
        if self.blk_num == victim_num and e_num not in self.hash_table:
            raise IOError("unlink failed")
        write(self)

    monkeypatch.setattr(UserDirBlock, "write", failing_write)
    with pytest.raises(IOError):
        volume.delete(FSString(VICTIM + "/e"))
    monkeypatch.undo()
    assert volume.get_free_blocks() == free
    assert get_comment(volume, VICTIM) == FSString("v" * 79)
    close_volume(blkdev, volume)
    assert header_comment_block_id(image, victim_num) == target
    assert validate(image) == stale


@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_block_bitmap_block_test(tmp_path, dos_type):
    # A bitmap block is always allocated, and its first long is its own
    # checksum, so that it can read as an entry's comment block. It is the
    # volume's: deleting the entry does not free it, and the next file
    # does not take it.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    volume.write_file(b"data", FSString(VICTIM))
    victim_num = volume.get_path_name(FSString(VICTIM)).block.blk_num
    bm_num = volume.bitmap.bitmap_blks[0].blk_num
    close_volume(blkdev, volume)
    blkdev = ADFBlockDevice(str(image))
    blkdev.open()
    longs = list(struct.unpack(">128I", blkdev.read_block(bm_num)))
    longs[0:3] = [Block.T_COMMENT, bm_num, victim_num]
    # a comment of 0 bytes: free blocks have their bits set
    longs[6] &= 0x00FFFFFF
    # long 127 lies past the bitmap: it makes the checksum right again
    longs[127] = (longs[127] - sum(longs)) & 0xFFFFFFFF
    blkdev.write_block(bm_num, struct.pack(">128I", *longs))
    hdr = FileHeaderBlock(blkdev, victim_num, is_longname=True)
    hdr.read()
    hdr.comment_block_id = bm_num
    hdr.write()
    blkdev.close()

    blkdev, volume = open_volume(image)
    node = volume.get_path_name(FSString(VICTIM))
    assert node.get_block_nums() == [victim_num] + node.data_blk_nums
    volume.delete(FSString(VICTIM))
    assert not volume.bitmap.get_bit(bm_num)
    volume.write_file(b"n" * 10000, FSString("new"))
    assert bm_num not in volume.get_path_name(FSString("new")).get_block_nums()
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    assert volume.read_file(FSString("new")) == b"n" * 10000
    close_volume(blkdev, volume)


@pytest.mark.parametrize("kind", ["file", "dir"])
@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_block_delete_read_fails_test(tmp_path, dos_type, kind, monkeypatch):
    # A delete checks that the comment block is still the entry's before
    # it writes anything, as that takes a read: once the unlink is written,
    # a read that fails would leave the blocks of the entry allocated with
    # nothing linking them.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    if kind == "dir":
        volume.create_dir(FSString(VICTIM))
    else:
        volume.write_file(b"data", FSString(VICTIM))
    volume.get_path_name(FSString(VICTIM)).change_comment(FSString("v" * 79))
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    free = volume.get_free_blocks()
    read_block = ADFBlockDevice.read_block
    write_block = ADFBlockDevice.write_block
    written = []

    def failing_read_block(self, num):
        if written:
            raise IOError("read failed")
        return read_block(self, num)

    def recording_write_block(self, num, data):
        written.append(num)
        return write_block(self, num, data)

    monkeypatch.setattr(ADFBlockDevice, "read_block", failing_read_block)
    monkeypatch.setattr(ADFBlockDevice, "write_block", recording_write_block)
    volume.delete(FSString(VICTIM))
    monkeypatch.undo()
    assert volume.get_free_blocks() == free + (2 if kind == "dir" else 3)
    close_volume(blkdev, volume)
    assert validate(image) == []


def hash_mate(volume, name, prefix):
    """a name made of prefix and a number that hashes as name does"""

    def hash_of(name):
        return FileName(FSString(name), volume.is_intl, volume.is_longname).hash()

    n = 0
    while hash_of("%s%d" % (prefix, n)) != hash_of(name):
        n += 1
    return "%s%d" % (prefix, n)


def make_comment_like_data(image, kind="file", length=0, checksum=False):
    """a DOS7 volume whose VICTIM, a file or a directory, points to the
    first data block of KEEPER, raw file data that reads as a comment block
    of VICTIM apart from its checksum, with a comment of length bytes, and
    with the checksum, too, if checksum is set. A directory holds "e",
    unless it is an empty one; a file is in front of the one other entry
    of its hash chain, whose name is returned. Returns that name and the
    numbers of the header of VICTIM and of that block"""
    blkdev, volume = create_volume(image, DosType.DOS7)
    mate = None
    if kind in ("dir", "empty_dir"):
        volume.create_dir(FSString(VICTIM))
        if kind == "dir":
            volume.write_file(b"e", FSString(VICTIM + "/e"))
    else:
        mate = hash_mate(volume, VICTIM, "t")
        volume.write_file(b"t", FSString(mate))
        volume.write_file(b"data", FSString(VICTIM))
    victim_num = volume.get_path_name(FSString(VICTIM)).block.blk_num
    volume.write_file(b"k" * 600, FSString(KEEPER))
    target = volume.get_path_name(FSString(KEEPER)).data_blk_nums[0]
    close_volume(blkdev, volume)
    blkdev = ADFBlockDevice(str(image))
    blkdev.open()
    data = bytearray(blkdev.read_block(target))
    data[0:12] = struct.pack(">III", Block.T_COMMENT, target, victim_num)
    data[24] = length
    if checksum:
        data[20:24] = bytes(4)
        longs = struct.unpack(">%dI" % (len(data) // 4), data)
        data[20:24] = struct.pack(">I", -sum(longs) & 0xFFFFFFFF)
    blkdev.write_block(target, data)
    if kind != "file":
        hdr = UserDirBlock(blkdev, victim_num, is_longname=True)
    else:
        hdr = FileHeaderBlock(blkdev, victim_num, is_longname=True)
    hdr.read()
    hdr.comment_block_id = target
    hdr.write()
    blkdev.close()
    return mate, victim_num, target


def take_comment_like_data(volume, target, taken=True):
    """delete KEEPER, and let the next file take its block target"""
    volume.delete(FSString(KEEPER))
    if taken:
        volume.write_file(b"n" * 600, FSString("new"))
        assert target in volume.get_path_name(FSString("new")).data_blk_nums


def header_comment_block_id(image, blk_num):
    """the comment block pointer on disk of long name header blk_num"""
    blkdev = ADFBlockDevice(str(image), read_only=True)
    blkdev.open()
    blk = Block(blkdev, blk_num)
    blk.read()
    blk_id = blk._get_long(-18)
    blkdev.close()
    return blk_id


def fs_comment_block_file_data_test(tmp_path):
    # FFS data blocks hold raw file data, which may read as any block: here
    # the first data block of KEEPER reads as a comment block of VICTIM,
    # whose header points to it. Once KEEPER is deleted and the next file
    # takes that block, it is no longer VICTIM's: VICTIM no longer counts
    # or lists it, but its header keeps the pointer.
    image = tmp_path / "test.adf"
    mate, victim_num, target = make_comment_like_data(image)
    blkdev, volume = open_volume(image)
    node = volume.get_path_name(FSString(VICTIM))
    assert node.get_block_usage() == (1, 2)
    assert node.get_block_nums() == [victim_num, target] + node.data_blk_nums
    take_comment_like_data(volume, target)
    assert node.get_block_usage() == (1, 1)
    assert node.get_block_nums() == [victim_num] + node.data_blk_nums
    node.change_protect(0x0F)
    close_volume(blkdev, volume)

    assert header_comment_block_id(image, victim_num) == target
    check_comment_pointer_dropped(image, victim_num, b"n" * 600)


def fs_comment_block_file_data_copy_test(tmp_path):
    # File data that reads as a comment block of VICTIM is let go once the
    # bitmap marks it free, and is not VICTIM's again when the next file
    # takes the block with a copy of what it held: VICTIM neither counts
    # nor frees it.
    image = tmp_path / "test.adf"
    mate, victim_num, target = make_comment_like_data(image)
    blkdev, volume = open_volume(image)
    node = volume.get_path_name(FSString(VICTIM))
    data = bytes(blkdev.read_block(target))
    volume.delete(FSString(KEEPER))
    assert node.get_block_usage() == (1, 1)
    volume.write_file(data, FSString("new"))
    assert target in volume.get_path_name(FSString("new")).data_blk_nums
    assert node.get_block_usage() == (1, 1)
    volume.delete(FSString(VICTIM))
    assert not volume.bitmap.get_bit(target)
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    assert volume.read_file(FSString("new")) == data
    close_volume(blkdev, volume)
    assert validate(image) == []


def fs_comment_block_file_data_comment_test(tmp_path):
    # A comment read from a block that stops being the entry's while the
    # volume is open stays the entry's, and its header keeps pointing to
    # that block, until a comment change of the entry writes the comment
    # anew.
    image = tmp_path / "test.adf"
    mate, victim_num, target = make_comment_like_data(image, length=10, checksum=True)
    blkdev, volume = open_volume(image)
    node = volume.get_path_name(FSString(VICTIM))
    assert get_comment(volume, VICTIM) == FSString("k" * 10)
    take_comment_like_data(volume, target)
    node.change_protect(0x0F)
    assert node.block.comment_block_id == target
    assert get_comment(volume, VICTIM) == FSString("k" * 10)
    free = volume.get_free_blocks()
    node.change_comment(get_comment(volume, VICTIM))
    assert node.block.comment_block_id == 0
    assert volume.get_free_blocks() == free
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    assert get_comment(volume, VICTIM) == FSString("k" * 10)
    assert volume.read_file(FSString("new")) == b"n" * 600
    close_volume(blkdev, volume)
    assert validate(image) == []


@pytest.mark.parametrize("op", ["shrink", "grow"])
@pytest.mark.parametrize("taken", [True, False], ids=["taken", "free"])
def fs_comment_block_file_data_change_test(tmp_path, taken, op):
    # A comment change checks again that the comment block is still the
    # entry's: once KEEPER is deleted, and maybe the next file takes its
    # block, a shorter comment does not free it, and a longer one does not
    # rewrite it but takes a new block.
    image = tmp_path / "test.adf"
    mate, victim_num, target = make_comment_like_data(image)
    blkdev, volume = open_volume(image)
    take_comment_like_data(volume, target, taken)
    free = volume.get_free_blocks()
    node = volume.get_path_name(FSString(VICTIM))
    if not taken:
        # block counts leave out a block the bitmap marks free
        assert node.get_block_usage() == (1, 1)
    want = "short" if op == "shrink" else "g" * 79
    node.change_comment(FSString(want))
    assert volume.get_free_blocks() == free - (op == "grow")
    assert volume.bitmap.get_bit(target) != taken
    close_volume(blkdev, volume)

    assert header_comment_block_id(image, victim_num) != target
    blkdev, volume = open_volume(image)
    if taken:
        assert volume.read_file(FSString("new")) == b"n" * 600
    assert get_comment(volume, VICTIM) == FSString(want)
    close_volume(blkdev, volume)
    assert validate(image) == []


def fs_comment_block_file_data_dir_delete_test(tmp_path):
    # Deleting a directory checks again that its comment block is still
    # its own, and does not free the block of the next file.
    image = tmp_path / "test.adf"
    mate, victim_num, target = make_comment_like_data(image, kind="empty_dir")
    blkdev, volume = open_volume(image)
    take_comment_like_data(volume, target)
    volume.delete(FSString(VICTIM))
    assert not volume.bitmap.get_bit(target)
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    assert volume.read_file(FSString("new")) == b"n" * 600
    close_volume(blkdev, volume)
    assert validate(image) == []


@pytest.mark.parametrize("op", ["create_in", "delete_in", "delete_next"])
def fs_comment_block_file_data_header_write_test(tmp_path, op):
    # A create or delete writes the header of the directory, or of the
    # entry in front of the deleted one in its hash chain, without the time
    # stamp change that follows, as xdftool pack and repack create and
    # delete entries: that header, too, keeps its pointer to a block that
    # is no longer its comment block.
    image = tmp_path / "test.adf"
    kind = "file" if op == "delete_next" else "dir"
    mate, victim_num, target = make_comment_like_data(image, kind=kind)
    blkdev, volume = open_volume(image)
    take_comment_like_data(volume, target)
    if op == "create_in":
        node = volume.get_path_name(FSString(VICTIM))
        node.create_file(FSString("x"), b"x", update_ts=False)
    elif op == "delete_in":
        volume.get_path_name(FSString(VICTIM + "/e")).delete(update_ts=False)
    else:
        volume.get_path_name(FSString(mate)).delete(update_ts=False)
    close_volume(blkdev, volume)

    assert header_comment_block_id(image, victim_num) == target
    check_comment_pointer_dropped(image, victim_num, b"n" * 600)


@pytest.mark.parametrize("op", ["protect", "delete", "shrink", "grow"])
def fs_comment_block_file_data_long_comment_test(tmp_path, op):
    # File data that reads as an entry's comment block apart from its
    # checksum, but with a comment longer than 79 bytes, is no comment
    # block: the entry neither frees nor rewrites it, and its header no
    # longer points to it.
    image = tmp_path / "test.adf"
    mate, victim_num, target = make_comment_like_data(image, length=107)
    blkdev, volume = open_volume(image)
    keeper = volume.read_file(FSString(KEEPER))
    node = volume.get_path_name(FSString(VICTIM))
    assert node.get_block_nums() == [victim_num] + node.data_blk_nums
    if op == "protect":
        node.change_protect(0x0F)
    elif op == "delete":
        volume.delete(FSString(VICTIM))
    elif op == "shrink":
        node.change_comment(FSString("short"))
    else:
        node.change_comment(FSString("g" * 79))
    assert not volume.bitmap.get_bit(target)
    close_volume(blkdev, volume)

    if op != "delete":
        assert header_comment_block_id(image, victim_num) != target
    blkdev, volume = open_volume(image)
    assert volume.read_file(FSString(KEEPER)) == keeper
    close_volume(blkdev, volume)
    assert validate(image) == []


def fs_comment_block_read_count_test(tmp_path, monkeypatch):
    # Reading a directory reads each comment block once. Block counts and
    # the bitmap drawing read each comment block once more, the
    # directory's own included, to check that it is still the entry's, and
    # no other block.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, DosType.DOS7)
    dir_name = "d" * 60
    volume.create_dir(FSString(dir_name))
    node = volume.get_path_name(FSString(dir_name))
    node.change_comment(FSString("c" * 79))
    comment_blks = [node.block.comment_block_id]
    want = []
    for n in range(5):
        path = FSString("%s/%s%d" % (dir_name, "f" * 60, n))
        volume.write_file(b"data", path)
        entry = volume.get_path_name(path)
        entry.change_comment(FSString("c" * 79))
        want += [entry.block.blk_num, entry.block.comment_block_id]
        comment_blks.append(entry.block.comment_block_id)
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    node = volume.get_path_name(FSString(dir_name))
    read_block = ADFBlockDevice.read_block
    reads = []

    def counting_read_block(self, num):
        reads.append(num)
        return read_block(self, num)

    monkeypatch.setattr(ADFBlockDevice, "read_block", counting_read_block)
    node.get_entries()
    assert sorted(reads) == sorted(want)
    del reads[:]
    assert node.get_block_usage(all=True) == (5, 12)
    bm = [0] * blkdev.num_blocks
    node.draw_on_bitmap(bm, True)
    assert [bm[blk_num] for blk_num in comment_blks] == [ord("c")] * 6
    assert sorted(reads) == sorted(comment_blks * 2)
    close_volume(blkdev, volume)


@pytest.mark.parametrize("length", [80, 256])
@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_comment_too_long_test(tmp_path, dos_type, length):
    # AmigaDOS keeps at most 79 bytes of comment on every DOS type, and
    # FastFileSystem refuses longer ones. Refuse them before anything
    # changes, both when changing a comment and when creating an entry.
    image = tmp_path / "test.adf"
    name = "n" * (60 if dos_type in LONGNAME_DOS_TYPES else 30)
    blkdev, volume = create_volume(image, dos_type)
    volume.write_file(b"data", FSString(name))
    node = volume.get_path_name(FSString(name))
    node.change_comment(FSString("c" * 79))
    free = volume.get_free_blocks()
    too_long = FSString("x" * length)
    with pytest.raises(FSError) as error:
        node.change_comment(too_long)
    assert error.value.code == INVALID_COMMENT
    meta_info = MetaInfo(protect=0, comment=too_long)
    meta_info.set_current_as_mod_time()
    with pytest.raises(FSError) as error:
        volume.get_root_dir().create_file(FSString("new"), b"data", meta_info)
    assert error.value.code == INVALID_COMMENT
    assert volume.get_free_blocks() == free
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    assert get_comment(volume, name) == FSString("c" * 79)
    assert volume.get_path_name(FSString("new")) is None
    close_volume(blkdev, volume)
    assert validate(image) == []


@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_comment_not_latin1_test(tmp_path, dos_type):
    # The disk holds Latin-1 only. A comment it cannot encode is refused
    # before it changes the node, so that later writes still succeed.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    volume.write_file(b"data", FSString("file"))
    node = volume.get_path_name(FSString("file"))
    node.change_comment(FSString("old"))
    euro = FSString("5 €")
    with pytest.raises(FSError) as error:
        node.change_meta_info(MetaInfo(protect=0x0F, comment=euro))
    assert error.value.code == INVALID_COMMENT
    assert node.get_meta_info().get_comment() == FSString("old")
    assert node.get_meta_info().get_protect() == 0
    meta_info = MetaInfo(protect=0, comment=euro)
    meta_info.set_current_as_mod_time()
    with pytest.raises(FSError) as error:
        volume.get_root_dir().create_file(FSString("new"), b"data", meta_info)
    assert error.value.code == INVALID_COMMENT
    node.change_protect(0x0F)
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    node = volume.get_path_name(FSString("file"))
    assert node.get_meta_info().get_comment() == FSString("old")
    assert node.get_meta_info().get_protect() == 0x0F
    assert volume.get_path_name(FSString("new")) is None
    close_volume(blkdev, volume)
    assert validate(image) == []
