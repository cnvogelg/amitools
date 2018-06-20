from amitools.vamos.path import AmiPathEnv, AmiPath
from amitools.vamos.cfgcore import ConfigDict


def path_env_default_test():
  pe = AmiPathEnv()
  assert pe.get_cwd() == "sys:"
  assert pe.get_cmd_paths() == ["c:"]


def path_env_parse_config_test():
  pe = AmiPathEnv()
  cfg = ConfigDict({
      "path": ConfigDict({
          "command": ["c:", "sc:c"],
          "cwd": "foo:bar"
      })
  })
  assert pe.parse_config(cfg)
  assert pe.get_cwd() == "foo:bar"
  assert pe.get_cmd_paths() == ["c:", "sc:c"]


def path_env_get_set_cwd_test():
  pe = AmiPathEnv()
  assert pe.get_cwd() == "sys:"
  assert pe.set_cwd("foo:")
  assert pe.get_cwd() == "foo:"
  # invalid path
  assert not pe.set_cwd(":bla")
  assert not pe.set_cwd("bla/baz")


def path_env_get_set_cmd_paths_test():
  pe = AmiPathEnv()
  assert pe.get_cmd_paths() == ["c:"]
  assert pe.set_cmd_paths(["a:", "b:", "c:"])
  assert pe.get_cmd_paths() == ["a:", "b:", "c:"]
  # invalid path
  assert not pe.set_cmd_paths(["a:", "b", ":c"])


def path_env_add_del_cmd_path_test():
  pe = AmiPathEnv()
  assert pe.get_cmd_paths() == ["c:"]
  # add
  assert pe.add_cmd_path("d:")
  assert pe.get_cmd_paths() == ["c:", "d:"]
  assert pe.add_cmd_path("b:", True)
  assert pe.get_cmd_paths() == ["b:", "c:", "d:"]
  # del
  assert pe.del_cmd_path("c:")
  assert pe.get_cmd_paths() == ["b:", "d:"]
  assert not pe.del_cmd_path("z:")
