import os
from amitools.vamos.path import VolumeManager, resolve_sys_path
from amitools.vamos.cfgcore import ConfigDict


def path_volume_resolve_sys_path_test(tmpdir):
    rsp = resolve_sys_path
    p = str(tmpdir)
    assert rsp(p) == p
    # user home
    assert rsp("~") == os.path.expanduser("~")
    # env var
    os.environ["TEST_PATH"] = p
    assert rsp("${TEST_PATH}") == p
    assert rsp("${TEST_PATH}/bla") == os.path.join(p, "bla")


def path_volume_add_del_test(tmpdir):
    v = VolumeManager()
    assert v.setup()
    assert v.get_all_names() == []
    my_path = str(tmpdir.mkdir("bla"))
    no_path = str(tmpdir.join("hugo"))
    # ok
    vol = v.add_volume("My:" + my_path)
    assert vol
    assert v.get_all_names() == ["My"]
    assert v.is_volume("MY")
    assert vol.is_setup
    assert vol.get_path() == my_path
    assert v.add_volume("foo:" + my_path)
    assert v.get_all_names() == ["My", "foo"]
    # duplicate path mapping
    assert not v.add_volume("foo:" + my_path)
    # duplicate path name
    assert not v.add_volume("my:" + no_path)
    # invalid path
    assert not v.add_volume("foo:" + no_path)
    # ok
    assert v.del_volume("my")
    assert not vol.is_setup
    assert v.get_all_names() == ["foo"]
    # invalid name
    assert not v.del_volume("baz")
    # shutdown
    v.shutdown()


def path_volume_add_local_test(tmpdir):
    vols_dir = str(tmpdir.join("volumes"))
    v = VolumeManager(vols_base_dir=vols_dir)
    v.setup()
    # without create
    assert not v.add_volume("My")
    # with create
    vol = v.add_volume("My?create")
    assert vol
    # check for vol dir
    vol_path = os.path.join(vols_dir, "My")
    assert os.path.isdir(vol_path)
    assert vol.get_path() == vol_path
    # create multiple
    vols = v.add_volumes(["foo?create", "bar?create"])
    assert vols
    for vol in vols:
        vol_path = os.path.join(vols_dir, vol.get_name())
        assert os.path.isdir(vol_path)
        assert vol.get_path() == vol_path
    # shutdown
    v.shutdown()


def path_volume_create_rel_sys_path_test(tmpdir):
    v = VolumeManager()
    org = tmpdir.mkdir("bla")
    my_path = str(org)
    # ok
    vol = v.add_volume("My:" + my_path)
    assert vol
    # single path
    path = vol.create_rel_sys_path("bla")
    assert path == str(org.join("bla"))
    assert os.path.isdir(path)
    # multi path
    path = vol.create_rel_sys_path(["foo", "bar"])
    assert path == str(org.join("foo").join("bar"))
    assert os.path.isdir(path)


def path_volume_sys_to_ami_test(tmpdir):
    v = VolumeManager()
    mp = tmpdir.mkdir("bla")
    my_path = str(mp)
    no_path = str(tmpdir.join("hugo"))
    mp2 = mp.mkdir("blub")
    my_path2 = str(mp2)
    assert v.add_volume("My:" + my_path)
    assert v.add_volume("nested:" + my_path2)
    # exisitng path
    s2a = v.sys_to_ami_path
    assert s2a(my_path) == "My:"
    assert s2a(str(mp.join("foo"))) == "My:foo"
    # expect nested path
    assert s2a(my_path2) == "nested:"
    assert s2a(str(mp2.join("bla/blub"))) == "nested:bla/blub"
    # non existing
    assert s2a(str(tmpdir)) is None
    # not abosulte
    assert s2a("bla") is None


def path_volume_ami_to_sys_test(tmpdir):
    v = VolumeManager()
    mp = tmpdir.mkdir("bla")
    my_path = str(mp)
    mp2 = mp.mkdir("Foo").mkdir("BAR").mkdir("baZ")
    # case insensitive file system?
    ci_fs = os.path.exists(os.path.join(my_path, "foo"))
    sub_path = str(mp2)
    assert v.add_volume("My:" + my_path)
    # base path
    a2s = v.ami_to_sys_path
    assert a2s("my:") == my_path
    assert a2s("my:unkown/PATH") == os.path.join(my_path, "unkown", "PATH")
    # follow along case of path in sys fs
    assert a2s("my:foo/bar/baz") == sub_path
    # fast mode on case insensitive fs does not adjust ami path
    if ci_fs:
        assert a2s("my:foo", True) == os.path.join(my_path, "foo")
    else:
        assert a2s("my:foo", True) == os.path.join(my_path, "Foo")


def path_volume_cfg_test(tmpdir):
    my_path = str(tmpdir.mkdir("bla"))
    v = VolumeManager()
    cfg = ConfigDict({"volumes": ["my:" + my_path]})
    assert v.parse_config(cfg)
    assert v.get_all_names() == ["my"]
    assert v.is_volume("MY")


def path_volume_create_test(tmpdir):
    v = VolumeManager(str(tmpdir))
    assert v.setup()
    spec = "my:" + str(tmpdir) + "/bla"
    # dir does not exist -> can't create
    assert not v.add_volume(spec)
    # create
    assert v.add_volume(spec + "?create")
    # check
    assert tmpdir.join("bla").check(dir=1)
    # shutdown
    v.shutdown()


def path_volume_temp_test(tmpdir):
    v = VolumeManager(str(tmpdir))
    assert v.setup()
    spec = "my:" + str(tmpdir)
    # dir does exist -> no temp possible
    assert not v.add_volume(spec + "?temp")
    # create temp
    spec += "/bla"
    assert v.add_volume(spec + "?temp")
    # check that temp dir exists
    assert tmpdir.join("bla").check(dir=1)
    # shutdown
    v.shutdown()
    # now temp is gone
    assert not tmpdir.join("bla").check()
