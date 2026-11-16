"""Cross-handler conformance tests at the handler API boundary.

The same operations are run against :class:`HostFileSysHandler` and
:class:`RamHandler`, so both file systems are exercised through the
packet-backed handler API with identical expectations. Only behavior common
to both handlers is asserted here; handler-specific details (host comments,
exact protection masks, rename-overwrite, ...) stay in ``handler_filesys.py``
and ``handler_ram.py``.

A coverage guard checks that every method in ``ACTION_METHODS`` is reachable
on both handlers, so the API surface stays complete.
"""

from types import SimpleNamespace

import pytest

from amitools.vamos.handler import (
    MODE_NEWFILE,
    MODE_OLDFILE,
    MODE_READWRITE,
    HandlerError,
    HandlerFileInfo,
    HandlerInfoData,
    HostFileSysHandler,
    RamHandler,
)
from amitools.vamos.handler.base import ACTION_METHODS


@pytest.fixture(params=["hostfs", "ram"])
def env(request, tmp_path):
    """a handler of each type with a volume named ``work``

    The host volume root is named ``work`` too, so the root's examine name is
    the volume name for both handlers.
    """
    kind = request.param
    if kind == "hostfs":
        root = tmp_path / "work"
        root.mkdir()
        handler = HostFileSysHandler("work", str(root))
    else:
        root = None
        handler = RamHandler("work")
    return SimpleNamespace(kind=kind, h=handler, root=root)


def make_dir(h, path):
    h.create_dir(path)


def make_file(h, path, data=b""):
    fh = h.find_output(path, MODE_NEWFILE)
    if data:
        assert h.write(fh, data) == len(data)
    h.end(fh)


def read_all(h, path):
    fh = h.find_input(path)
    data = h.read(fh, -1)
    h.end(fh)
    return data


def expect_error(code, func, *args, **kwargs):
    with pytest.raises(HandlerError) as exc:
        func(*args, **kwargs)
    assert exc.value.code == code
    return exc.value


# ----- locks -----


def handler_conf_locate_object_test(env):
    h = env.h
    make_dir(h, "dir")
    make_file(h, "file.txt", b"hello")
    lock = h.locate_object("dir")
    assert lock.rel_path == "dir"
    assert lock.key == "dir"
    assert lock.handler is h
    assert h.locate_object("file.txt").key == "file.txt"
    # the volume root
    root = h.locate_object("")
    assert root.key == ""
    assert root.rel_path == ""
    # missing object
    expect_error(205, h.locate_object, "missing")


def handler_conf_locate_case_test(env):
    h = env.h
    make_file(h, "MixedCase", b"x")
    lock = h.locate_object("mixedcase")
    assert lock.rel_path == "MixedCase"
    assert lock.key == "mixedcase"


def handler_conf_parent_steps_test(env):
    h = env.h
    make_dir(h, "a")
    make_dir(h, "a/b")
    make_file(h, "a/c", b"x")
    # 'a/b//c' is c in the parent of b
    lock = h.locate_object("a/b//c")
    assert lock.rel_path == "a/c"
    assert lock.key == "a/c"
    # climbing above the volume root fails
    expect_error(205, h.locate_object, "//x")


def handler_conf_free_lock_test(env):
    h = env.h
    lock = h.locate_object("")
    # releasing a lock is a no-op that must not raise
    h.free_lock(lock)


def handler_conf_copy_dir_test(env):
    h = env.h
    make_dir(h, "a")
    make_dir(h, "a/b")
    lock = h.locate_object("a/b")
    copy = h.copy_dir(lock)
    assert copy.key == "a/b"
    assert h.same_lock(lock, copy)
    # copy_dir only works on directories
    make_file(h, "f", b"x")
    expect_error(212, h.copy_dir, h.locate_object("f"))


def handler_conf_parent_test(env):
    h = env.h
    make_dir(h, "a")
    make_dir(h, "a/b")
    parent = h.parent(h.locate_object("a/b"))
    assert parent.key == "a"
    grand = h.parent(parent)
    assert grand.key == ""
    # the volume root has no parent
    expect_error(205, h.parent, grand)


def handler_conf_same_lock_test(env):
    h = env.h
    lock = h.locate_object("")
    assert h.same_lock(lock, h.copy_dir(lock))
    # a lock of another handler is never the same
    if env.kind == "hostfs":
        other = HostFileSysHandler("other", str(env.root))
    else:
        other = RamHandler("other")
    assert not h.same_lock(lock, other.locate_object(""))


# ----- examine / info -----


def handler_conf_examine_object_test(env):
    h = env.h
    make_dir(h, "dir")
    make_file(h, "file.txt", b"hello")
    info = h.examine_object(h.locate_object(""))
    assert info.entry_type == HandlerFileInfo.DIR
    assert info.is_dir
    assert info.key == 0
    assert info.name == "work"
    file_info = h.examine_object(h.locate_object("file.txt"))
    assert file_info.entry_type == HandlerFileInfo.FILE
    assert not file_info.is_dir
    assert file_info.name == "file.txt"
    assert file_info.size == 5
    assert file_info.blocks == 1


def handler_conf_examine_next_test(env):
    h = env.h
    make_dir(h, "dir")
    make_file(h, "file.txt", b"hello")
    lock = h.locate_object("")
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
    # a file cannot be enumerated
    expect_error(212, h.examine_next, h.locate_object("file.txt"), 0)


def handler_conf_examine_cache_test(env):
    h = env.h
    for name in ("a", "b", "c"):
        make_file(h, name, b"x")
    lock = h.locate_object("")
    first = h.examine_next(lock, 0).name
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


def handler_conf_info_test(env):
    h = env.h
    lock = h.locate_object("")
    info = h.info(lock)
    assert isinstance(info, HandlerInfoData)
    assert info.num_blocks > 0
    assert info.bytes_per_block > 0
    assert info.disk_state == HandlerInfoData.DISK_STATE_VALIDATED
    disk = h.disk_info(lock)
    assert disk.num_blocks == info.num_blocks


# ----- files -----


def handler_conf_find_input_test(env):
    h = env.h
    make_file(h, "f", b"data")
    fh = h.find_input("f")
    assert h.read(fh, 10) == b"data"
    h.end(fh)
    expect_error(205, h.find_input, "missing")
    # a directory is not a file
    make_dir(h, "d")
    expect_error(205, h.find_input, "d")


def handler_conf_find_output_modes_test(env):
    h = env.h
    # MODE_NEWFILE creates and truncates
    make_file(h, "f", b"hello")
    fh = h.find_output("f", MODE_NEWFILE)
    h.end(fh)
    assert read_all(h, "f") == b""
    # MODE_READWRITE creates a missing file and keeps existing content
    fh = h.find_output("rw", MODE_READWRITE)
    h.write(fh, b"abc")
    h.end(fh)
    assert read_all(h, "rw") == b"abc"
    # MODE_OLDFILE requires an existing file
    expect_error(205, h.find_output, "nope", MODE_OLDFILE)
    fh = h.find_output("f", MODE_OLDFILE)
    h.end(fh)


def handler_conf_find_update_test(env):
    h = env.h
    fh = h.find_update("up")
    h.write(fh, b"abc")
    h.end(fh)
    assert read_all(h, "up") == b"abc"


def handler_conf_read_write_test(env):
    h = env.h
    fh = h.find_output("f", MODE_NEWFILE)
    assert h.write(fh, b"hello") == 5
    h.flush(fh)
    h.end(fh)
    fh = h.find_input("f")
    assert h.read(fh, 2) == b"he"
    assert h.seek(fh, 0, 0) == 0
    assert h.read(fh, 10) == b"hello"
    h.end(fh)


def handler_conf_seek_limit_test(env):
    h = env.h
    fh = h.find_output("f", MODE_NEWFILE)
    h.write(fh, b"0123456789")
    h.flush(fh)
    # a seek beyond EOF is clamped back to EOF and reported as -2
    assert h.seek(fh, 100, 0) == -2
    assert h.seek(fh, 0, 1) == 10
    assert h.seek(fh, 2, 0) == 2
    h.end(fh)
    assert read_all(h, "f") == b"0123456789"


def handler_conf_set_file_size_test(env):
    h = env.h
    # OFFSET_BEGINNING: size = offset
    fh = h.find_output("f", MODE_NEWFILE)
    h.write(fh, b"0123456789")
    assert h.set_file_size(fh, 4, -1) == 4
    h.end(fh)
    assert read_all(h, "f") == b"0123"
    # OFFSET_END: size = file size + offset
    fh = h.find_output("g", MODE_NEWFILE)
    h.write(fh, b"0123456789")
    assert h.set_file_size(fh, 2, 1) == 12
    h.end(fh)
    assert read_all(h, "g") == b"0123456789\x00\x00"
    # OFFSET_CURRENT: size = position + offset
    fh = h.find_output("h", MODE_NEWFILE)
    h.write(fh, b"0123456789")
    assert h.set_file_size(fh, -1, 0) == 9
    h.end(fh)
    assert read_all(h, "h") == b"012345678"


def handler_conf_fh_from_lock_test(env):
    h = env.h
    make_file(h, "f", b"data")
    fh = h.fh_from_lock(h.locate_object("f"), MODE_OLDFILE)
    assert h.read(fh, 10) == b"data"
    h.end(fh)
    # a directory cannot be opened as a file
    expect_error(212, h.fh_from_lock, h.locate_object(""))


def handler_conf_parent_copy_fh_test(env):
    h = env.h
    make_dir(h, "d")
    make_file(h, "d/x", b"q")
    # parent_fh operates on an open file handle
    fh = h.find_input("d/x")
    assert h.parent_fh(fh).key == "d"
    h.end(fh)
    # copy_dir_fh returns a lock on the same directory object
    assert h.copy_dir_fh(h.locate_object("d")).key == "d"


# ----- names -----


def handler_conf_delete_object_test(env):
    h = env.h
    make_file(h, "f", b"x")
    h.delete_object("f")
    expect_error(205, h.locate_object, "f")
    # a non-empty directory cannot be deleted
    make_dir(h, "d")
    make_file(h, "d/x", b"x")
    expect_error(216, h.delete_object, "d")
    h.delete_object("d/x")
    h.delete_object("d")
    expect_error(205, h.locate_object, "d")
    expect_error(205, h.delete_object, "gone")


def handler_conf_rename_object_test(env):
    h = env.h
    make_file(h, "a", b"x")
    h.rename_object("a", "b")
    assert h.locate_object("b").key == "b"
    expect_error(205, h.locate_object, "a")
    expect_error(205, h.rename_object, "a", "c")
    # rename across directories
    make_dir(h, "d")
    make_file(h, "e", b"x")
    h.rename_object("e", "d/e")
    assert read_all(h, "d/e") == b"x"


def handler_conf_set_protect_test(env):
    h = env.h
    make_file(h, "f", b"x")
    # the exact mask mapping is host-specific; both must accept it
    h.set_protect("f", 0)
    expect_error(205, h.set_protect, "gone", 0)


def handler_conf_set_comment_test(env):
    h = env.h
    make_file(h, "f", b"x")
    h.set_comment("f", "hello")
    # hostfs cannot store comments; ram round-trips them
    if env.kind == "ram":
        assert h.examine_object(h.locate_object("f")).comment == "hello"


def handler_conf_set_date_test(env):
    h = env.h
    make_file(h, "f", b"x")
    h.set_date("f", 1000000)
    assert h.examine_object(h.locate_object("f")).date == 1000000
    expect_error(205, h.set_date, "gone", 0)


def handler_conf_create_dir_test(env):
    h = env.h
    h.create_dir("newdir")
    assert h.locate_object("newdir").key == "newdir"
    expect_error(203, h.create_dir, "newdir")
    # nested dirs need their parent to exist first
    h.create_dir("newdir/sub")
    assert h.locate_object("newdir/sub").key == "newdir/sub"


# ----- interactive ops are unsupported on a file system -----


def handler_conf_set_mode_unsupported_test(env):
    h = env.h
    fh = h.find_output("f", MODE_NEWFILE)
    expect_error(209, h.set_mode, fh, True)
    h.end(fh)


def handler_conf_wait_for_char_unsupported_test(env):
    h = env.h
    fh = h.find_output("f", MODE_NEWFILE)
    expect_error(209, h.wait_for_char, fh, 0)
    h.end(fh)


# ----- API surface -----


def handler_conf_action_methods_test(env):
    # every packet-backed handler method is present on both handlers
    for name in ACTION_METHODS:
        assert callable(getattr(env.h, name, None)), name


def handler_conf_every_action_is_exercised_test():
    """guard: this module calls every packet-backed handler method

    Keeps the conformance suite complete as the API grows: a new
    ``ACTION_METHODS`` entry must get a test here.
    """
    import inspect
    import re
    import sys

    source = inspect.getsource(sys.modules[__name__])
    missing = [
        name
        for name in ACTION_METHODS
        if not re.search(rf"\.{re.escape(name)}\b", source)
    ]
    assert not missing, f"handler methods not exercised: {missing}"
