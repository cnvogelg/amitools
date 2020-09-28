from amitools.vamos.cfgcore import *
import argparse


def config_parser_default_empty_test():
    p = Parser("a")
    assert p.get_def_cfg().get_cfg() == {}
    assert p.get_arg_cfg().get_cfg() == {}
    assert p.get_cfg_dict() == {}


def config_parser_default_test():
    def_cfg = {
        "a": {"v": 1, "w": ValueList(str), "x": True},
        "b": "hello",
        "c": ValueDict(int),
    }
    p = Parser("a", def_cfg)
    # check internal default
    def_cfg = p.get_def_cfg().get_cfg()
    assert def_cfg == {
        "a": {"v": Value(int, 1), "w": ValueList(str), "x": Value(bool, True)},
        "b": Value(str, "hello"),
        "c": ValueDict(int),
    }
    # get default config
    assert p.get_cfg_dict() == {
        "a": {"v": 1, "w": None, "x": True},
        "b": "hello",
        "c": None,
    }


def config_parser_config_test():
    def_cfg = {
        "a": {"v": 1, "w": ValueList(str), "x": True},
        "b": "hello",
        "c": ValueDict(int),
    }
    p = Parser("a", def_cfg)
    # update with some config
    m = {"a": {"v": 3, "w": "a,b", "x": False}, "b": "no", "c": {"a": 1, "b": 2}}
    p.parse_config(m, "dict")
    assert p.get_cfg_dict() == {
        "a": {"v": 3, "w": ["a", "b"], "x": False},
        "b": "no",
        "c": {"a": 1, "b": 2},
    }


def config_parser_arg_test():
    def_cfg = {
        "a": {"v": 1, "w": ValueList(str), "x": True},
        "b": "hello",
        "c": ValueDict(int),
    }
    arg_cfg = {
        "a": {
            "v": Argument("-v", action="store_const", const=2),
            "w": Argument("-w"),
            "x": Argument("-x", action="store_false"),
        },
        "b": Argument("-b"),
        "c": Argument("-c"),
    }
    p = Parser("a", def_cfg, arg_cfg)
    # update with some args
    ap = argparse.ArgumentParser()
    p.setup_args(ap)
    args = ap.parse_args(["-v", "-w", "hi", "-x", "-b", "cool", "-c", "a:10,b:20"])
    p.parse_args(args)
    assert p.get_cfg_dict() == {
        "a": {"v": 2, "w": ["hi"], "x": False},
        "b": "cool",
        "c": {"a": 10, "b": 20},
    }


def config_parser_ini_trafo_test():
    def_cfg = {
        "a": {"v": 1, "w": ValueList(str), "x": True},
        "b": "hello",
        "c": ValueDict(int),
    }
    trafo_cfg = {"a": {"v": "V", "w": "W", "x": "X"}}
    p = Parser("a", def_cfg, ini_trafo=trafo_cfg)
    # update with some args
    m = {"V": 23, "W": ["hello", "world"], "X": False}
    p.parse_config(m, "ini")
    assert p.get_cfg_dict() == {
        "a": {"v": 23, "w": ["hello", "world"], "x": False},
        "b": "hello",
        "c": None,
    }
