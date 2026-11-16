"""Host file system handler (``hostfs``) tests.

The shared handler contract lives in :mod:`handler_contract` and runs here
against :class:`HostFileSysHandler` via ``TestHostFsContract``. Only behavior
specific to the host file system is asserted in this module.
"""

import os
from types import SimpleNamespace

import pytest
from handler_contract import HandlerContract, expect_error

from amitools.vamos.handler import HostFileSysHandler


def make_handler(tmp_path, name="work"):
    root = tmp_path / "root"
    root.mkdir()
    return HostFileSysHandler(name, str(root)), root


@pytest.fixture
def env(tmp_path):
    # the volume root is a host dir named like the volume, so the root's
    # examine name matches the volume name
    root = tmp_path / "work"
    root.mkdir()
    handler = HostFileSysHandler("work", str(root))
    return SimpleNamespace(
        kind="hostfs",
        h=handler,
        root=root,
        new_handler=lambda name: HostFileSysHandler(name, str(root)),
    )


class TestHostFsContract(HandlerContract):
    pass


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


def handler_filesys_comment_ignored_test(tmp_path):
    h, root = make_handler(tmp_path)
    (root / "f").write_bytes(b"x")
    # a host file system cannot store Amiga comments: the call is accepted but
    # nothing is kept
    h.set_comment("f", "hello")
    assert h.examine_object(h.locate_object("f")).comment == ""
    # a missing object is silently ignored on the host
    h.set_comment("gone", "hello")


def handler_filesys_rename_overwrite_test(tmp_path):
    h, root = make_handler(tmp_path)
    (root / "a").write_bytes(b"A")
    (root / "b").write_bytes(b"B")
    # on the host a rename replaces the existing target
    h.rename_object("a", "b")
    assert (root / "b").read_bytes() == b"A"
    assert not (root / "a").exists()


def handler_filesys_create_dir_missing_parent_test(tmp_path):
    h, _ = make_handler(tmp_path)
    # the host reports a missing parent as "object not found"
    expect_error(203, h.create_dir, "missing/sub")
