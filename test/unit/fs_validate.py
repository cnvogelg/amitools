import struct

import pytest

from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.FSString import FSString
from amitools.fs.blkdev.ADFBlockDevice import ADFBlockDevice
from amitools.fs.block.Block import Block
from amitools.fs.block.CommentBlock import CommentBlock
from amitools.fs.block.DirCacheBlock import DirCacheBlock, DirCacheRecord
from amitools.fs.validate.Log import Log
from amitools.fs.validate.Validator import Validator
import amitools.fs.DosType as DosType

DOS_TYPES = [DosType.DOS0 + n for n in range(8)]
FFS_DOS_TYPES = [DosType.DOS1, DosType.DOS3, DosType.DOS5, DosType.DOS7]
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


def make_dircache_volume(path, dos_type):
    """a volume whose 'dir' needs several dircache blocks; returns the
    numbers of the dircache blocks of 'dir'"""
    blkdev, volume = create_volume(path, dos_type)
    volume.create_dir(FSString("dir"))
    volume.create_dir(FSString("dir/sub"))
    for n in range(40):
        volume.write_file(b"x" * (n * 50), FSString("dir/file%02d" % n))
    volume.write_file(b"data", FSString("top"))
    node = volume.get_path_name(FSString("dir"))
    dcb_nums = [dcb.blk_num for dcb in node.dcache_blks or []]
    if volume.is_dircache:
        assert len(dcb_nums) > 1
    close_volume(blkdev, volume)
    return dcb_nums


@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_validate_clean_volume_test(tmp_path, dos_type):
    image = tmp_path / "test.adf"
    make_dircache_volume(image, dos_type)
    assert validate(image) == []


def rewrite_dircache_block(path, blk_num, change):
    blkdev = ADFBlockDevice(str(path))
    blkdev.open()
    dcb = DirCacheBlock(blkdev, blk_num)
    dcb.read()
    assert dcb.valid
    change(dcb)
    blkdev.close()


@pytest.mark.parametrize("dos_type", DIRCACHE_DOS_TYPES, ids=dos_id)
def fs_validate_dircache_checksum_test(tmp_path, dos_type):
    image = tmp_path / "test.adf"
    # the last block, so that no block depends on its link
    dcb_num = make_dircache_volume(image, dos_type)[-1]

    def corrupt(dcb):
        data = bytearray(dcb.blkdev.read_block(dcb.blk_num))
        data[24] ^= 0xFF  # first record, checksum now stale
        dcb.blkdev.write_block(dcb.blk_num, data)

    rewrite_dircache_block(image, dcb_num, corrupt)
    errors = validate(image)
    assert len(errors) == 1
    assert "@%06d:ERROR" % dcb_num in errors[0]
    assert "dircache" in errors[0]


@pytest.mark.parametrize("dos_type", DIRCACHE_DOS_TYPES, ids=dos_id)
def fs_validate_dircache_parent_test(tmp_path, dos_type):
    image = tmp_path / "test.adf"
    dcb_num = make_dircache_volume(image, dos_type)[0]

    def reparent(dcb):
        dcb.parent += 1
        dcb.write()

    rewrite_dircache_block(image, dcb_num, reparent)
    errors = validate(image)
    assert len(errors) == 1
    assert "@%06d:ERROR" % dcb_num in errors[0]
    assert "parent" in errors[0]


@pytest.mark.parametrize("dos_type", DIRCACHE_DOS_TYPES, ids=dos_id)
def fs_validate_dircache_own_key_test(tmp_path, dos_type):
    image = tmp_path / "test.adf"
    dcb_num = make_dircache_volume(image, dos_type)[0]

    def rekey(dcb):
        dcb.own_key += 1
        dcb.write()

    rewrite_dircache_block(image, dcb_num, rekey)
    errors = validate(image)
    assert len(errors) == 1
    assert "@%06d:ERROR" % dcb_num in errors[0]
    assert "own key" in errors[0]


@pytest.mark.parametrize(
    "change", ["name", "size", "comment", "entry", "missing", "duplicate"]
)
@pytest.mark.parametrize("dos_type", DIRCACHE_DOS_TYPES, ids=dos_id)
def fs_validate_dircache_record_test(tmp_path, dos_type, change):
    # Each entry of a directory has exactly one dircache record, and that
    # record matches the entry's name, block, size and comment.
    image = tmp_path / "test.adf"
    # the last dircache block of 'dir' has room for another record
    dcb_num = make_dircache_volume(image, dos_type)[-1]
    entry = []

    def alter(dcb):
        r = dcb.records[0]
        entry.append(r.entry)
        if change == "name":
            r.name = FSString("x" + r.name.get_unicode()[1:])
        elif change == "size":
            r.size += 1
        elif change == "comment":
            r.comment = FSString("x")
        elif change == "entry":
            r.entry = dcb.parent
        elif change == "missing":
            dcb.remove_record(r)
        else:
            dcb.add_record(
                DirCacheRecord(
                    r.entry, r.size, r.protect, r.mod_ts, r.sub_type, r.name, r.comment
                )
            )
        dcb.write()

    rewrite_dircache_block(image, dcb_num, alter)
    want = {
        "name": [(dcb_num, "name")],
        "size": [(dcb_num, "size")],
        "comment": [(dcb_num, "comment")],
        "entry": [(dcb_num, "no entry"), (entry[0], "no dircache record")],
        "missing": [(entry[0], "no dircache record")],
        "duplicate": [(dcb_num, "duplicate")],
    }[change]
    errors = validate(image)
    assert len(errors) == len(want)
    for error, (blk_num, words) in zip(errors, want):
        assert "@%06d:ERROR" % blk_num in error
        assert words in error


@pytest.mark.parametrize("dos_type", DIRCACHE_DOS_TYPES, ids=dos_id)
def fs_validate_dircache_record_overrun_test(tmp_path, dos_type):
    # A record count that runs past the end of the block makes the block
    # invalid; neither the validator nor reading the directory may crash.
    image = tmp_path / "test.adf"
    dcb_num = make_dircache_volume(image, dos_type)[-1]

    def overrun(dcb):
        dcb.num_records = 0xFFFFFFFF
        dcb.write()

    rewrite_dircache_block(image, dcb_num, overrun)
    errors = validate(image)
    assert len(errors) == 1
    assert "@%06d:ERROR" % dcb_num in errors[0]
    assert "dircache" in errors[0]

    blkdev = ADFBlockDevice(str(image))
    blkdev.open()
    volume = ADFSVolume(blkdev)
    volume.open()
    node = volume.get_path_name(FSString("dir"))
    node.read()
    assert not node.valid
    close_volume(blkdev, volume)


def dircache_like_data(blkdev):
    """file data that passes for a dircache block whose record count runs
    past its end"""
    data = bytearray(blkdev.block_bytes)
    struct.pack_into(">I", data, 0, Block.T_DIR_CACHE)
    struct.pack_into(">I", data, 12, 0xFFFFFFFF)
    longs = struct.unpack(">%dI" % blkdev.block_longs, data)
    struct.pack_into(">I", data, 20, -sum(longs) & 0xFFFFFFFF)
    return bytes(data)


@pytest.mark.parametrize("dos_type", FFS_DOS_TYPES, ids=dos_id)
def fs_validate_file_data_like_dircache_test(tmp_path, dos_type):
    # FFS data blocks hold raw file data, which may look like any block.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    volume.write_file(dircache_like_data(blkdev), FSString("file"))
    close_volume(blkdev, volume)
    assert validate(image) == []


@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_validate_comment_block_test(tmp_path, dos_type):
    image = tmp_path / "test.adf"
    name = FSString("n" * 60)
    blkdev, volume = create_volume(image, dos_type)
    volume.write_file(b"data", name)
    volume.create_dir(FSString("d" * 60))
    volume.get_path_name(name).change_comment(FSString("c" * 79))
    volume.get_path_name(FSString("d" * 60)).change_comment(FSString("c" * 79))
    close_volume(blkdev, volume)
    assert validate(image) == []


@pytest.mark.parametrize("dos_type", LONGNAME_DOS_TYPES, ids=dos_id)
def fs_validate_comment_block_own_key_test(tmp_path, dos_type):
    image = tmp_path / "test.adf"
    name = FSString("n" * 60)
    blkdev, volume = create_volume(image, dos_type)
    volume.write_file(b"data", name)
    node = volume.get_path_name(name)
    node.change_comment(FSString("c" * 79))
    cblk_num = node.block.comment_block_id
    close_volume(blkdev, volume)

    blkdev = ADFBlockDevice(str(image))
    blkdev.open()
    cblk = CommentBlock(blkdev, cblk_num)
    cblk.read()
    cblk.own_key += 1
    cblk.write()
    blkdev.close()
    errors = validate(image)
    assert len(errors) == 1
    assert "@%06d:ERROR" % cblk_num in errors[0]
    assert "own key" in errors[0]
