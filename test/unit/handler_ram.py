"""In-memory RAM handler (``ram``) tests.

The shared handler contract lives in :mod:`handler_contract` and runs here
against :class:`RamHandler` via ``TestRamContract``. Only behavior specific to
the in-memory file system is asserted in this module.
"""

from types import SimpleNamespace

import pytest
from handler_contract import HandlerContract, expect_error

from amitools.vamos.handler import (
    MODE_NEWFILE,
    MODE_READWRITE,
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


@pytest.fixture
def env():
    handler = RamHandler("work")
    return SimpleNamespace(
        kind="ram",
        h=handler,
        new_handler=lambda name: RamHandler(name),
    )


class TestRamContract(HandlerContract):
    pass


def handler_ram_size_config_test():
    h = make_handler(cfg={"size": "8"})
    # size is given in KiB and reported in 512 byte blocks
    assert h.num_blocks == 16
    info = h.info(h.locate_object(""))
    assert info.num_blocks == 16
    assert info.bytes_per_block == 512


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


def handler_ram_rename_onto_existing_test():
    h = make_handler()
    write_file(h, "a", b"x")
    write_file(h, "b", b"y")
    # ram rejects renaming onto an existing object instead of overwriting
    expect_error(202, h.rename_object, "a", "b")


def handler_ram_protect_comment_date_test():
    h = make_handler()
    write_file(h, "f", b"x")
    h.set_protect("f", 0x123)
    h.set_comment("f", "hello")
    h.set_date("f", 1000000)
    info = h.examine_object(h.locate_object("f"))
    # ram stores the exact protection mask and the comment
    assert info.protection == 0x123
    assert info.comment == "hello"
    assert info.date == 1000000
    # missing objects fail
    expect_error(205, h.set_protect, "gone", 0)
    expect_error(205, h.set_comment, "gone", "x")
    expect_error(205, h.set_date, "gone", 0)


def handler_ram_create_dir_missing_parent_test():
    h = make_handler()
    # the parent must exist
    expect_error(205, h.create_dir, "missing/sub")


def handler_ram_rename_disk_test():
    h = make_handler()
    h.rename_disk("newvol")
    assert h.name == "newvol"
    # the root node is renamed too, so examining it reports the new name
    assert h.examine_object(h.locate_object("")).name == "newvol"


def handler_ram_link_not_implemented_test():
    h = make_handler()
    lock = h.locate_object("")
    expect_error(236, h.make_link, lock, "link", "target", True)
    expect_error(236, h.read_link, lock, "link", 32)


def handler_ram_set_file_size_grow_test():
    h = make_handler()
    write_file(h, "f", b"0123")
    # grow the file again with zeros
    fh = h.find_output("f", MODE_READWRITE)
    assert h.set_file_size(fh, 6, -1) == 6
    h.end(fh)
    assert read_file(h, "f") == b"0123\x00\x00"
