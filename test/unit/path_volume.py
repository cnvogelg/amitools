import os
from amitools.vamos.path import VolumeManager
from amitools.vamos.cfgcore import ConfigDict


def path_volume_add_del_test(tmpdir):
  v = VolumeManager()
  assert v.get_all_names() == []
  my_path = str(tmpdir.mkdir("bla"))
  no_path = str(tmpdir.join("hugo"))
  # ok
  assert v.add_volume("My", my_path)
  assert v.get_all_names() == ['My']
  assert v.is_volume('MY')
  # duplicate path mapping
  assert not v.add_volume("foo", my_path)
  # duplicate path name
  assert not v.add_volume("my", no_path)
  # invalid path
  assert not v.add_volume("foo", no_path)
  # ok
  assert v.del_volume("my")
  # invalid name
  assert not v.del_volume("baz")


def path_volume_sys_to_ami_test(tmpdir):
  v = VolumeManager()
  mp = tmpdir.mkdir("bla")
  my_path = str(mp)
  no_path = str(tmpdir.join("hugo"))
  mp2 = mp.mkdir("blub")
  my_path2 = str(mp2)
  assert v.add_volume("My", my_path)
  assert v.add_volume("nested", my_path2)
  # exisitng path
  s2a = v.sys_to_ami_path
  assert s2a(my_path) == 'My:'
  assert s2a(str(mp.join("foo"))) == 'My:foo'
  # expect nested path
  assert s2a(my_path2) == 'nested:'
  assert s2a(str(mp2.join("bla/blub"))) == "nested:bla/blub"
  # non existing
  assert s2a(str(tmpdir)) is None


def path_volume_ami_to_sys_test(tmpdir):
  v = VolumeManager()
  mp = tmpdir.mkdir("bla")
  my_path = str(mp)
  mp2 = mp.mkdir("Foo").mkdir("BAR").mkdir("baZ")
  # case insensitive file system?
  ci_fs = os.path.exists(os.path.join(my_path, "foo"))
  sub_path = str(mp2)
  assert v.add_volume("My", my_path)
  # base path
  a2s = v.ami_to_sys_path
  assert a2s("my:") == my_path + "/"
  assert a2s("my:unkown/PATH") == os.path.join(my_path, "unkown", "PATH")
  assert a2s("my:foo/bar/baz") == sub_path
  # fast mode
  if ci_fs:
    assert a2s("my:foo", True) == os.path.join(my_path, "foo")
  else:
    assert a2s("my:foo", True) == os.path.join(my_path, "Foo")


def path_volume_cfg_test(tmpdir):
  my_path = str(tmpdir.mkdir("bla"))
  v = VolumeManager()
  cfg = ConfigDict({
      'volumes': ConfigDict({
          'my': my_path
      })
  })
  assert v.parse_config(cfg)
  assert v.get_all_names() == ['my']
  assert v.is_volume('MY')
