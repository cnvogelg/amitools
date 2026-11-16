import os

import pytest

from amitools.vamos.path import PathManager
from amitools.vamos.handler import (
    HandlerError,
    HandlerManager,
    HostFileSysHandler,
)


def setup_mgr(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    pm = PathManager(vols_base_dir=str(tmp_path), auto_volumes=[], auto_assigns=[])
    vm = pm.get_vol_mgr()
    am = pm.get_assign_mgr()
    vm.add_volume("root:" + str(root))
    vm.add_volume("work:" + str(work))
    am.add_assign("w:work:")
    pm.get_default_env().set_cwd("work:")
    assert pm.setup()
    mgr = HandlerManager(pm)
    root_h = HostFileSysHandler("root", str(root))
    work_h = HostFileSysHandler("work", str(work))
    mgr.register("root", root_h)
    mgr.register("work", work_h)
    return pm, mgr, root, work


def expect_error(code, func, *args, **kwargs):
    with pytest.raises(HandlerError) as exc:
        func(*args, **kwargs)
    assert exc.value.code == code
    return exc.value


def handler_mgr_resolve_test(tmp_path):
    pm, mgr, root, work = setup_mgr(tmp_path)
    # volume path
    res = mgr.resolve("work:sub/file")
    assert len(res) == 1
    handler, rel = res[0]
    assert handler.name == "work"
    assert rel == "sub/file"
    # assign path
    res = mgr.resolve("w:sub")
    assert res[0][0].name == "work"
    assert res[0][1] == "sub"
    # relative path via default cwd
    res = mgr.resolve("sub")
    assert res[0][0].name == "work"
    assert res[0][1] == "sub"
    # volume root
    res = mgr.resolve("work:")
    assert res[0][1] == ""
    # unknown volume
    assert mgr.resolve("nope:file") == []


def handler_mgr_dispatch_test(tmp_path):
    pm, mgr, root, work = setup_mgr(tmp_path)
    (work / "sub").mkdir()
    (work / "sub" / "f").write_bytes(b"data")
    handler, lock = mgr.locate_object("work:sub/f")
    assert handler.name == "work"
    assert lock.key == "sub/f"
    handler, fh = mgr.find_input("work:sub/f")
    assert handler.read(fh, 10) == b"data"
    handler.end(fh)
    expect_error(205, mgr.find_input, "work:missing")


def handler_mgr_find_output_test(tmp_path):
    pm, mgr, root, work = setup_mgr(tmp_path)
    handler, fh = mgr.find_output("work:new.txt")
    handler.write(fh, b"hi")
    handler.end(fh)
    assert (work / "new.txt").read_bytes() == b"hi"
    # an unknown volume cannot be created
    expect_error(205, mgr.find_output, "nope:new.txt")


def handler_mgr_create_delete_test(tmp_path):
    pm, mgr, root, work = setup_mgr(tmp_path)
    mgr.create_dir("work:newdir")
    assert (work / "newdir").is_dir()
    expect_error(203, mgr.create_dir, "work:newdir")
    mgr.delete_object("work:newdir")
    assert not (work / "newdir").exists()


def handler_mgr_rename_test(tmp_path):
    pm, mgr, root, work = setup_mgr(tmp_path)
    (work / "a").write_bytes(b"x")
    mgr.rename_object("work:a", "work:b")
    assert (work / "b").exists()
    # rename across handlers is rejected
    (root / "r").write_bytes(b"x")
    expect_error(215, mgr.rename_object, "work:b", "root:r")


def handler_mgr_protect_date_test(tmp_path):
    pm, mgr, root, work = setup_mgr(tmp_path)
    (work / "f").write_bytes(b"x")
    mgr.set_protect("work:f", 0)
    assert os.access(work / "f", os.R_OK)
    mgr.set_date("work:f", 1000000)
    assert os.path.getmtime(work / "f") == 1000000
    mgr.set_comment("work:f", "ignored")


def handler_mgr_registry_test(tmp_path):
    pm, mgr, root, work = setup_mgr(tmp_path)
    assert mgr.get_handler("WORK") is mgr.get_handler("work")
    assert set(mgr.get_all_names()) == {"root", "work"}
    assert mgr.is_filesystem("work")
    # unknown names default to a file system
    assert mgr.is_filesystem("unknown")
    assert mgr.unregister("work") is not None
    assert mgr.get_handler("work") is None
