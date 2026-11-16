import pytest

from amitools.vamos.handler import (
    MODE_NEWFILE,
    MODE_OLDFILE,
    MODE_READWRITE,
    HandlerError,
    HandlerFileInfo,
    HandlerInfoData,
    RamHandler,
)


def make_handler(name="ram", cfg=None):
    return RamHandler(name, cfg)


def write_file(h, path, data, mode=MODE_NEWFILE):
    fh = h.find_output(path, mode)
    assert h.write(fh, data) == len(data)
    h.end(fh)


def read_file(h, path):
    fh = h.find_input(path)
    data = h.read(fh, -1)
    h.end(fh)
    return data


def expect_error(code, func, *args, **kwargs):
    with pytest.raises(HandlerError) as exc:
        func(*args, **kwargs)
    assert exc.value.code == code
    return exc.value


def handler_ram_locate_test():
    h = make_handler()
    h.create_dir("dir")
    write_file(h, "file.txt", b"hello")
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


def handler_ram_locate_case_test():
    h = make_handler()
    write_file(h, "MixedCase", b"x")
    lock = h.locate_object("mixedcase")
    assert lock.rel_path == "MixedCase"
    assert lock.key == "mixedcase"


def handler_ram_parent_steps_test():
    h = make_handler()
    h.create_dir("a")
    h.create_dir("a/b")
    write_file(h, "a/c", b"x")
    # 'a/b//c' is c in the parent of b
    lock = h.locate_object("a/b//c")
    assert lock.rel_path == "a/c"
    assert lock.key == "a/c"
    # climbing above the volume root fails
    expect_error(205, h.locate_object, "//x")


def handler_ram_dir_ops_test():
    h = make_handler()
    h.create_dir("a")
    h.create_dir("a/b")
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
    write_file(h, "f", b"x")
    file_lock = h.locate_object("f")
    expect_error(212, h.copy_dir, file_lock)


def handler_ram_same_lock_other_handler_test():
    h1 = make_handler("one")
    h2 = make_handler("two")
    a = h1.locate_object("")
    b = h2.locate_object("")
    assert not h1.same_lock(a, b)


def handler_ram_examine_test():
    h = make_handler()
    h.create_dir("dir")
    write_file(h, "file.txt", b"hello")
    lock = h.locate_object("")
    info = h.examine_object(lock)
    assert info.entry_type == HandlerFileInfo.DIR
    assert info.is_dir
    assert info.key == 0
    assert info.name == "ram"
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
    # no enumeration on a file
    expect_error(212, h.examine_next, file_lock, 0)


def handler_ram_examine_cache_test():
    h = make_handler()
    for name in ("a", "b", "c"):
        write_file(h, name, b"x")
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


def handler_ram_info_test():
    h = make_handler()
    lock = h.locate_object("")
    info = h.info(lock)
    assert isinstance(info, HandlerInfoData)
    assert info.num_blocks > 0
    assert info.bytes_per_block > 0
    assert info.disk_state == HandlerInfoData.DISK_STATE_VALIDATED
    disk = h.disk_info(lock)
    assert disk.num_blocks == info.num_blocks


def handler_ram_size_config_test():
    h = make_handler(cfg={"size": "8"})
    # size is given in KiB and reported in 512 byte blocks
    assert h.num_blocks == 16
    info = h.info(h.locate_object(""))
    assert info.num_blocks == 16
    assert info.bytes_per_block == 512


def handler_ram_file_io_test():
    h = make_handler()
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
    assert read_file(h, "up.txt") == b"abc"


def handler_ram_shared_buffer_test():
    # all opens of the same node share one buffer, so handles see each
    # other's writes even though they keep independent file positions
    h = make_handler()
    fh1 = h.find_output("f", MODE_NEWFILE)
    h.write(fh1, b"abc")
    fh2 = h.find_output("f", MODE_READWRITE)
    assert h.read(fh2, 10) == b"abc"
    h.seek(fh2, 0, 0)
    h.write(fh2, b"X")
    assert h.seek(fh1, 0, 0) == 0
    assert h.read(fh1, 10) == b"Xbc"
    h.end(fh1)
    h.end(fh2)


def handler_ram_seek_limit_test():
    h = make_handler()
    fh = h.find_output("f", MODE_NEWFILE)
    h.write(fh, b"0123456789")
    h.flush(fh)
    # a seek beyond EOF is clamped back to EOF and reported as -2
    assert h.seek(fh, 100, 0) == -2
    # ...and the file pointer now sits at the end of the file
    assert h.seek(fh, 0, 1) == 10
    # a normal seek returns the new position
    assert h.seek(fh, 2, 0) == 2
    h.end(fh)
    assert read_file(h, "f") == b"0123456789"


def handler_ram_readwrite_mode_test():
    h = make_handler()
    fh = h.find_output("f", MODE_READWRITE)
    h.write(fh, b"12345")
    h.end(fh)
    # re-open read/write keeps the content
    fh = h.find_output("f", MODE_READWRITE)
    assert h.seek(fh, 1, 0) == 1
    h.write(fh, b"X")
    h.end(fh)
    assert read_file(h, "f") == b"1X345"


def handler_ram_set_file_size_test():
    h = make_handler()
    fh = h.find_output("f", MODE_NEWFILE)
    h.write(fh, b"0123456789")
    assert h.set_file_size(fh, 4, -1) == 4
    h.end(fh)
    assert read_file(h, "f") == b"0123"
    # grow the file again with zeros
    fh = h.find_output("f", MODE_READWRITE)
    assert h.set_file_size(fh, 6, -1) == 6
    h.end(fh)
    assert read_file(h, "f") == b"0123\x00\x00"


def handler_ram_delete_test():
    h = make_handler()
    write_file(h, "f", b"x")
    h.delete_object("f")
    expect_error(205, h.locate_object, "f")
    # non-empty dir
    h.create_dir("d")
    write_file(h, "d/x", b"x")
    expect_error(216, h.delete_object, "d")
    h.delete_object("d/x")
    h.delete_object("d")
    expect_error(205, h.locate_object, "d")
    # missing
    expect_error(205, h.delete_object, "gone")


def handler_ram_rename_test():
    h = make_handler()
    write_file(h, "a", b"x")
    h.rename_object("a", "b")
    assert h.locate_object("b")
    expect_error(205, h.locate_object, "a")
    # renaming a missing object fails
    expect_error(205, h.rename_object, "a", "c")
    # renaming onto an existing object is rejected
    write_file(h, "c", b"x")
    expect_error(202, h.rename_object, "b", "c")


def handler_ram_protect_comment_date_test():
    h = make_handler()
    write_file(h, "f", b"x")
    h.set_protect("f", 0x123)
    h.set_comment("f", "hello")
    h.set_date("f", 1000000)
    info = h.examine_object(h.locate_object("f"))
    assert info.protection == 0x123
    assert info.comment == "hello"
    assert info.date == 1000000
    # missing objects fail
    expect_error(205, h.set_protect, "gone", 0)
    expect_error(205, h.set_comment, "gone", "x")
    expect_error(205, h.set_date, "gone", 0)


def handler_ram_create_dir_test():
    h = make_handler()
    h.create_dir("newdir")
    assert h.locate_object("newdir")
    expect_error(203, h.create_dir, "newdir")
    # the parent must exist
    expect_error(205, h.create_dir, "missing/sub")


def handler_ram_fh_from_lock_test():
    h = make_handler()
    write_file(h, "f", b"data")
    lock = h.locate_object("f")
    fh = h.fh_from_lock(lock, MODE_OLDFILE)
    assert h.read(fh, 10) == b"data"
    h.end(fh)
    dir_lock = h.locate_object("")
    expect_error(212, h.fh_from_lock, dir_lock)


def handler_ram_base_unsupported_test():
    from amitools.vamos.handler import Handler

    handler = Handler("dummy")
    with pytest.raises(HandlerError) as exc:
        handler.find_input("x")
    assert exc.value.code == 209
