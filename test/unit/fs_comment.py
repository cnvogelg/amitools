import pytest

from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.FSError import FSError, INVALID_COMMENT, NO_FREE_BLOCKS
from amitools.fs.FSString import FSString
from amitools.fs.MetaInfo import MetaInfo
from amitools.fs.blkdev.ADFBlockDevice import ADFBlockDevice
from amitools.fs.block.CommentBlock import CommentBlock
from amitools.fs.block.FileHeaderBlock import FileHeaderBlock
from amitools.fs.validate.Log import Log
from amitools.fs.validate.Validator import Validator
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


def make_foreign_comment_pointer(image, dos_type, kind):
    """a long name volume whose VICTIM points to a comment block that is
    not its own; returns the block number it points to"""
    blkdev, volume = create_volume(image, dos_type)
    volume.write_file(b"keep", FSString(KEEPER))
    keeper = volume.get_path_name(FSString(KEEPER))
    keeper.change_comment(FSString("k" * 79))
    volume.write_file(b"data", FSString(VICTIM))
    victim = volume.get_path_name(FSString(VICTIM))
    if kind == "bad_checksum":
        victim.change_comment(FSString("v" * 79))
    target = {
        "other_entry": keeper.block.comment_block_id,
        "file_header": keeper.block.blk_num,
        "bad_checksum": victim.block.comment_block_id,
        "out_of_range": blkdev.num_blocks + 1,
    }[kind]
    victim_num = victim.block.blk_num
    close_volume(blkdev, volume)

    blkdev = ADFBlockDevice(str(image))
    blkdev.open()
    if kind == "bad_checksum":
        data = bytearray(blkdev.read_block(target))
        data[30] ^= 0xFF
        blkdev.write_block(target, data)
    else:
        hdr = FileHeaderBlock(blkdev, victim_num, is_longname=True)
        hdr.read()
        hdr.comment_block_id = target
        hdr.write()
    blkdev.close()
    return target


@pytest.mark.parametrize("op", ["delete", "shrink", "grow"])
@pytest.mark.parametrize(
    "kind", ["other_entry", "file_header", "bad_checksum", "out_of_range"]
)
@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_comment_block_not_owned_test(tmp_path, dos_type, kind, op):
    # An entry frees or rewrites only a comment block that is valid and names
    # the entry as its header. Any other pointer counts as no comment block.
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
    # a comment block with a bad checksum stays allocated: it may be anyone's
    if kind != "bad_checksum":
        assert validate(image) == []


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
