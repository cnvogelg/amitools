import pytest
from amitools.vamos.path import *
from amitools.vamos.cfgcore import ConfigDict


def path_env_default_test():
    pe = AmiPathEnv()
    assert pe.get_cwd() == "sys:"
    assert pe.get_cmd_paths() == ["c:"]
    assert repr(pe) == "AmiPathEnv(cwd=sys:, cmd_paths=[c:])"
    assert str(pe) == "[cwd=sys:, cmd_paths=[c:]]"


def path_env_eq_ne_test():
    pe = AmiPathEnv()
    assert pe.get_cwd() == "sys:"
    assert pe.get_cmd_paths() == ["c:"]
    pe2 = AmiPathEnv(cwd="sys:", cmd_paths=["c:"])
    assert pe == pe2
    pe3 = AmiPathEnv(cwd="bla:")
    assert pe != pe3
    pe4 = AmiPathEnv(cmd_paths=["b:"])
    assert pe != pe4


def path_env_parse_config_test():
    pe = AmiPathEnv()
    cfg = ConfigDict(
        {"path": ConfigDict({"command": ["c:", "sc:c"], "cwd": "foo:bar"})}
    )
    assert pe.parse_config(cfg)
    assert pe.get_cwd() == "foo:bar"
    assert pe.get_cmd_paths() == ["c:", "sc:c"]


def path_env_get_set_cwd_test():
    pe = AmiPathEnv()
    assert not pe.is_cwd_resolved()
    assert pe.get_cwd() == "sys:"
    assert pe.is_cwd_resolved()
    # set valid path
    pe.set_cwd("foo:")
    assert pe.get_cwd() == "foo:"
    # set invalid path
    pe.set_cwd(":bla")
    with pytest.raises(AmiPathError):
        pe.get_cwd()
    # another invalid
    pe.set_cwd("bla/baz")
    with pytest.raises(AmiPathError):
        pe.get_cwd()


def path_env_get_set_cmd_paths_test():
    pe = AmiPathEnv()
    assert not pe.are_cmd_paths_resolved()
    assert pe.get_cmd_paths() == ["c:"]
    assert pe.are_cmd_paths_resolved()
    pe.set_cmd_paths(["a:", "b:", "c:"])
    assert pe.get_cmd_paths() == ["a:", "b:", "c:"]
    # invalid path
    pe.set_cmd_paths(["a:", "b", ":c"])
    with pytest.raises(AmiPathError):
        pe.get_cmd_paths()


def path_env_add_del_cmd_path_test():
    pe = AmiPathEnv()
    assert pe.get_cmd_paths() == ["c:"]
    # append
    pe.append_cmd_path("d:")
    assert pe.get_cmd_paths() == ["c:", "d:"]
    pe.prepend_cmd_path("b:")
    assert pe.get_cmd_paths() == ["b:", "c:", "d:"]
    # del
    pe.remove_cmd_path("c:")
    assert pe.get_cmd_paths() == ["b:", "d:"]
    with pytest.raises(ValueError):
        pe.remove_cmd_path("z:")
