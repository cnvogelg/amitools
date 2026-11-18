"""Shared conformance contract for file-system handlers.

``HandlerContract`` holds the handler-API tests whose expectations are the
same for every file-system handler. The handler-specific test modules
(``handler_filesys.py``, ``handler_ram.py``) subclass it and provide an
``env`` fixture, so the same contract runs against each handler without
duplicating the tests.

Only behavior common to all handlers is asserted here. Handler-specific
details (host comments, exact protection masks, rename-overwrite vs ``202``,
missing-parent ``203`` vs ``205``, ...) belong in the handler-specific test
modules.

``env`` is a namespace with:

- ``kind``: the handler type (``"hostfs"`` / ``"ram"``)
- ``h``: the handler under test
- ``new_handler(name)``: build another handler of the same type

The module also holds the two contract tests that need no ``env``: the base
``Handler`` being unsupported, and a guard that every packet-backed method is
exercised here.
"""

import pytest

from amitools.vamos.handler import (
    MODE_NEWFILE,
    MODE_OLDFILE,
    MODE_READWRITE,
    HandlerError,
    HandlerFileInfo,
    HandlerInfoData,
)
from amitools.vamos.handler.base import ACTION_METHODS


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


class HandlerContract:
    """packet-backed handler behavior shared by all file systems.

    Subclasses must provide an ``env`` fixture (see the module docstring).
    """

    # ----- locks -----

    def locate_object_test(self, env):
        h = env.h
        make_dir(h, "dir")
        make_file(h, "file.txt", b"hello")
        lock = h.locate_object("dir")
        # a lock is opaque; its object is observed by examining it
        assert h.examine_object(lock).name == "dir"
        assert lock.handler is h
        assert h.examine_object(h.locate_object("file.txt")).name == "file.txt"
        # the volume root is named after the handler
        root = h.locate_object("")
        assert h.examine_object(root).name == h.name
        # missing object
        expect_error(205, h.locate_object, "missing")

    def locate_case_test(self, env):
        h = env.h
        make_file(h, "MixedCase", b"x")
        lock = h.locate_object("mixedcase")
        # the lock is found case-insensitively but names the real object
        assert h.examine_object(lock).name == "MixedCase"

    def parent_steps_test(self, env):
        h = env.h
        make_dir(h, "a")
        make_dir(h, "a/b")
        make_file(h, "a/c", b"x")
        # 'a/b//c' is c in the parent of b
        lock = h.locate_object("a/b//c")
        assert h.same_lock(lock, h.locate_object("a/c"))
        # climbing above the volume root fails
        expect_error(205, h.locate_object, "//x")

    def free_lock_test(self, env):
        h = env.h
        lock = h.locate_object("")
        # releasing a lock is a no-op that must not raise
        h.free_lock(lock)

    def copy_dir_test(self, env):
        h = env.h
        make_dir(h, "a")
        make_dir(h, "a/b")
        lock = h.locate_object("a/b")
        copy = h.copy_dir(lock)
        assert h.same_lock(lock, copy)
        # copy_dir replicates any lock, including a file lock
        make_file(h, "f", b"x")
        file_lock = h.locate_object("f")
        assert h.same_lock(h.copy_dir(file_lock), file_lock)

    def parent_test(self, env):
        h = env.h
        make_dir(h, "a")
        make_dir(h, "a/b")
        parent = h.parent(h.locate_object("a/b"))
        assert h.same_lock(parent, h.locate_object("a"))
        grand = h.parent(parent)
        assert h.same_lock(grand, h.locate_object(""))
        # the volume root has no parent
        expect_error(205, h.parent, grand)

    def same_lock_test(self, env):
        h = env.h
        lock = h.locate_object("")
        assert h.same_lock(lock, h.copy_dir(lock))
        # a lock of another handler is never the same
        other = env.new_handler("other")
        assert not h.same_lock(lock, other.locate_object(""))

    # ----- examine / info -----

    def examine_object_test(self, env):
        h = env.h
        make_dir(h, "dir")
        make_file(h, "file.txt", b"hello")
        info = h.examine_object(h.locate_object(""))
        assert info.entry_type == HandlerFileInfo.DIR
        assert info.is_dir
        assert info.key == 0
        assert info.name == h.name
        file_info = h.examine_object(h.locate_object("file.txt"))
        assert file_info.entry_type == HandlerFileInfo.FILE
        assert not file_info.is_dir
        assert file_info.name == "file.txt"
        assert file_info.size == 5
        # the exact block accounting (header/fs blocks) is handler-specific
        assert file_info.blocks >= 1

    def examine_next_test(self, env):
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

    def examine_cache_test(self, env):
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

    def info_test(self, env):
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

    def find_input_test(self, env):
        h = env.h
        make_file(h, "f", b"data")
        fh = h.find_input("f")
        assert h.read(fh, 10) == b"data"
        h.end(fh)
        expect_error(205, h.find_input, "missing")
        # a directory is not a file
        make_dir(h, "d")
        expect_error(205, h.find_input, "d")

    def find_output_modes_test(self, env):
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

    def find_update_test(self, env):
        h = env.h
        fh = h.find_update("up")
        h.write(fh, b"abc")
        h.end(fh)
        assert read_all(h, "up") == b"abc"

    def read_write_test(self, env):
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

    def seek_limit_test(self, env):
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

    def set_file_size_test(self, env):
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

    def fh_from_lock_test(self, env):
        h = env.h
        make_file(h, "f", b"data")
        fh = h.fh_from_lock(h.locate_object("f"), MODE_OLDFILE)
        assert h.read(fh, 10) == b"data"
        h.end(fh)
        # a directory cannot be opened as a file
        expect_error(212, h.fh_from_lock, h.locate_object(""))

    def parent_copy_fh_test(self, env):
        h = env.h
        make_dir(h, "d")
        make_file(h, "d/x", b"q")
        # parent_fh operates on an open file handle
        fh = h.find_input("d/x")
        assert h.same_lock(h.parent_fh(fh), h.locate_object("d"))
        # copy_dir_fh locks the file opened by the handle
        assert h.same_lock(h.copy_dir_fh(fh), h.locate_object("d/x"))
        h.end(fh)

    # ----- names -----

    def delete_object_test(self, env):
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

    def rename_object_test(self, env):
        h = env.h
        make_file(h, "a", b"x")
        h.rename_object("a", "b")
        assert h.examine_object(h.locate_object("b")).name == "b"
        expect_error(205, h.locate_object, "a")
        expect_error(205, h.rename_object, "a", "c")
        # rename across directories
        make_dir(h, "d")
        make_file(h, "e", b"x")
        h.rename_object("e", "d/e")
        assert read_all(h, "d/e") == b"x"

    def set_protect_test(self, env):
        h = env.h
        make_file(h, "f", b"x")
        # the exact mask mapping is host-specific; both must accept it
        h.set_protect("f", 0)
        expect_error(205, h.set_protect, "gone", 0)

    def set_comment_test(self, env):
        h = env.h
        make_file(h, "f", b"x")
        # whether the comment is stored is handler-specific; the call must work
        h.set_comment("f", "hello")

    def set_date_test(self, env):
        h = env.h
        make_file(h, "f", b"x")
        # a date after the Amiga epoch (1978), so every handler can store it
        h.set_date("f", 1000000000)
        assert h.examine_object(h.locate_object("f")).date == 1000000000
        expect_error(205, h.set_date, "gone", 0)

    def create_dir_test(self, env):
        h = env.h
        h.create_dir("newdir")
        assert h.examine_object(h.locate_object("newdir")).name == "newdir"
        expect_error(203, h.create_dir, "newdir")
        # nested dirs need their parent to exist first
        h.create_dir("newdir/sub")
        assert h.examine_object(h.locate_object("newdir/sub")).name == "sub"

    # ----- volume maintenance -----

    def rename_disk_test(self, env):
        h = env.h
        # every file system can relabel its volume
        h.rename_disk("newvol")
        assert h.name == "newvol"

    def more_cache_test(self, env):
        h = env.h
        # a handler that does not cache reports the unchanged buffer count
        assert h.more_cache(10) == 0

    def inhibit_test(self, env):
        h = env.h
        # inhibit/uninhibit is a no-op for these file systems
        h.inhibit(True)
        h.inhibit(False)

    def format_test(self, env):
        h = env.h
        if env.kind == "adfs":
            # only ADFS formats a real volume
            h.format("fresh", 0)
            assert h.name == "fresh"
        else:
            # the other handlers cannot format: not implemented
            expect_error(236, h.format, "fresh", 0)

    def write_protect_test(self, env):
        h = env.h
        h.write_protect(True)
        assert h.write_protected is True
        h.write_protect(False)
        assert h.write_protected is False

    def is_filesystem_test(self, env):
        h = env.h
        # the shared contract only runs against file systems
        assert h.is_filesystem() is True

    # ----- links -----

    def make_read_link_test(self, env):
        h = env.h
        if env.kind not in ("hostfs", "decoder", "dospkt"):
            # only the host file system can express a link
            lock = h.locate_object("")
            expect_error(236, h.make_link, lock, "link", "target", True)
            expect_error(236, h.read_link, lock, "link", 32)
            return
        make_file(h, "target", b"data")
        lock = h.locate_object("")
        h.make_link(lock, "link", "target", True)
        assert h.read_link(lock, "link", 32) == "target"
        # the soft link resolves to the target file
        assert read_all(h, "link") == b"data"
        # the host file system cannot express a hard link
        expect_error(236, h.make_link, lock, "hard", lock, False)
        # a plain file is not a link
        make_file(h, "plain", b"x")
        expect_error(212, h.read_link, lock, "plain", 32)

    # ----- objects / metadata -----

    def change_mode_test(self, env):
        h = env.h
        make_file(h, "f", b"x")
        # a sharing-mode change is accepted (and a no-op) on these file systems
        h.change_mode(h.locate_object("f"), -2)
        fh = h.find_input("f")
        h.change_mode(fh, -1)
        h.end(fh)

    def examine_fh_test(self, env):
        h = env.h
        make_file(h, "f", b"hello")
        fh = h.find_input("f")
        info = h.examine_fh(fh)
        assert info.name == "f"
        assert info.entry_type == HandlerFileInfo.FILE
        assert info.size == 5
        h.end(fh)

    def set_owner_test(self, env):
        h = env.h
        # owner information is not stored by any handler here
        expect_error(236, h.set_owner, h.locate_object(""), "f", 0x1234)

    # ----- record locks -----

    def lock_record_test(self, env):
        h = env.h
        make_file(h, "f", b"0123456789")
        fh = h.find_update("f")
        h.lock_record(fh, 0, 5, 0, 0)  # REC_EXCLUSIVE
        # an overlapping exclusive lock collides
        expect_error(241, h.lock_record, fh, 3, 5, 0, 0)
        # a disjoint lock is fine
        h.lock_record(fh, 5, 5, 0, 0)
        h.free_record(fh, 0, 5)
        h.free_record(fh, 5, 5)
        # releasing a record that is not locked fails
        expect_error(240, h.free_record, fh, 0, 5)
        h.end(fh)

    # ----- notification -----

    def add_remove_notify_test(self, env):
        h = env.h
        # notifications are accepted as a no-op
        h.add_notify(0x1234)
        h.remove_notify(0x1234)

    # ----- interactive ops are unsupported on a file system -----

    def set_mode_unsupported_test(self, env):
        h = env.h
        fh = h.find_output("f", MODE_NEWFILE)
        expect_error(209, h.set_mode, fh, True)
        h.end(fh)

    def wait_for_char_unsupported_test(self, env):
        h = env.h
        fh = h.find_output("f", MODE_NEWFILE)
        expect_error(209, h.wait_for_char, fh, 0)
        h.end(fh)

    # ----- API surface -----

    def action_methods_present_test(self, env):
        # every packet-backed handler method is present on the handler
        for name in ACTION_METHODS:
            assert callable(getattr(env.h, name, None)), name


def base_handler_unsupported_test():
    from amitools.vamos.handler import Handler

    handler = Handler("dummy")
    with pytest.raises(HandlerError) as exc:
        handler.find_input("x")
    assert exc.value.code == 209


def base_handler_new_action_defaults_test():
    from amitools.vamos.handler import Handler

    handler = Handler("dummy", is_filesystem=False)
    # the maintenance/metadata/link/record/notify actions have no default
    # implementation: they report "not implemented" (not "unknown action")
    for func, args in (
        (handler.rename_disk, ("x",)),
        (handler.inhibit, (True,)),
        (handler.format, ("x", 0)),
        (handler.write_protect, (True,)),
        (handler.change_mode, (None, 0)),
        (handler.examine_fh, (None,)),
        (handler.set_owner, (None, "f", 0)),
        (handler.lock_record, (None, 0, 1, 0, 0)),
        (handler.free_record, (None, 0, 1)),
        (handler.add_notify, (0,)),
        (handler.remove_notify, (0,)),
        (handler.make_link, (None, "l", "t", True)),
        (handler.read_link, (None, "l", 32)),
    ):
        with pytest.raises(HandlerError) as exc:
            func(*args)
        assert exc.value.code == 236
    # the two actions with a benign default
    assert handler.more_cache(5) == 0
    assert handler.is_filesystem() is False


def every_action_is_exercised_test():
    """guard: this module calls every packet-backed handler method

    Keeps the contract complete as the API grows: a new ``ACTION_METHODS``
    entry must get a test here.
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


def every_dos_action_is_covered_test():
    """guard: every ``DosAction`` is either mapped or explicitly internal

    The handler API is a 1:1 model of the AmigaDOS packets, so a new action
    must either gain an ``ACTION_METHODS`` entry (and a test above) or be
    listed in ``INTERNAL_ACTIONS`` with the reason it is not exposed.
    """
    from amitools.vamos.handler.base import INTERNAL_ACTIONS
    from amitools.vamos.lib.dos.action import DosAction

    mapped = set(ACTION_METHODS.values())
    missing = [
        action.name
        for action in DosAction
        if action not in mapped and action not in INTERNAL_ACTIONS
    ]
    assert not missing, f"DosActions neither mapped nor internal: {missing}"
