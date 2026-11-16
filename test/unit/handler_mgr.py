import os

import pytest

from amitools.vamos.handler import (
    MODE_NEWFILE,
    ConsoleHandler,
    Handler,
    HandlerError,
    HandlerManager,
    HandlerRegistry,
    HostFileSysHandler,
    NilHandler,
    build_handler_manager,
    default_registry,
)
from amitools.vamos.path import PathManager


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


def handler_mgr_resolve_device_test(tmp_path):
    pm, mgr, root, work = setup_mgr(tmp_path)
    # a device name is a handler but neither a volume nor an assign, so the
    # path manager does not resolve it and the manager falls back to a direct
    # lookup by prefix
    dev = HostFileSysHandler("nil", str(root))
    mgr.register("nil", dev)
    assert mgr.resolve("nil:") == [(dev, "")]
    assert mgr.resolve("nil:sub/file") == [(dev, "sub/file")]
    # the device name lookup is case-insensitive too
    assert mgr.resolve("NIL:foo") == [(dev, "foo")]
    # an unregistered prefix still yields no candidates
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


def handler_mgr_find_output_multi_assign_test(tmp_path):
    pm, mgr, root, work = setup_mgr(tmp_path)
    pm.get_assign_mgr().add_assign("m:work:+root:")
    # an existing object in a later candidate is preferred for output
    (root / "f").write_bytes(b"root")
    handler, fh = mgr.find_output("m:f", MODE_NEWFILE)
    assert handler.name == "root"
    handler.end(fh)
    # a new object is created in the first candidate
    handler, fh = mgr.find_output("m:new", MODE_NEWFILE)
    assert handler.name == "work"
    handler.end(fh)
    assert (work / "new").exists()
    assert not (root / "new").exists()


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


def handler_registry_default_test():
    reg = default_registry()
    assert "hostfs" in reg.get_all_types()
    # type names are case-insensitive
    assert reg.get("HOSTFS") is not None
    # unknown types are not registered
    assert reg.get("nope") is None
    assert reg.create("nope", "x", "/tmp", {}, None) is None


def handler_mgr_bind_volume_test(tmp_path):
    pm, mgr, root, work = setup_mgr(tmp_path)
    # a fresh manager binds the volumes via their config; default is hostfs
    mgr2 = HandlerManager(pm)
    for volume in pm.get_vol_mgr().get_all_volumes():
        mgr2.bind_volume(volume)
    # the explicitly added volumes are bound (auto volumes are present too)
    assert {"root", "work"} <= set(mgr2.get_all_names())
    handler = mgr2.get_handler("work")
    assert isinstance(handler, HostFileSysHandler)
    assert handler.name == "work"
    assert handler.root_path == str(work)


def handler_mgr_bind_volume_type_test(tmp_path):
    pm, mgr, root, work = setup_mgr(tmp_path)

    class DummyHandler(Handler):
        def __init__(self, name):
            super().__init__(name, is_filesystem=False)

    def dummy_factory(name, path, cfg, file_system):
        assert cfg.get("extra") == "42"
        return DummyHandler(name)

    reg = HandlerRegistry()
    reg.add_type("dummy", dummy_factory)
    mgr2 = HandlerManager(pm, registry=reg)
    volume = pm.get_vol_mgr().get_volume("work")
    volume.cfg["handler"] = "dummy"
    volume.cfg["extra"] = "42"
    handler = mgr2.bind_volume(volume)
    assert isinstance(handler, DummyHandler)
    assert mgr2.get_handler("work") is handler
    assert not mgr2.is_filesystem("work")


def handler_mgr_bind_volume_unknown_type_test(tmp_path):
    pm, mgr, root, work = setup_mgr(tmp_path)
    mgr2 = HandlerManager(pm)
    volume = pm.get_vol_mgr().get_volume("work")
    volume.cfg["handler"] = "nope"
    # ERROR_ACTION_NOT_KNOWN
    expect_error(209, mgr2.bind_volume, volume)
    assert mgr2.get_handler("work") is None


def handler_build_manager_test(tmp_path):
    pm, mgr, root, work = setup_mgr(tmp_path)
    built = build_handler_manager(pm)
    # every configured volume is bound and shares the volume manager's fs
    assert isinstance(built.get_handler("work"), HostFileSysHandler)
    assert built.get_handler("work").root_path == str(work)
    assert built.file_system is pm.get_vol_mgr().file_system
    built.shutdown()
    assert built.get_all_names() == []


def handler_build_manager_devices_test(tmp_path):
    pm, mgr, root, work = setup_mgr(tmp_path)
    built = build_handler_manager(pm)
    # NIL: and CONSOLE: are built-in devices, not file systems
    assert isinstance(built.get_handler("nil"), NilHandler)
    assert isinstance(built.get_handler("console"), ConsoleHandler)
    assert built.is_filesystem("nil") is False
    assert built.is_filesystem("console") is False
    assert built.is_filesystem("work") is True
    built.shutdown()


def handler_mgr_device_open_test(tmp_path):
    pm, mgr, root, work = setup_mgr(tmp_path)
    built = build_handler_manager(pm)
    # NIL: reads EOF and discards writes
    handler, fh = built.find_input("NIL:")
    assert isinstance(handler, NilHandler)
    assert fh.is_nil is True
    handler, fh = built.find_output("NIL:", MODE_NEWFILE)
    assert isinstance(handler, NilHandler)
    assert fh.is_nil is True
    # CONSOLE: resolves to the console device
    handler, fh = built.find_output("CONSOLE:", MODE_NEWFILE)
    assert isinstance(handler, ConsoleHandler)
    assert fh.need_close is False
    built.shutdown()


def handler_mgr_nil_volume_test(tmp_path):
    # a non-host volume needs no host directory and still resolves
    pm = PathManager(vols_base_dir=str(tmp_path), auto_volumes=[], auto_assigns=[])
    assert pm.get_vol_mgr().add_volume("nil:?handler=nil")
    assert pm.setup()
    built = build_handler_manager(pm)
    assert isinstance(built.get_handler("nil"), NilHandler)
    handler, fh = built.find_input("NIL:foo")
    assert isinstance(handler, NilHandler)
    assert fh.is_nil is True
    built.shutdown()
    pm.shutdown()


def handler_mgr_shutdown_test(tmp_path):
    pm, mgr, root, work = setup_mgr(tmp_path)
    calls = []

    class ClosingHandler(Handler):
        def shutdown(self):
            calls.append(self.name)

    mgr.register("closing", ClosingHandler("closing"))
    mgr.shutdown()
    # a handler exposing shutdown() is released and all handlers are dropped
    assert calls == ["closing"]
    assert mgr.get_all_names() == []
