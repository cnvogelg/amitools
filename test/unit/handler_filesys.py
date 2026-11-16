import os

import pytest

from amitools.vamos.handler import (
    HandlerError,
    HandlerFileInfo,
    HandlerInfoData,
    HostFileSysHandler,
    MODE_NEWFILE,
    MODE_OLDFILE,
    MODE_READWRITE,
)


def make_handler(tmp_path, name="work"):
    root = tmp_path / "root"
    root.mkdir()
    return HostFileSysHandler(name, str(root)), root


def expect_error(code, func, *args, **kwargs):
    with pytest.raises(HandlerError) as exc:
        func(*args, **kwargs)
    assert exc.value.code == code
    return exc.value


def handler_filesys_locate_test(tmp_path):
    h, root = make_handler(tmp_path)
    (root / "dir").mkdir()
    (root / "file.txt").write_bytes(b"hello")
    lock = h.locate_object("dir")
    assert lock.rel_path == "dir"
    assert lock.key == "dir"
    assert lock.handler is h
    file_lock = h.locate_object("file.txt")
    assert file_lock.key == "file.txt"
    # volume root
    root_lock = h.locate_object("")
    assert root_lock.key == ""
    assert root_lock.rel_path == ""
    # missing
    expect_error(205, h.locate_object, "missing")


def handler_filesys_locate_case_test(tmp_path):
    h, root = make_handler(tmp_path)
    (root / "MixedCase").write_bytes(b"x")
    lock = h.locate_object("mixedcase")
    assert lock.rel_path == "MixedCase"
    assert lock.key == "mixedcase"


def handler_filesys_parent_steps_test(tmp_path):
    h, root = make_handler(tmp_path)
    (root / "a" / "b").mkdir(parents=True)
    (root / "a" / "c").write_bytes(b"x")
    # 'a/b//c' is c in the parent of b
    lock = h.locate_object("a/b//c")
    assert lock.rel_path == "a/c"
    assert lock.key == "a/c"
    # climbing above the volume root fails
    expect_error(205, h.locate_object, "//x")


def handler_filesys_dir_ops_test(tmp_path):
    h, root = make_handler(tmp_path)
    (root / "a" / "b").mkdir(parents=True)
    lock = h.locate_object("a/b")
    copy = h.copy_dir(lock)
    assert copy.key == "a/b"
    assert h.same_lock(lock, copy)
    parent = h.parent(lock)
    assert parent.key == "a"
    grand = h.parent(parent)
    assert grand.key == ""
    # volume root has no parent
    expect_error(205, h.parent, grand)
    # copy_dir only works on dirs
    (root / "f").write_bytes(b"x")
    file_lock = h.locate_object("f")
    expect_error(212, h.copy_dir, file_lock)


def handler_filesys_same_lock_other_handler_test(tmp_path):
    h1, _ = make_handler(tmp_path, "one")
    root2 = tmp_path / "root2"
    root2.mkdir()
    h2 = HostFileSysHandler("two", str(root2))
    a = h1.locate_object("")
    b = h2.locate_object("")
    assert not h1.same_lock(a, b)


def handler_filesys_examine_test(tmp_path):
    h, root = make_handler(tmp_path)
    (root / "dir").mkdir()
    (root / "file.txt").write_bytes(b"hello")
    lock = h.locate_object("")
    info = h.examine_object(lock)
    assert info.entry_type == HandlerFileInfo.DIR
    assert info.is_dir
    assert info.key == 0
    assert info.name == "root"
    # enumerate
    names = []
    key = 0
    while True:
        try:
            entry = h.examine_next(lock, key)
        except HandlerError as e:
            assert e.code == 232
            break
        names.append(entry.name)
        key = entry.key
    assert set(names) == {"dir", "file.txt"}
    # examine a file
    file_lock = h.locate_object("file.txt")
    finfo = h.examine_object(file_lock)
    assert finfo.entry_type == HandlerFileInfo.FILE
    assert not finfo.is_dir
    assert finfo.name == "file.txt"
    assert finfo.size == 5
    assert finfo.blocks == 1
    assert finfo.date > 0
    # no enumeration on a file
    expect_error(212, h.examine_next, file_lock, 0)


def handler_filesys_examine_cache_test(tmp_path):
    h, root = make_handler(tmp_path)
    for name in ("a", "b", "c"):
        (root / name).write_bytes(b"x")
    lock = h.locate_object("")
    first = h.examine_next(lock, 0).name
    # the cached listing keeps the order stable for continuation
    rest = []
    key = 1
    while True:
        try:
            entry = h.examine_next(lock, key)
        except HandlerError as e:
            assert e.code == 232
            break
        rest.append(entry.name)
        key = entry.key
    assert len(rest) == 2
    assert first not in rest
    assert set([first] + rest) == {"a", "b", "c"}


def handler_filesys_info_test(tmp_path):
    h, root = make_handler(tmp_path)
    lock = h.locate_object("")
    info = h.info(lock)
    assert isinstance(info, HandlerInfoData)
    assert info.num_blocks > 0
    assert info.bytes_per_block > 0
    assert info.disk_state == HandlerInfoData.DISK_STATE_VALIDATED
    disk = h.disk_info(lock)
    assert disk.num_blocks == info.num_blocks


def handler_filesys_file_io_test(tmp_path):
    h, root = make_handler(tmp_path)
    fh = h.find_output("new.txt", MODE_NEWFILE)
    assert h.write(fh, b"hello") == 5
    h.flush(fh)
    h.end(fh)
    # read back
    fh = h.find_input("new.txt")
    assert h.read(fh, 2) == b"he"
    assert h.seek(fh, 0, 0) == 0
    assert h.read(fh, 10) == b"hello"
    h.end(fh)
    # missing input
    expect_error(205, h.find_input, "nope.txt")
    # old file output requires the file to exist
    expect_error(205, h.find_output, "nope.txt", MODE_OLDFILE)
    # update creates the file if needed
    fh = h.find_update("up.txt")
    h.write(fh, b"abc")
    h.end(fh)
    assert (root / "up.txt").read_bytes() == b"abc"


def handler_filesys_readwrite_mode_test(tmp_path):
    h, root = make_handler(tmp_path)
    fh = h.find_output("f", MODE_READWRITE)
    h.write(fh, b"12345")
    h.end(fh)
    # re-open read/write keeps the content
    fh = h.find_output("f", MODE_READWRITE)
    assert h.seek(fh, 1, 0) == 1
    h.write(fh, b"X")
    h.end(fh)
    assert (root / "f").read_bytes() == b"1X345"


def handler_filesys_set_file_size_test(tmp_path):
    h, root = make_handler(tmp_path)
    fh = h.find_output("f", MODE_NEWFILE)
    h.write(fh, b"0123456789")
    assert h.set_file_size(fh, 4, -1) == 4
    h.end(fh)
    assert (root / "f").read_bytes() == b"0123"


def handler_filesys_delete_test(tmp_path):
    h, root = make_handler(tmp_path)
    (root / "f").write_bytes(b"x")
    h.delete_object("f")
    assert not (root / "f").exists()
    # non-empty dir
    (root / "d").mkdir()
    (root / "d" / "x").write_bytes(b"x")
    expect_error(216, h.delete_object, "d")
    (root / "d" / "x").unlink()
    h.delete_object("d")
    assert not (root / "d").exists()
    # missing
    expect_error(205, h.delete_object, "gone")


def handler_filesys_rename_test(tmp_path):
    h, root = make_handler(tmp_path)
    (root / "a").write_bytes(b"x")
    h.rename_object("a", "b")
    assert (root / "b").exists()
    assert not (root / "a").exists()
    expect_error(205, h.rename_object, "a", "c")


def handler_filesys_protect_date_test(tmp_path):
    h, root = make_handler(tmp_path)
    (root / "f").write_bytes(b"x")
    # clear all protection bits -> owner readable/writable
    h.set_protect("f", 0)
    assert os.access(root / "f", os.R_OK)
    expect_error(205, h.set_protect, "gone", 0)
    h.set_date("f", 1000000)
    assert os.path.getmtime(root / "f") == 1000000
    expect_error(205, h.set_date, "gone", 0)


def handler_filesys_create_dir_test(tmp_path):
    h, root = make_handler(tmp_path)
    h.create_dir("newdir")
    assert (root / "newdir").is_dir()
    expect_error(203, h.create_dir, "newdir")


def handler_filesys_fh_from_lock_test(tmp_path):
    h, root = make_handler(tmp_path)
    (root / "f").write_bytes(b"data")
    lock = h.locate_object("f")
    fh = h.fh_from_lock(lock, MODE_OLDFILE)
    assert h.read(fh, 10) == b"data"
    h.end(fh)
    dir_lock = h.locate_object("")
    expect_error(212, h.fh_from_lock, dir_lock)


def handler_filesys_base_unsupported_test(tmp_path):
    from amitools.vamos.handler import Handler

    handler = Handler("dummy")
    with pytest.raises(HandlerError) as exc:
        handler.find_input("x")
    assert exc.value.code == 209
