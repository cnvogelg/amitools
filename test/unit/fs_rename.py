"""ADFS rename tests.

``ADFSVolume.rename`` is the fs half of the handler's ``rename_object``
action. It moves an entry within a directory or into another one without
copying its blocks, and must leave the entry in exactly one hash chain.
"""

import pytest

from amitools.fs import DosType
from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.FSError import FILE_NOT_FOUND, NAME_ALREADY_EXISTS, FSError
from amitools.fs.FSString import FSString
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


def root_entry_blocks(volume):
    return [e.block.blk_num for e in volume.root_dir.get_entries()]


def fs_rename_same_dir_test(tmp_path):
    volume, blkdev = make_volume(tmp_path)
    volume.write_file(b"hello", FSString("a"))
    volume.rename(FSString("a"), FSString("b"))
    check = reopen(blkdev)
    assert check.get_path_name(FSString("a")) is None
    node = check.get_file_path_name(FSString("b"))
    assert node.get_file_data() == b"hello"
    # the node is in exactly one chain
    assert root_entry_blocks(check).count(node.block.blk_num) == 1


def fs_rename_move_into_dir_test(tmp_path):
    volume, blkdev = make_volume(tmp_path)
    volume.create_dir(FSString("d"))
    volume.write_file(b"x", FSString("a"))
    volume.rename(FSString("a"), FSString("d/a"))
    check = reopen(blkdev)
    assert check.get_path_name(FSString("a")) is None
    node = check.get_file_path_name(FSString("d/a"))
    assert node.get_file_data() == b"x"
    # the entry left the root chain
    assert node.block.blk_num not in root_entry_blocks(check)


def fs_rename_dir_with_children_test(tmp_path):
    volume, blkdev = make_volume(tmp_path)
    volume.create_dir(FSString("d"))
    volume.write_file(b"q", FSString("d/x"))
    volume.rename(FSString("d"), FSString("e"))
    check = reopen(blkdev)
    assert check.get_dir_path_name(FSString("d")) is None
    node = check.get_file_path_name(FSString("e/x"))
    assert node.get_file_data() == b"q"


def fs_rename_case_only_test(tmp_path):
    # renaming to a different case changes the stored name
    volume, blkdev = make_volume(tmp_path)
    volume.write_file(b"x", FSString("Name"))
    volume.rename(FSString("Name"), FSString("name"))
    check = reopen(blkdev)
    node = check.get_file_path_name(FSString("name"))
    assert node.get_file_data() == b"x"
    assert node.name.get_unicode_name() == "name"


def fs_rename_missing_source_test(tmp_path):
    volume, _ = make_volume(tmp_path)
    with pytest.raises(FSError) as e:
        volume.rename(FSString("a"), FSString("b"))
    assert e.value.code == FILE_NOT_FOUND


def fs_rename_name_conflict_test(tmp_path):
    volume, _ = make_volume(tmp_path)
    volume.write_file(b"a", FSString("a"))
    volume.write_file(b"b", FSString("b"))
    with pytest.raises(FSError) as e:
        volume.rename(FSString("a"), FSString("b"))
    assert e.value.code == NAME_ALREADY_EXISTS


@pytest.mark.parametrize(
    "dos_type",
    [DosType.DOS0, DosType.DOS5, DosType.DOS7],
    ids=["ofs", "dircache", "longname"],
)
def fs_rename_dos_types_test(tmp_path, dos_type):
    volume, blkdev = make_volume(tmp_path, dos_type=dos_type)
    volume.create_dir(FSString("d"))
    volume.write_file(b"hello", FSString("d/a"))
    volume.rename(FSString("d/a"), FSString("d/b"))
    volume.rename(FSString("d/b"), FSString("c"))
    check = reopen(blkdev)
    assert check.get_path_name(FSString("d/b")) is None
    assert check.get_file_path_name(FSString("c")).get_file_data() == b"hello"


def fs_rename_failure_leaves_one_chain_test(tmp_path):
    volume, blkdev = make_volume(tmp_path)
    volume.write_file(b"hello", FSString("a"))
    node = volume.get_file_path_name(FSString("a"))
    fail_blk = node.block.blk_num
    orig = blkdev.write_block
    state = {"fired": False}

    def flaky(blk_num, data):
        # fail the node's header write once, in the middle of the rename
        if blk_num == fail_blk and not state["fired"]:
            state["fired"] = True
            raise IOError("boom")
        return orig(blk_num, data)

    blkdev.write_block = flaky
    with pytest.raises(IOError):
        volume.rename(FSString("a"), FSString("b"))
    blkdev.write_block = orig
    check = reopen(blkdev)
    # the node is back at its old place, in exactly one chain
    old = check.get_path_name(FSString("a"))
    assert old is not None
    assert check.get_path_name(FSString("b")) is None
    assert root_entry_blocks(check).count(old.block.blk_num) == 1
