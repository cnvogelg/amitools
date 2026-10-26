import struct

import pytest

from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.FSString import FSString
from amitools.fs.blkdev.ADFBlockDevice import ADFBlockDevice
from amitools.fs.blkdev.BlkDevFactory import BlkDevFactory
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


def fs_validate_read_error_test(tmp_path, monkeypatch):
    # A block that cannot be read is reported; the validator goes on.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, DosType.DOS0)
    volume.write_file(b"data", FSString("file"))
    blk_num = volume.get_path_name(FSString("file")).block.blk_num
    close_volume(blkdev, volume)
    read_block = ADFBlockDevice.read_block

    def failing_read_block(self, num):
        if num == blk_num:
            raise IOError("read failed")
        return read_block(self, num)

    monkeypatch.setattr(ADFBlockDevice, "read_block", failing_read_block)
    errors = validate(image)
    assert "@%06d:ERROR:Can't read block" % blk_num in errors


def validate_hdf(path, options, fail_blk_num=None):
    """validate an HDF image, with reads of block fail_blk_num failing"""
    blkdev = BlkDevFactory().open(str(path), read_only=True, options=options)
    if fail_blk_num is not None:
        read_block = blkdev.read_block

        def failing_read_block(num):
            if num == fail_blk_num:
                raise IOError("read failed")
            return read_block(num)

        blkdev.read_block = failing_read_block
    validator = Validator(blkdev, Log.WARN)
    assert validator.scan_boot()[0]
    assert validator.scan_root()
    validator.scan_dir_tree()
    validator.scan_files()
    validator.scan_bitmap()
    blkdev.close()
    return [str(e) for e in validator.log.entries]


@pytest.mark.parametrize("kind", ["bitmap", "bitmap_ext"])
def fs_validate_bitmap_read_error_test(tmp_path, kind):
    # A bitmap block or bitmap extension block that cannot be read is
    # reported, as are the bitmap blocks missing then; the validator goes
    # on. 60 MB of 512 byte blocks need more bitmap blocks than the 25
    # that the root block points to, so an extension block holds the rest.
    image = tmp_path / "test.hdf"
    options = {"size": "60M"}
    blkdev = BlkDevFactory().create(str(image), options=options)
    volume = ADFSVolume(blkdev)
    volume.create(FSString("Test"), dos_type=DosType.DOS0)
    bitmap = volume.bitmap
    assert len(bitmap.ext_blks) == 1
    if kind == "bitmap":
        blk_num = bitmap.bitmap_blks[0].blk_num
    else:
        blk_num = bitmap.ext_blks[0].blk_num
    close_volume(blkdev, volume)
    assert validate_hdf(image, options) == []
    errors = validate_hdf(image, options, fail_blk_num=blk_num)
    assert "@%06d:ERROR:Can't read block" % blk_num in errors
    assert any("Invalid number of Bitmap Blocks" in e for e in errors)


@pytest.mark.parametrize("block_bytes", [1024, 4096])
@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_validate_hash_size_test(tmp_path, dos_type, block_bytes):
    # A directory has 200 hash slots with 1024 byte blocks and 968 with
    # 4096, not 72. Entries in the chain that their name hashes to are
    # valid, also those in the slots past the first 72.
    image = tmp_path / "test.hdf"
    options = {"size": "4M", "bs": str(block_bytes)}
    blkdev = BlkDevFactory().create(str(image), options=options)
    volume = ADFSVolume(blkdev)
    volume.create(FSString("Test"), dos_type=dos_type)
    volume.create_dir(FSString("dir"))
    for n in range(20):
        volume.write_file(b"data", FSString("file%d" % n))
        volume.write_file(b"data", FSString("dir/file%d" % n))
    for node in (volume.get_root_dir(), volume.get_path_name(FSString("dir"))):
        slots = [i for i, blk_num in enumerate(node.block.hash_table) if blk_num]
        assert max(slots) >= 72
    close_volume(blkdev, volume)
    assert validate_hdf(image, options) == []


@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_validate_root_hash_size_field_test(tmp_path, dos_type):
    # A root block whose hash size field is not the normal one for its
    # block size is reported once, by itself. Its entries are hashed with
    # the normal slot count, as they were written, so none of them is
    # reported, too.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    for n in range(20):
        volume.write_file(b"data", FSString("file%d" % n))
    root_num = volume.root.blk_num
    close_volume(blkdev, volume)
    blkdev = ADFBlockDevice(str(image))
    blkdev.open()
    blk = Block(blkdev, root_num)
    blk._set_data(bytearray(blkdev.read_block(root_num)))
    blk._put_long(3, 71)
    blk._put_chksum()
    blk._write_data()
    blkdev.close()
    errors = validate(image)
    assert any("does not have normal hash size: 71 != 72" in e for e in errors)
    assert not any("invalid name hash" in e for e in errors)


@pytest.mark.parametrize("kind", ["adf", "hdf"])
@pytest.mark.parametrize(
    "where, message",
    [
        ("hash_slot", "out-of-range block terminates chain"),
        ("bitmap", "Error reading bitmap block"),
        ("bitmap_ext", "Error reading bitmap ext block"),
    ],
)
def fs_validate_block_off_disk_test(tmp_path, kind, where, message):
    # A pointer of the root block past the end of the volume, in a hash
    # table slot, the list of bitmap blocks or the link to a bitmap
    # extension block, is reported; the validator goes on. Reading such a
    # block raises ValueError on an ADF and IOError on an HDF.
    if kind == "adf":
        image = tmp_path / "test.adf"
        blkdev, volume = create_volume(image, DosType.DOS0)
    else:
        image = tmp_path / "test.hdf"
        options = {"size": "4M"}
        blkdev = BlkDevFactory().create(str(image), options=options)
        volume = ADFSVolume(blkdev)
        volume.create(FSString("Test"), dos_type=DosType.DOS0)
    volume.write_file(b"data", FSString("file"))
    root = volume.root
    if where == "hash_slot":
        index = 6 + [i for i, b in enumerate(root.hash_table) if b][0]
    elif where == "bitmap":
        index = -49
    else:
        index = -24
    root_num = root.blk_num
    off_disk = blkdev.num_blocks + 10
    close_volume(blkdev, volume)
    if kind == "adf":
        blkdev = ADFBlockDevice(str(image))
        blkdev.open()
    else:
        blkdev = BlkDevFactory().open(str(image), options=options)
    blk = Block(blkdev, root_num)
    blk._set_data(bytearray(blkdev.read_block(root_num)))
    blk._put_long(index, off_disk)
    blk._put_chksum()
    blk._write_data()
    blkdev.close()
    if kind == "adf":
        errors = validate(image)
    else:
        errors = validate_hdf(image, options)
    assert any(message in e for e in errors)
