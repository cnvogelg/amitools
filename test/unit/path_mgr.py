import os
import pytest
from amitools.vamos.path import *
from amitools.vamos.cfgcore import ConfigDict
import logging
from amitools.vamos.log import log_path


log_path.setLevel(logging.DEBUG)


def path_mgr_default_test():
    pm = PathManager()
    assert pm.get_vol_mgr()
    assert pm.get_assign_mgr()
    assert pm.get_default_env()


def path_mgr_config_test(tmpdir):
    vols_base = str(tmpdir.mkdir("volumes"))
    tmpdir.join("volumes").mkdir("work")
    sys_path = str(tmpdir.mkdir("sys"))
    pm = PathManager()
    cfg = ConfigDict(
        {
            "volumes": ["sys:" + sys_path, "work", "home:~"],  # local volume
            "assigns": ["c:sys:c+home:c", "libs:sys:libs", "devs:sys:devs"],
            "path": {
                "command": ["c:", "work:c"],
                "cwd": "work:",
                "vols_base_dir": vols_base,
                "auto_assigns": None,
                "auto_volumes": None,
            },
        }
    )
    assert pm.parse_config(cfg)
    assert pm.setup()
    assert pm.get_all_volume_names() == ["sys", "work", "home", "root", "ram"]
    assert pm.get_all_assign_names() == ["c", "libs", "devs", "s", "t"]
    assert pm.get_cwd() == "work:"
    assert pm.get_cmd_paths() == ["c:", "work:c"]
    pm.shutdown()


def path_mgr_config_auto_empty_test(tmpdir):
    vols_base = str(tmpdir.mkdir("volumes"))
    tmpdir.join("volumes").mkdir("work")
    sys_path = str(tmpdir.mkdir("sys"))
    pm = PathManager()
    cfg = ConfigDict(
        {
            "volumes": ["sys:" + sys_path, "work", "home:~"],  # local volume
            "assigns": ["c:sys:c+home:c", "libs:sys:libs", "devs:sys:devs"],
            "path": {
                "command": ["c:", "work:c"],
                "cwd": "work:",
                "vols_base_dir": vols_base,
                "auto_assigns": [],
                "auto_volumes": [],
            },
        }
    )
    assert pm.parse_config(cfg)
    assert pm.setup()
    assert pm.get_all_volume_names() == ["sys", "work", "home"]
    assert pm.get_all_assign_names() == ["c", "libs", "devs"]
    assert pm.get_cwd() == "work:"
    assert pm.get_cmd_paths() == ["c:", "work:c"]
    pm.shutdown()


def path_mgr_config_esc_sys_test(tmpdir):
    sys_path = str(tmpdir.mkdir("sys"))
    work_path = str(tmpdir.mkdir("work"))
    pm = PathManager()
    cfg = ConfigDict(
        {
            "volumes": ["sys:" + sys_path, "work:" + work_path, "home:~"],
            "assigns": ["c:sys:c+home:c", "libs:sys:libs", "devs:sys:devs"],
            "path": {
                "command": ["::" + work_path],
                "cwd": "::~",
                "vols_base_dir": None,
                "auto_assigns": [],
                "auto_volumes": [],
            },
        }
    )
    assert pm.parse_config(cfg)
    assert pm.setup()
    assert pm.get_all_volume_names() == ["sys", "work", "home"]
    assert pm.get_all_assign_names() == ["c", "libs", "devs"]
    assert pm.get_cwd() == "home:"
    assert pm.get_cmd_paths() == ["work:"]
    pm.shutdown()


def path_mgr_config_empty_test():
    pm = PathManager()
    cfg = ConfigDict(
        {
            "volumes": None,
            "assigns": None,
            "path": {
                "command": ["sys:c"],
                "cwd": "sys:",
                "vols_base_dir": None,
                "auto_volumes": [],
                "auto_assigns": [],
            },
        }
    )
    assert pm.parse_config(cfg)
    assert pm.setup()
    assert pm.get_all_volume_names() == ["system"]
    assert pm.get_all_assign_names() == ["sys"]
    pm.shutdown()


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


def path_mgr_valid_prefix_volume_assign_test(tmpdir):
    pm = setup_pm(tmpdir)
    pv = pm.is_prefix_valid
    vp = pm.is_volume_path
    ap = pm.is_assign_path
    iv = pm.is_valid
    # prefix
    assert pv(AmiPath("a:"))
    assert pv(AmiPath("root:"))
    assert not pv(AmiPath("foo:"))
    with pytest.raises(AmiPathError):
        pv(AmiPath("rel"))
    # volume
    assert not vp(AmiPath("a:"))
    assert vp(AmiPath("root:"))
    assert not vp(AmiPath("foo:"))
    with pytest.raises(AmiPathError):
        vp(AmiPath("rel"))
    # assign
    assert ap(AmiPath("a:"))
    assert not ap(AmiPath("root:"))
    assert not ap(AmiPath("foo:"))
    with pytest.raises(AmiPathError):
        ap(AmiPath("rel"))
    # valid
    assert iv(AmiPath("a:"))
    assert iv(AmiPath("root:"))
    assert not iv(AmiPath("foo:"))
    assert iv(AmiPath("rel"))
    # shutdown
    pm.shutdown()


def path_mgr_multi_assigns_test(tmpdir):
    pm = setup_pm(tmpdir)
    im = pm.is_multi_assign_path
    assert im(AmiPath("A:"))
    assert not im(AmiPath("b:"))
    with pytest.raises(AmiPathError):
        im(AmiPath("rel"))
    assert not im(AmiPath("root:"))
    # recursive
    assert im(AmiPath("D:"))
    # shutdown
    pm.shutdown()


def path_mgr_abspath_test(tmpdir):
    pm = setup_pm(tmpdir)
    ap = pm.abspath
    # abspath of abs
    p = AmiPath("foo:bar")
    assert ap(p) is p
    # abspath of rel
    cur_dir = pm.get_default_env().get_cwd()
    assert ap("") == cur_dir
    assert ap("baz") == cur_dir.join(AmiPath("baz"))
    assert ap("/baz") == cur_dir.join(AmiPath("/baz"))
    # invalid rel
    with pytest.raises(AmiPathError):
        env = AmiPathEnv(cwd="foo:")
        ap("/", env=env)
    # assign
    env = AmiPathEnv(cwd="blub:")
    assert ap(AmiPath("rel"), env=env) == env.get_cwd().join(AmiPath("rel"))
    # other volpath
    env = AmiPathEnv(cwd="work:blub")
    assert ap("baz", env=env) == env.get_cwd().join(AmiPath("baz"))
    # shutdown
    pm.shutdown()


def path_mgr_volpath_test(tmpdir):
    pm = setup_pm(tmpdir)
    env = pm.get_default_env()
    cur_dir = env.get_cwd()
    vp = pm.volpath
    # relpath
    assert vp(AmiPath()) == cur_dir
    assert vp(AmiPath("foo")) == cur_dir.join(AmiPath("foo"))
    # relpath own env
    cwd = AmiPath("work:bar")
    env = AmiPathEnv(cwd=cwd)
    assert vp(AmiPath(), env=env) == cwd
    assert vp(AmiPath("foo"), env=env) == cwd.join(AmiPath("foo"))
    # invalid relpath
    with pytest.raises(AmiPathError):
        env = AmiPathEnv(cwd="foo:")
        assert vp("/", env=env) == cwd
    # volpath
    assert vp(AmiPath("work:bla")) == AmiPath("work:bla")
    # multi assign
    with pytest.raises(AmiPathError):
        vp(AmiPath("a:bla"))
    # assign
    assert vp(AmiPath("b:foo")) == AmiPath("root:bla/foo")
    # unknown prefix
    assert vp(AmiPath("what:is/this")) is None
    # strict: unknown prefix
    with pytest.raises(AmiPathError):
        vp("what:is/this", strict=True)
    # shutdown
    pm.shutdown()


def path_mgr_volpaths_test(tmpdir):
    pm = setup_pm(tmpdir)
    env = pm.get_default_env()
    cur_dir = env.get_cwd()
    vp = pm.volpaths
    # relpath
    assert vp(AmiPath()) == [cur_dir]
    assert vp("foo") == [cur_dir.join(AmiPath("foo"))]
    # relpath own env
    cwd = AmiPath("work:bar")
    env = AmiPathEnv(cwd=cwd)
    assert vp(AmiPath(), env=env) == [cwd]
    assert vp(AmiPath("foo"), env=env) == [cwd.join(AmiPath("foo"))]
    # invalid relpath
    with pytest.raises(AmiPathError):
        env = AmiPathEnv(cwd="foo:")
        assert vp("/", env=env) == cwd
    # volpath
    assert vp(AmiPath("work:bla")) == [AmiPath("work:bla")]
    # multi assign
    assert vp(AmiPath("a:bla")) == [AmiPath("root:bla/bla"), AmiPath("sys:c/foo/bla")]
    # assign
    assert vp(AmiPath("b:foo")) == [AmiPath("root:bla/foo")]
    # unknown prefix
    assert vp("what:is/this") == []
    # strict: unknown prefix
    with pytest.raises(AmiPathError):
        vp("what:is/this", strict=True)
    # shutdown
    pm.shutdown()


def path_mgr_resolve_assigns_test(tmpdir):
    pm = setup_pm(tmpdir)
    env = pm.get_default_env()
    ra = pm.resolve_assigns
    # relpath
    assert ra(AmiPath()) == AmiPath()
    assert ra(AmiPath("foo")) == AmiPath("foo")
    # volpath
    assert ra(AmiPath("work:bla")) == AmiPath("work:bla")
    # multi assign - non recursive
    assert ra(AmiPath("a:bla")) == [AmiPath("b:bla"), AmiPath("c:foo/bla")]
    # multi assign - recursive
    assert ra(AmiPath("a:bla"), True) == [
        AmiPath("root:bla/bla"),
        AmiPath("sys:c/foo/bla"),
    ]
    # assign
    assert ra(AmiPath("b:foo")) == AmiPath("root:bla/foo")
    assert ra(AmiPath("d:baz")) == AmiPath("a:baz")
    # assign recursive
    assert ra(AmiPath("d:baz"), True) == [
        AmiPath("root:bla/baz"),
        AmiPath("sys:c/foo/baz"),
    ]
    # shutdown
    pm.shutdown()


def path_mgr_cmdpaths_test(tmpdir):
    pm = setup_pm(tmpdir)
    env = pm.get_default_env()
    cp = pm.cmdpaths
    cur_dir = env.get_cwd()
    # relpath
    with pytest.raises(AmiPathError):
        cp(AmiPath())
    p = AmiPath("bla/blub")
    assert cp(p) == [cur_dir.join(p)]
    assert cp(p, make_volpaths=False) == [p]
    # invalid command path
    p = AmiPath("bla/blub/")
    with pytest.raises(AmiPathError):
        cp(p)
    # abspath
    with pytest.raises(AmiPathError):
        cp(AmiPath("foo:"))
    with pytest.raises(AmiPathError):
        cp(AmiPath("foo:bla/"))
    p = AmiPath("root:cmd")
    assert cp(p) == [p]
    assert cp(p, make_volpaths=False) == [p]
    # name only
    p = AmiPath("cmd")
    assert cp(p) == [
        AmiPath("root:baz/cmd"),
        AmiPath("root:bla/cmd"),
        AmiPath("sys:c/foo/cmd"),
        AmiPath("sys:c/cmd"),
    ]
    assert cp(p, prepend_cur_dir=False) == [
        AmiPath("root:bla/cmd"),
        AmiPath("sys:c/foo/cmd"),
        AmiPath("sys:c/cmd"),
    ]
    assert cp(p, make_volpaths=False) == [
        AmiPath("root:baz/cmd"),
        AmiPath("a:cmd"),
        AmiPath("c:cmd"),
    ]
    # shutdown
    pm.shutdown()


def get_volume_sys_path(pm, vol_name):
    vol = pm.get_volume(vol_name)
    return vol.get_path()


def path_mgr_to_sys_path_test(tmpdir):
    pm = setup_pm(tmpdir)
    tsp = pm.to_sys_path
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
    with pytest.raises(AmiPathError):
        tsp("/", env=env)
    # unknown prefix
    assert tsp("unknown:") is None
    with pytest.raises(AmiPathError):
        tsp("unknown:", strict=True)
    # shutdown
    pm.shutdown()


def path_mgr_from_sys_path_test(tmpdir):
    pm = setup_pm(tmpdir)
    fsp = pm.from_sys_path
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


def path_mgr_resolve_esc_sys_path_test(tmpdir):
    pm = setup_pm(tmpdir)
    sys_sys_path = get_volume_sys_path(pm, "sys")
    assert pm.get_vol_mgr().add_volume("cwd:.")
    sys_cwd_path = get_volume_sys_path(pm, "cwd")
    resp = pm.resolve_esc_sys_path
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


def path_mgr_create_env_test(tmpdir):
    pm = setup_pm(tmpdir)
    sys_sys_path = get_volume_sys_path(pm, "sys")
    assert pm.get_vol_mgr().add_volume("cwd:.")
    sys_cwd_path = get_volume_sys_path(pm, "cwd")
    def_env = pm.get_default_env()
    # create clone of default env
    env = pm.create_env()
    assert env == def_env
    # set cwd
    env = pm.create_env(cwd="work:")
    assert env.get_cwd() == "work:"
    env.set_cwd("root:")
    assert env.get_cwd() == "root:"
    assert env.get_cmd_paths() == def_env.get_cmd_paths()
    # set cmd_paths
    env = pm.create_env(cmd_paths=["b:"])
    assert env.get_cwd() == "root:baz"
    assert env.get_cmd_paths() == ["b:"]
    # set both
    env = pm.create_env(cwd="work:bla", cmd_paths=["d:"])
    assert env.get_cwd() == "work:bla"
    assert env.get_cmd_paths() == ["d:"]
    # shutdown
    pm.shutdown()


def path_mgr_auto_volume_assign_test(tmpdir):
    pm = PathManager(vols_base_dir=str(tmpdir))
    assert pm.setup()
    vm = pm.get_vol_mgr()
    assert vm.is_volume("system")
    assert vm.is_volume("root")
    assert vm.is_volume("ram")
    am = pm.get_assign_mgr()
    assert am.is_assign("sys")
    assert am.is_assign("c")
    assert am.is_assign("t")
    assert am.is_assign("s")
    assert am.is_assign("devs")
    assert am.is_assign("libs")
    pm.shutdown()
