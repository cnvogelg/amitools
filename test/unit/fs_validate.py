import pytest

from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.FSString import FSString
from amitools.fs.blkdev.ADFBlockDevice import ADFBlockDevice
from amitools.fs.block.DirCacheBlock import DirCacheBlock
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
