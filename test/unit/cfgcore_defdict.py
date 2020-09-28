from amitools.vamos.cfgcore import *


def config_defdict_empty_test():
    dd = DefaultDict()
    assert dd.get_cfg() == {}
    assert dd.gen_dict() == {}


def config_defdict_setup_test():
    cfg = {
        "a": {"v": 1, "w": ValueList(str), "x": True},
        "b": "hello",
        "c": ValueDict(int),
    }
    dd = DefaultDict(cfg)
    # check internal default
    def_cfg = dd.get_cfg()
    assert def_cfg == {
        "a": {"v": Value(int, 1), "w": ValueList(str), "x": Value(bool, True)},
        "b": Value(str, "hello"),
        "c": ValueDict(int),
    }
    # get initial config from parser
    cfg = dd.gen_dict()
    assert cfg == {"a": {"v": 1, "w": None, "x": True}, "b": "hello", "c": None}


def config_defdict_merge_test():
    cfg = {
        "a": {"v": 1, "w": ValueList(str), "x": True},
        "b": "hello",
        "c": ValueDict(int),
    }
    dd = DefaultDict(cfg)
    # generate default dict
    d = dd.gen_dict()
    m = {
        "a": {"v": 2, "w": ["hello", "world"], "x": False, "z": "ignore me"},
        "c": {"a": 10, "b": 20},
        "d": "ignore me",
    }
    dd.merge_cfg(d, m)
    assert d == {
        "a": {"v": 2, "w": ["hello", "world"], "x": False},
        "b": "hello",
        "c": {"a": 10, "b": 20},
    }


def config_defdict_merge_key_test():
    cfg = {
        "a": {"v": 1, "w": ValueList(str), "x": True},
        "b": "hello",
        "c": ValueDict(int),
    }
    dd = DefaultDict(cfg)
    # generate default dict
    d = dd.gen_dict()
    m = {"X": {"v": 2, "w": ["hello", "world"], "x": False, "z": "ignore me"}}
    dd.merge_cfg_key(d, m, "X", def_key="a")
    assert d == {
        "a": {"v": 1, "w": None, "x": True},
        "b": "hello",
        "c": None,
        "X": {"v": 2, "w": ["hello", "world"], "x": False},
    }
