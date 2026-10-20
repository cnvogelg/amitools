import copy
import struct

import pytest

from amitools.fs.ADFSDir import ADFSDir
from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.FSError import (
    DELETE_NOT_ALLOWED,
    FSError,
    INTERNAL_ERROR,
    INVALID_DIR_CACHE_BLOCK,
    INVALID_ENTRY_BLOCK,
)
from amitools.fs.FSString import FSString
from amitools.fs.FileName import FileName
from amitools.fs.blkdev.ADFBlockDevice import ADFBlockDevice
from amitools.fs.blkdev.BlkDevFactory import BlkDevFactory
from amitools.fs.block.Block import Block
from amitools.fs.block.CommentBlock import CommentBlock
from amitools.fs.block.DirCacheBlock import DirCacheBlock, DirCacheRecord
from amitools.fs.block.UserDirBlock import UserDirBlock
from amitools.fs.validate.Log import Log
from amitools.fs.validate.Validator import Validator
import amitools.fs.DosType as DosType
from amitools.tools.xdftool import main as xdftool_main

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


def overrun(dcb):
    dcb.num_records = 0xFFFFFFFF
    dcb.write()


@pytest.mark.parametrize("dos_type", DIRCACHE_DOS_TYPES, ids=dos_id)
def fs_validate_dircache_record_overrun_test(tmp_path, dos_type, capsys):
    # A record count that runs past the end of the block makes the block
    # invalid. The validator reports it; the directory can still be listed
    # and its files read, to rescue them.
    image = tmp_path / "test.adf"
    dcb_num = make_dircache_volume(image, dos_type)[-1]
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
    assert len(node.get_entries()) == 41
    assert volume.read_file(FSString("dir/file01")) == b"x" * 50
    close_volume(blkdev, volume)

    capsys.readouterr()
    assert xdftool_main([str(image), "list"]) == 0
    assert "file39" in capsys.readouterr().out


@pytest.mark.parametrize(
    "op", ["write", "delete", "protect", "write_sub", "delete_sub", "delete_dir"]
)
@pytest.mark.parametrize("dos_type", DIRCACHE_DOS_TYPES, ids=dos_id)
def fs_validate_dircache_overrun_change_test(tmp_path, dos_type, op):
    # Nothing changes a directory whose dircache cannot be read: a write
    # would drop the records it could not read, and leave the block
    # allocated with nothing pointing to it. Trying again fails again.
    image = tmp_path / "test.adf"
    dcb_num = make_dircache_volume(image, dos_type)[-1]
    blkdev, volume = open_volume(image)
    volume.write_file(b"x", FSString("dir/sub/old"))
    close_volume(blkdev, volume)
    rewrite_dircache_block(image, dcb_num, overrun)
    before = image.read_bytes()
    blkdev = ADFBlockDevice(str(image))
    blkdev.open()
    volume = ADFSVolume(blkdev)
    volume.open()
    free = volume.get_free_blocks()
    for attempt in range(2):
        with pytest.raises(FSError) as error:
            if op == "write":
                volume.write_file(b"x", FSString("dir/new"))
            elif op == "delete":
                volume.delete(FSString("dir/file00"))
            elif op == "protect":
                volume.get_path_name(FSString("dir/file00")).change_protect(0x0F)
            elif op == "write_sub":
                # its new time stamp would change the record of dir/sub
                volume.write_file(b"x", FSString("dir/sub/new"))
            elif op == "delete_sub":
                volume.delete(FSString("dir/sub/old"))
            else:
                volume.delete(FSString("dir"), all=True)
        assert error.value.code == INVALID_DIR_CACHE_BLOCK
    assert volume.get_free_blocks() == free
    close_volume(blkdev, volume)
    assert image.read_bytes() == before


def open_volume(path):
    blkdev = ADFBlockDevice(str(path))
    blkdev.open()
    volume = ADFSVolume(blkdev)
    volume.open()
    return blkdev, volume


@pytest.mark.parametrize("op", ["write", "delete", "protect"])
@pytest.mark.parametrize("dos_type", DIRCACHE_DOS_TYPES, ids=dos_id)
def fs_validate_root_dircache_overrun_test(tmp_path, dos_type, op, capsys):
    # A volume whose root has an invalid dircache block opens, and its
    # files list and read; a change to the root is refused.
    image = tmp_path / "test.adf"
    make_dircache_volume(image, dos_type)
    blkdev, volume = open_volume(image)
    dcb_num = volume.get_root_dir().block.extension
    close_volume(blkdev, volume)
    rewrite_dircache_block(image, dcb_num, overrun)
    before = image.read_bytes()

    blkdev, volume = open_volume(image)
    names = [e.name.get_unicode_name() for e in volume.get_root_dir().get_entries()]
    assert sorted(names) == ["dir", "top"]
    assert volume.read_file(FSString("top")) == b"data"
    with pytest.raises(FSError) as error:
        if op == "write":
            volume.write_file(b"x", FSString("new"))
        elif op == "delete":
            volume.delete(FSString("top"))
        else:
            volume.get_path_name(FSString("top")).change_protect(0x0F)
    assert error.value.code == INVALID_DIR_CACHE_BLOCK
    close_volume(blkdev, volume)
    assert image.read_bytes() == before

    capsys.readouterr()
    assert xdftool_main([str(image), "list"]) == 0
    out = capsys.readouterr().out
    assert "top" in out and "file39" in out


@pytest.mark.parametrize("dos_type", DIRCACHE_DOS_TYPES, ids=dos_id)
def fs_validate_dircache_overrun_delete_dir_test(tmp_path, dos_type):
    # An empty directory whose dircache block is invalid is not deleted:
    # the dircache blocks after it could not be found and released.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    volume.create_dir(FSString("empty"))
    dcb_num = volume.get_path_name(FSString("empty")).block.extension
    close_volume(blkdev, volume)
    rewrite_dircache_block(image, dcb_num, overrun)
    before = image.read_bytes()

    blkdev, volume = open_volume(image)
    with pytest.raises(FSError) as error:
        volume.delete(FSString("empty"))
    assert error.value.code == INVALID_DIR_CACHE_BLOCK
    close_volume(blkdev, volume)
    assert image.read_bytes() == before


@pytest.mark.parametrize("kind", ["loop", "other_dir", "out_of_range", "own_key"])
@pytest.mark.parametrize("dos_type", DIRCACHE_DOS_TYPES, ids=dos_id)
def fs_validate_dircache_chain_test(tmp_path, dos_type, kind, capsys, monkeypatch):
    # A dircache chain that links a block twice, a block of another
    # directory or a block off the disk, or holds a block with a wrong own
    # key, is an invalid dircache: the directory lists, but a change that
    # would move a record into such a block is refused. A loop is not
    # followed for ever: past a few hundred reads, reading fails.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    volume.create_dir(FSString("P"))
    volume.create_dir(FSString("Q"))
    volume.write_file(b"q", FSString("Q/qfile"))
    # 17 records fill a dircache block
    for n in range(17):
        volume.write_file(b"x", FSString("P/f%02d" % n))
    p_node = volume.get_path_name(FSString("P"))
    p_num = p_node.block.blk_num
    p_dcb = p_node.block.extension
    q_dcb = volume.get_path_name(FSString("Q")).block.extension
    close_volume(blkdev, volume)

    def relink(dcb):
        if kind == "loop":
            dcb.next_cache = p_dcb
        elif kind == "other_dir":
            dcb.next_cache = q_dcb
        else:
            dcb.own_key += 1
        dcb.write()

    if kind == "out_of_range":
        blkdev = ADFBlockDevice(str(image))
        blkdev.open()
        ud = UserDirBlock(blkdev, p_num)
        ud.read()
        ud.extension = 5000
        ud.write()
        blkdev.close()
    else:
        rewrite_dircache_block(image, p_dcb, relink)
    before = image.read_bytes()
    read = DirCacheBlock.read
    reads = []

    def bounded_read(self):
        reads.append(self.blk_num)
        if len(reads) > 300:
            raise RuntimeError("dircache chain followed for ever")
        read(self)

    monkeypatch.setattr(DirCacheBlock, "read", bounded_read)

    capsys.readouterr()
    assert xdftool_main([str(image), "list"]) == 0
    assert "f16" in capsys.readouterr().out
    blkdev, volume = open_volume(image)
    with pytest.raises(FSError) as error:
        volume.get_path_name(FSString("P/f00")).change_comment(FSString("c" * 79))
    assert error.value.code == INVALID_DIR_CACHE_BLOCK
    close_volume(blkdev, volume)
    assert image.read_bytes() == before


@pytest.mark.parametrize("dos_type", DIRCACHE_DOS_TYPES, ids=dos_id)
def fs_validate_dircache_overrun_backstop_test(tmp_path, dos_type):
    # Every change checks the dircache before it writes anything. Should
    # one get past that, the dircache code refuses, too.
    image = tmp_path / "test.adf"
    dcb_num = make_dircache_volume(image, dos_type)[-1]
    rewrite_dircache_block(image, dcb_num, overrun)
    before = image.read_bytes()
    blkdev, volume = open_volume(image)
    node = volume.get_path_name(FSString("dir"))
    node.get_entries()
    dcb = node.dcache_blks[0]
    record = dcb.records[0]
    calls = [
        lambda: node._dircache_add_entry_int(copy.copy(record)),
        lambda: node._dircache_remove_record(dcb, record),
        lambda: node.update_dircache_record(record, copy.copy(record)),
    ]
    for call in calls:
        with pytest.raises(FSError) as error:
            call()
        assert error.value.code == INTERNAL_ERROR
    assert dcb.records[0] is record
    close_volume(blkdev, volume)
    assert image.read_bytes() == before


def entry_read_order(node):
    """the header block numbers of the entries of node, in the order that
    reading node reads them: the hash table, then the hash chains"""
    entries = {e.block.blk_num: e for e in node.get_entries()}
    order = [blk_num for blk_num in node.block.hash_table if blk_num != 0]
    for blk_num in order:
        if entries[blk_num].block.hash_chain != 0:
            order.append(entries[blk_num].block.hash_chain)
    return order


def flip_checksum(path, blk_num):
    """invert a byte of the checksum of block blk_num: twice restores it"""
    blkdev = ADFBlockDevice(str(path))
    blkdev.open()
    data = bytearray(blkdev.read_block(blk_num))
    data[20] ^= 0xFF
    blkdev.write_block(blk_num, data)
    blkdev.close()


def make_invalid_entry(path, dos_type, bad):
    """a volume whose 'dir' holds a0 to a5, of which the one read first or
    last has a bad checksum: reading 'dir' skips it and the rest of its
    hash chain. Returns the names of the entries that are read"""
    blkdev, volume = create_volume(path, dos_type)
    volume.create_dir(FSString("dir"))
    for n in range(6):
        volume.write_file(b"x" * 10, FSString("dir/a%d" % n))
    node = volume.get_path_name(FSString("dir"))
    order = entry_read_order(node)
    bad_num = order[0] if bad == "first" else order[-1]
    entries = {e.block.blk_num: e for e in node.get_entries()}
    chain = [bad_num]
    while entries[chain[-1]].block.hash_chain != 0:
        chain.append(entries[chain[-1]].block.hash_chain)
    names = sorted(
        e.name.get_unicode_name() for num, e in entries.items() if num not in chain
    )
    close_volume(blkdev, volume)
    flip_checksum(path, bad_num)
    return names


@pytest.mark.parametrize("op", ["write", "makedir", "delete", "delete_dir"])
@pytest.mark.parametrize("bad", ["first", "last"])
@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_validate_entry_invalid_change_test(tmp_path, dos_type, bad, op):
    # Reading a directory skips an entry whose header is invalid, and the
    # rest of its hash chain. No entry is then added or removed: a new one
    # could take the name or the hash chain of one that was not read, and
    # deleting the directory would lose those. Trying again fails again.
    image = tmp_path / "test.adf"
    want = make_invalid_entry(image, dos_type, bad)
    before = image.read_bytes()
    blkdev, volume = open_volume(image)
    names = sorted(
        e.name.get_unicode_name()
        for e in volume.get_path_name(FSString("dir")).get_entries()
    )
    assert names == want and len(names) >= 4
    free = volume.get_free_blocks()
    for attempt in range(2):
        with pytest.raises(FSError) as error:
            if op == "write":
                volume.write_file(b"x", FSString("dir/new"))
            elif op == "makedir":
                volume.create_dir(FSString("dir/new"))
            elif op == "delete":
                volume.delete(FSString("dir/" + names[0]))
            else:
                volume.delete(FSString("dir"), all=True)
        assert error.value.code == INVALID_ENTRY_BLOCK
    assert volume.get_free_blocks() == free
    close_volume(blkdev, volume)
    assert image.read_bytes() == before


@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_validate_entry_invalid_chain_test(tmp_path, dos_type, capsys):
    # An invalid header ends its own hash chain only: of 30 files, each in
    # a hash chain of its own, 29 list and unpack when the header in the
    # first slot of the root's hash table is invalid. Creating an entry in
    # the root is refused.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    for n in range(30):
        volume.write_file(b"file %d" % n, FSString("f%02d" % n))
    slots = [b for b in volume.get_root_dir().block.hash_table if b != 0]
    assert len(slots) == 30
    close_volume(blkdev, volume)
    flip_checksum(image, slots[0])

    blkdev, volume = open_volume(image)
    names = sorted(
        e.name.get_unicode_name() for e in volume.get_root_dir().get_entries()
    )
    assert len(names) == 29
    with pytest.raises(FSError) as error:
        volume.write_file(b"x", FSString("new"))
    assert error.value.code == INVALID_ENTRY_BLOCK
    close_volume(blkdev, volume)

    capsys.readouterr()
    assert xdftool_main([str(image), "list"]) == 0
    out = capsys.readouterr().out
    assert all(name in out for name in names)
    unpacked = tmp_path / "unpacked"
    assert xdftool_main([str(image), "unpack", str(unpacked)]) == 0
    files = sorted(p.name for p in unpacked.iterdir() if p.suffix != ".uaem")
    assert files == names
    for name in names:
        data = (unpacked / name).read_bytes()
        assert data == b"file %d" % int(name[1:])


@pytest.mark.parametrize("target", ["dir", "dir/sub"])
@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_validate_entry_invalid_delete_all_test(tmp_path, dos_type, target):
    # Deleting a directory with all its entries, when it or its parent
    # holds an invalid header, is refused before the entries of a
    # subdirectory read in full go.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    volume.create_dir(FSString("dir"))

    # a file in the hash chain of "sub", created first: "sub" heads the
    # chain and is read before it
    def hash_of(name):
        return FileName(FSString(name), volume.is_intl, volume.is_longname).hash()

    n = 0
    while hash_of("g%d" % n) != hash_of("sub"):
        n += 1
    volume.write_file(b"g", FSString("dir/g%d" % n))
    volume.create_dir(FSString("dir/sub"))
    volume.write_file(b"s", FSString("dir/sub/s"))
    order = entry_read_order(volume.get_path_name(FSString("dir")))
    bad = volume.get_path_name(FSString("dir/g%d" % n)).block.blk_num
    assert order[-1] == bad
    close_volume(blkdev, volume)
    flip_checksum(image, bad)
    before = image.read_bytes()

    blkdev, volume = open_volume(image)
    with pytest.raises(FSError) as error:
        volume.delete(FSString(target), all=True)
    assert error.value.code == INVALID_ENTRY_BLOCK
    assert volume.read_file(FSString("dir/sub/s")) == b"s"
    close_volume(blkdev, volume)
    assert image.read_bytes() == before


@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_validate_entry_invalid_read_test(tmp_path, dos_type, capsys):
    # A volume whose root holds an invalid header still lists the other
    # entries, and their files read. Their meta info changes, and
    # entries are created in and deleted from a directory read in full, as
    # these do not add or remove entries of the root. Once the header is
    # repaired, the image is valid.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    volume.create_dir(FSString("good"))
    volume.write_file(b"old", FSString("good/old"))
    for n in range(6):
        volume.write_file(b"r%d" % n, FSString("r%d" % n))
    # the header read last is not that of "good"
    bad = entry_read_order(volume.get_root_dir())[-1]
    assert bad != volume.get_path_name(FSString("good")).block.blk_num
    close_volume(blkdev, volume)
    flip_checksum(image, bad)

    blkdev, volume = open_volume(image)
    root = volume.get_root_dir()
    names = sorted(e.name.get_unicode_name() for e in root.get_entries())
    assert len(names) == 6 and "good" in names
    name = [n for n in names if n != "good"][0]
    assert volume.read_file(FSString(name)) == name.encode()
    with pytest.raises(FSError) as error:
        volume.write_file(b"x", FSString("new"))
    assert error.value.code == INVALID_ENTRY_BLOCK
    volume.get_path_name(FSString(name)).change_comment(FSString("a comment"))
    volume.get_path_name(FSString("good")).change_protect(0x0F)
    volume.write_file(b"new", FSString("good/new"))
    volume.delete(FSString("good/old"))
    close_volume(blkdev, volume)

    capsys.readouterr()
    assert xdftool_main([str(image), "list"]) == 0
    assert name in capsys.readouterr().out
    flip_checksum(image, bad)
    blkdev, volume = open_volume(image)
    assert volume.read_file(FSString("good/new")) == b"new"
    assert len(volume.get_root_dir().get_entries()) == 7
    close_volume(blkdev, volume)
    assert validate(image) == []


@pytest.mark.parametrize(
    "dos_type,fail",
    [(dos_type, "entry") for dos_type in DOS_TYPES]
    + [(dos_type, "dircache") for dos_type in DIRCACHE_DOS_TYPES],
    ids=lambda v: dos_id(v) if isinstance(v, int) else v,
)
def fs_validate_read_raises_test(tmp_path, dos_type, fail, monkeypatch):
    # A read of a directory that raises, as when a header or a dircache
    # block cannot be read, leaves it unread: the next use reads it again,
    # in full, and the entries created then keep all records.
    image = tmp_path / "test.adf"
    dcb_nums = make_dircache_volume(image, dos_type)
    blkdev, volume = open_volume(image)
    if fail == "dircache":
        blk_num = dcb_nums[1]
    else:
        blk_num = entry_read_order(volume.get_path_name(FSString("dir")))[1]
    close_volume(blkdev, volume)
    read_block = ADFBlockDevice.read_block
    failed = []

    def failing_read_block(self, num):
        if num == blk_num and not failed:
            failed.append(num)
            raise IOError("read failed")
        return read_block(self, num)

    blkdev, volume = open_volume(image)
    monkeypatch.setattr(ADFBlockDevice, "read_block", failing_read_block)
    node = volume.get_path_name(FSString("dir"))
    with pytest.raises(IOError):
        node.get_entries()
    assert node.entries is None
    for n in range(20):
        volume.write_file(b"y", FSString("dir/new%02d" % n))
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    assert len(volume.get_path_name(FSString("dir")).get_entries()) == 61
    close_volume(blkdev, volume)
    assert validate(image) == []


def hash_of(volume, name):
    return FileName(FSString(name), volume.is_intl, volume.is_longname).hash()


def names_in_rising_slots(volume, count):
    """count file names, each with a hash slot of its own, in the order of
    their slots, which is the order a directory reads them in"""
    slots = {}
    n = 0
    while len(slots) < count:
        name = "f%03d" % n
        slots.setdefault(hash_of(volume, name), name)
        n += 1
    return [slots[slot] for slot in sorted(slots)]


def bounded_reads(monkeypatch, limit=2000):
    """make reading fail past limit block reads, so that a loop fails"""
    read_block = ADFBlockDevice.read_block
    reads = []

    def bounded_read_block(self, num):
        reads.append(num)
        if len(reads) > limit:
            raise RuntimeError("chain followed for ever")
        return read_block(self, num)

    monkeypatch.setattr(ADFBlockDevice, "read_block", bounded_read_block)
    return reads


@pytest.mark.parametrize("damage", ["list_block", "no_header"])
@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_validate_entry_no_node_test(tmp_path, dos_type, damage, capsys):
    # A block that gives no entry, as a block that is no header or a file
    # whose list block is invalid, is skipped, also when an invalid header
    # was read before it: the other chains are read, the volume opens and
    # its files read.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    names = names_in_rising_slots(volume, 6)
    for name in names:
        volume.write_file(b"x" * (40000 if name == names[4] else 10), FSString(name))
    flipped = volume.get_path_name(FSString(names[1])).block.blk_num
    node = volume.get_path_name(FSString(names[4]))
    if damage == "list_block":
        damaged = node.ext_blk_nums[0]
    else:
        damaged = node.block.blk_num
    close_volume(blkdev, volume)
    flip_checksum(image, flipped)
    if damage == "list_block":
        flip_checksum(image, damaged)
    else:
        blkdev = ADFBlockDevice(str(image))
        blkdev.open()
        blkdev.write_block(damaged, bytes(blkdev.block_bytes))
        blkdev.close()

    blkdev, volume = open_volume(image)
    want = [names[0], names[2], names[3], names[5]]
    got = sorted(e.name.get_unicode_name() for e in volume.root_dir.get_entries())
    assert got == want
    assert volume.read_file(FSString(names[0])) == b"x" * 10
    with pytest.raises(FSError) as error:
        volume.write_file(b"x", FSString("new"))
    assert error.value.code == INVALID_ENTRY_BLOCK
    close_volume(blkdev, volume)
    capsys.readouterr()
    assert xdftool_main([str(image), "list"]) == 0
    assert names[0] in capsys.readouterr().out


def hash_mate(volume, name, prefix):
    """a name made of prefix and a number that hashes as name does"""
    n = 0
    while hash_of(volume, "%s%d" % (prefix, n)) != hash_of(volume, name):
        n += 1
    return "%s%d" % (prefix, n)


def rewrite_long(path, blk_num, index, value):
    """set long index of block blk_num to value, with a valid checksum"""
    blkdev = ADFBlockDevice(str(path))
    blkdev.open()
    blk = Block(blkdev, blk_num)
    blk.read()
    blk._put_long(index, value)
    blk._put_chksum()
    blk._write_data()
    blkdev.close()


def check_entries_read(path, want, capsys):
    """the root lists the entries named in want, the first reads, and no
    entry is added or removed; xdftool lists them, too"""
    before = path.read_bytes()
    blkdev, volume = open_volume(path)
    got = sorted(e.name.get_unicode_name() for e in volume.root_dir.get_entries())
    assert got == sorted(want)
    assert volume.read_file(FSString(want[0])) == want[0].encode()
    for op in ("write", "delete"):
        with pytest.raises(FSError) as error:
            if op == "write":
                volume.write_file(b"x", FSString("new"))
            else:
                volume.delete(FSString(want[0]))
        assert error.value.code == INVALID_ENTRY_BLOCK
    close_volume(blkdev, volume)
    capsys.readouterr()
    assert xdftool_main([str(path), "list"]) == 0
    out = capsys.readouterr().out
    assert all(name in out for name in want)
    assert path.read_bytes() == before


@pytest.mark.parametrize("damage", ["list_block", "list_off_disk", "count"])
@pytest.mark.parametrize(
    "dos_type", [DosType.DOS0, DosType.DOS5, DosType.DOS7], ids=dos_id
)
def fs_validate_entry_file_blocks_chain_test(tmp_path, dos_type, damage, capsys):
    # A file whose header is valid but whose blocks cannot all be found, as
    # when its list block is invalid or lies off the disk, or they do not
    # match its size, gives no entry, but its header still leads on along
    # its hash chain: the file behind it lists and reads.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    big = hash_mate(volume, "t7", "big")
    volume.write_file(b"t7", FSString("t7"))
    volume.write_file(b"b" * 60000, FSString(big))
    node = volume.get_path_name(FSString(big))
    assert node.block.hash_chain == volume.get_path_name(FSString("t7")).block.blk_num
    hdr_num, list_num = node.block.blk_num, node.ext_blk_nums[0]
    num_blocks = blkdev.num_blocks
    close_volume(blkdev, volume)
    if damage == "list_block":
        flip_checksum(image, list_num)
    elif damage == "list_off_disk":
        rewrite_long(image, hdr_num, -2, num_blocks + 5)
    else:
        rewrite_long(image, hdr_num, -47, 100)
    check_entries_read(image, ["t7"], capsys)


@pytest.mark.parametrize("target", ["off_disk", "boot"])
@pytest.mark.parametrize("where", ["hash_chain", "hash_table"])
@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_validate_entry_off_disk_test(tmp_path, dos_type, where, target, capsys):
    # A hash chain or a hash table slot that leads off the disk, or to a
    # boot block, ends there, as an invalid header does: the volume opens,
    # where it raised ValueError, and its other entries list and read. The
    # boot block here reads as a valid header, a copy of the last one.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    names = names_in_rising_slots(volume, 4)
    for name in names:
        volume.write_file(name.encode(), FSString(name))
    last = volume.get_path_name(FSString(names[3])).block.blk_num
    root_num = volume.root.blk_num
    slot = hash_of(volume, names[3])
    bad = blkdev.num_blocks + 5 if target == "off_disk" else 1
    if target == "boot":
        blk = Block(blkdev, 1)
        blk._set_data(bytearray(blkdev.read_block(last)))
        blk._put_long(1, 1)
        blk._put_chksum()
        blk._write_data()
    close_volume(blkdev, volume)
    if where == "hash_chain":
        rewrite_long(image, last, -4, bad)
        want = names
    else:
        rewrite_long(image, root_num, 6 + slot, bad)
        want = names[:3]
    check_entries_read(image, want, capsys)


@pytest.mark.parametrize("kind", ["hard_link", "soft_link", "root"])
@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_validate_entry_other_type_test(tmp_path, dos_type, kind, capsys):
    # A header of a type that is not read, as a link, or a hash chain that
    # leads to the root block, gives no entry, as an invalid header does:
    # the directory lists and its files read, where
    # it raised UNSUPPORTED_DIR_BLOCK and could not be read at all.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    names = names_in_rising_slots(volume, 4)
    for name in names:
        volume.write_file(name.encode(), FSString(name))
    hdr_num = volume.get_path_name(FSString(names[2])).block.blk_num
    root_num = volume.root.blk_num
    close_volume(blkdev, volume)
    if kind == "root":
        rewrite_long(image, hdr_num, -4, root_num)
        want = names
    else:
        sub_type = Block.ST_LINKFILE if kind == "hard_link" else Block.ST_SOFTLINK
        rewrite_long(image, hdr_num, -1, sub_type)
        want = [name for name in names if name != names[2]]
    check_entries_read(image, want, capsys)


@pytest.mark.parametrize("kind", ["hard_link", "soft_link"])
@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_validate_entry_link_chain_test(tmp_path, dos_type, kind, capsys):
    # A link, valid but of a type that is not read, leads on along its hash
    # chain: the entry behind it in its chain lists and reads, too.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    names = names_in_rising_slots(volume, 3)
    mate = hash_mate(volume, names[1], "m")
    for name in [names[0], mate] + names[1:]:
        volume.write_file(name.encode(), FSString(name))
    link = volume.get_path_name(FSString(names[1])).block
    assert link.hash_chain == volume.get_path_name(FSString(mate)).block.blk_num
    close_volume(blkdev, volume)
    sub_type = Block.ST_LINKFILE if kind == "hard_link" else Block.ST_SOFTLINK
    rewrite_long(image, link.blk_num, -1, sub_type)
    check_entries_read(image, [names[0], mate, names[2]], capsys)


@pytest.mark.parametrize("bad", [False, True], ids=["loop", "loop_and_invalid"])
@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_validate_entry_chain_loop_test(tmp_path, dos_type, bad, monkeypatch, capsys):
    # A hash chain that leads back to a header read before ends there, as
    # an invalid header does, also beside an invalid header in another
    # chain: each header is read once, the other chains in full, and no
    # entry is added or removed. Past a few thousand reads, reading fails.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    names = names_in_rising_slots(volume, 3)
    tail = names[0]
    head = None
    n = 0
    while head is None:
        if hash_of(volume, "g%d" % n) == hash_of(volume, tail):
            head = "g%d" % n
        n += 1
    for name in names + [head]:
        volume.write_file(b"x", FSString(name))
    head_num = volume.get_path_name(FSString(head)).block.blk_num
    tail_num = volume.get_path_name(FSString(tail)).block.blk_num
    assert volume.get_path_name(FSString(head)).block.hash_chain == tail_num
    flipped = volume.get_path_name(FSString(names[2])).block.blk_num
    close_volume(blkdev, volume)
    blkdev = ADFBlockDevice(str(image))
    blkdev.open()
    blk = Block(blkdev, tail_num)
    blk.read()
    blk._put_long(-4, head_num)
    blk._put_chksum()
    blk._write_data()
    blkdev.close()
    if bad:
        flip_checksum(image, flipped)
    before = image.read_bytes()

    bounded_reads(monkeypatch)
    blkdev, volume = open_volume(image)
    want = sorted([head, tail, names[1]] + ([] if bad else [names[2]]))
    got = sorted(e.name.get_unicode_name() for e in volume.root_dir.get_entries())
    assert got == want
    for op in ("write", "delete"):
        with pytest.raises(FSError) as error:
            if op == "write":
                volume.write_file(b"x", FSString("new"))
            else:
                volume.delete(FSString(names[1]))
        assert error.value.code == INVALID_ENTRY_BLOCK
    close_volume(blkdev, volume)
    capsys.readouterr()
    assert xdftool_main([str(image), "list"]) == 0
    assert head in capsys.readouterr().out
    assert image.read_bytes() == before


def deleted_before(volume, path, name):
    """does deleting directory path with all its entries delete one before
    it gets to entry name?"""
    node = volume.get_path_name(FSString(path))
    entry = volume.get_path_name(FSString(path + "/" + name if path else name))
    return entry_read_order(node)[0] != entry.block.blk_num


@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_validate_delete_all_hash_chain_test(tmp_path, dos_type):
    # An entry that is not in the hash chain its name hashes to cannot be
    # unlinked. amitools before df53f16a wrote such entries on HDFs with
    # blocks over 512 bytes. Deleting a tree that holds one is refused
    # before the first entry goes.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    volume.create_dir(FSString("tree"))
    for n in range(5):
        volume.write_file(b"a", FSString("tree/a%d" % n))
    volume.create_dir(FSString("tree/sub"))
    volume.write_file(b"m", FSString("tree/sub/moved"))
    assert deleted_before(volume, "tree", "sub")
    sub = volume.get_path_name(FSString("tree/sub"))
    slot = hash_of(volume, "moved")
    moved_num = sub.block.hash_table[slot]
    sub_num = sub.block.blk_num
    close_volume(blkdev, volume)
    blkdev = ADFBlockDevice(str(image))
    blkdev.open()
    ud = UserDirBlock(blkdev, sub_num, volume.is_longname)
    ud.read()
    ud.hash_table[slot] = 0
    ud.hash_table[(slot + 1) % ud.hash_size] = moved_num
    ud.write()
    blkdev.close()
    before = image.read_bytes()

    blkdev, volume = open_volume(image)
    with pytest.raises(FSError) as error:
        volume.delete(FSString("tree"), all=True)
    assert error.value.code == INTERNAL_ERROR
    assert volume.read_file(FSString("tree/sub/moved")) == b"m"
    close_volume(blkdev, volume)
    assert image.read_bytes() == before


@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_validate_delete_all_root_test(tmp_path, dos_type):
    # Deleting the root with all its entries checks the tree of each entry
    # first: an invalid header in d/sub refuses it before the first entry
    # goes.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    for name in "abcde":
        volume.create_dir(FSString(name))
        volume.write_file(b"x", FSString(name + "/f"))
    volume.create_dir(FSString("d/sub"))
    volume.write_file(b"x", FSString("d/sub/bad"))
    assert deleted_before(volume, "", "d")
    bad = volume.get_path_name(FSString("d/sub/bad")).block.blk_num
    close_volume(blkdev, volume)
    flip_checksum(image, bad)
    before = image.read_bytes()

    blkdev, volume = open_volume(image)
    with pytest.raises(FSError) as error:
        volume.delete(FSString("/"), all=True)
    assert error.value.code == INVALID_ENTRY_BLOCK
    assert len(volume.root_dir.get_entries()) == 5
    close_volume(blkdev, volume)
    assert image.read_bytes() == before


@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_validate_delete_all_root_ok_test(tmp_path, dos_type):
    # Deleting the root with all its entries, as xdftool delete / all does,
    # deletes them and keeps the root, which has no parent to unlink it
    # from. Deleting the root alone is refused, and deletes no entry.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    free = volume.get_free_blocks()
    volume.write_file(b"top", FSString("top"))
    with pytest.raises(FSError) as error:
        volume.delete(FSString("/"))
    assert error.value.code == DELETE_NOT_ALLOWED
    assert volume.read_file(FSString("top")) == b"top"
    for name in "abcde":
        volume.create_dir(FSString(name))
        volume.write_file(b"x", FSString(name + "/f"))
    volume.create_dir(FSString("d/sub"))
    volume.write_file(b"x", FSString("d/sub/f"))
    close_volume(blkdev, volume)

    assert xdftool_main([str(image), "delete", "/", "all"]) == 0
    blkdev, volume = open_volume(image)
    assert volume.root_dir.get_entries() == []
    assert volume.get_free_blocks() == free
    close_volume(blkdev, volume)
    assert validate(image) == []


@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_validate_delete_all_deep_test(tmp_path, dos_type):
    # Deleting a directory with all its entries checks the whole tree
    # before the first entry goes: an invalid header two levels below
    # refuses it.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    path = ""
    for level in ("dir", "sub", "inner"):
        path = path + "/" + level if path else level
        volume.create_dir(FSString(path))
        for n in range(4):
            volume.write_file(b"x", FSString("%s/f%d" % (path, n)))
    assert deleted_before(volume, "dir", "sub")
    bad = volume.get_path_name(FSString("dir/sub/inner/f0")).block.blk_num
    close_volume(blkdev, volume)
    flip_checksum(image, bad)
    before = image.read_bytes()

    blkdev, volume = open_volume(image)
    with pytest.raises(FSError) as error:
        volume.delete(FSString("dir"), all=True)
    assert error.value.code == INVALID_ENTRY_BLOCK
    close_volume(blkdev, volume)
    assert image.read_bytes() == before


@pytest.mark.parametrize("dos_type", DOS_TYPES, ids=dos_id)
def fs_validate_delete_all_reads_test(tmp_path, dos_type, monkeypatch):
    # Deleting a deep tree with all its entries checks it once, and reads
    # each directory once, empty ones too.
    image = tmp_path / "test.adf"
    blkdev, volume = create_volume(image, dos_type)
    path = "t"
    volume.create_dir(FSString(path))
    for level in range(60):
        path += "/d"
        volume.create_dir(FSString(path))
    close_volume(blkdev, volume)

    blkdev, volume = open_volume(image)
    reads = bounded_reads(monkeypatch)
    check_delete = ADFSDir.check_delete
    checks = []

    def counting_check_delete(self, node, all=False, update_ts=True):
        checks.append(node)
        check_delete(self, node, all, update_ts)

    monkeypatch.setattr(ADFSDir, "check_delete", counting_check_delete)
    volume.delete(FSString("t"), all=True)
    # the header of each directory below "t", whose header the volume read
    # when it opened, and on DOS4/5 the dircache block of each directory
    assert len(reads) == 60 + (61 if volume.is_dircache else 0)
    # once for the tree, and once for each delete
    assert len(checks) == 2 * 61
    close_volume(blkdev, volume)
    assert validate(image) == []


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
