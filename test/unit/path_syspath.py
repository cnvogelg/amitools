import os
import pytest
from amitools.vamos.path import (
    PathManager,
    SysPathResolver,
    SysPathError,
    AmiPath,
    AmiPathError,
    AmiPathEnv,
)


def setup_pm(tmpdir):
    root_path = str(tmpdir)
    sys_path = str(tmpdir.mkdir("sys"))
    work_path = str(tmpdir.mkdir("work"))
    pm = PathManager(vols_base_dir=str(tmpdir), auto_volumes=[], auto_assigns=[])
    env = pm.get_default_env()
    env.set_cwd("root:baz")
    env.set_cmd_paths(["a:", "c:"])
    vm = pm.get_vol_mgr()
    am = pm.get_assign_mgr()
    vm.add_volume("root:" + root_path)
    vm.add_volume("sys:" + sys_path)
    vm.add_volume("work:" + work_path)
    am.add_assign("a:b:+c:foo")
    am.add_assign("b:root:bla")
    am.add_assign("c:sys:c")
    am.add_assign("d:a:")
    assert pm.setup()
    return pm


def get_volume_sys_path(pm, vol_name):
    vol = pm.get_volume(vol_name)
    return vol.get_path()


def path_syspath_to_sys_path_test(tmpdir):
    pm = setup_pm(tmpdir)
    tsp = SysPathResolver(pm).to_sys_path
    sys_sys_path = get_volume_sys_path(pm, "sys")
    sys_root_path = get_volume_sys_path(pm, "root")
    # vol path
    assert tsp("sys:") == sys_sys_path
    # assign path
    assert tsp("c:") == os.path.join(sys_sys_path, "c")
    # relpath
    assert tsp("") == os.path.join(sys_root_path, "baz")
    assert tsp("what/next") == os.path.join(sys_root_path, "baz", "what", "next")
    # relpath env
    env = AmiPathEnv(cwd="sys:")
    assert tsp("", env=env) == os.path.join(sys_sys_path)
    assert tsp("foo/bar", env=env) == os.path.join(sys_sys_path, "foo", "bar")
    # invalid relpath
    assert tsp("/", env=env) == os.path.join(sys_sys_path)
    # unknown prefix
    assert tsp("unknown:") is None
    with pytest.raises(AmiPathError):
        tsp("unknown:", strict=True)
    # shutdown
    pm.shutdown()


def path_syspath_from_sys_path_test(tmpdir):
    pm = setup_pm(tmpdir)
    fsp = SysPathResolver(pm).from_sys_path
    sys_sys_path = get_volume_sys_path(pm, "sys")
    sys_root_path = get_volume_sys_path(pm, "root")
    assert pm.get_vol_mgr().add_volume("cwd:.")
    sys_cwd_path = get_volume_sys_path(pm, "cwd")
    # abs sys path
    assert fsp(sys_sys_path) == "sys:"
    assert fsp(sys_root_path) == "root:"
    assert fsp(sys_cwd_path) == "cwd:"
    assert fsp(os.path.join(sys_sys_path, "my", "Path")) == "sys:my/Path"
    # rel sys path
    assert fsp(".") == "cwd:"
    assert fsp("my/Path") == "cwd:my/Path"
    # can't map
    assert fsp("..") is None
    with pytest.raises(SysPathError):
        fsp("..", strict=True)
    # shutdown
    pm.shutdown()


def path_syspath_resolve_esc_sys_path_test(tmpdir):
    pm = setup_pm(tmpdir)
    sys_sys_path = get_volume_sys_path(pm, "sys")
    assert pm.get_vol_mgr().add_volume("cwd:.")
    resp = SysPathResolver(pm).resolve_esc_sys_path
    # ami path
    assert resp("bla:") == AmiPath("bla:")
    assert resp("rel") == AmiPath("rel")
    assert resp("") == AmiPath()
    # esc sys path
    # invalid empty
    with pytest.raises(AmiPathError):
        resp("::")
    # valid abs
    assert resp("::" + sys_sys_path) == "sys:"
    # valid rel
    assert resp("::.") == "cwd:"
    # invalid sys
    assert resp("::..") is None
    with pytest.raises(SysPathError):
        resp("::..", strict=True)
    # shutdown
    pm.shutdown()
