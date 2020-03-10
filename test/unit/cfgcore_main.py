from amitools.vamos.cfgcore import *
from io import StringIO
import logging
import os


def config_main_logging_test(caplog):
    mp = MainParser(debug=True)
    assert caplog.record_tuples == [("config", logging.DEBUG, "logging setup")]


def config_main_ini_test():
    mp = MainParser()
    cfg = """
[hello]
key=value
what=on
number=12

[more]
sys=/home/me
"""
    io = StringIO(cfg)
    res = mp.parse_ini_config(io)
    assert res == {
        "hello": {"key": "value", "what": "on", "number": "12"},
        "more": {"sys": "/home/me"},
    }


def config_main_ini_comment_test():
    mp = MainParser()
    cfg = """
# comment
[hello]
key=value
what=on
number=12

[more]
sys=/home/me
"""
    io = StringIO(cfg)
    res = mp.parse_ini_config(io)
    assert res == {
        "hello": {"key": "value", "what": "on", "number": "12"},
        "more": {"sys": "/home/me"},
    }


def config_main_ini_error_test(caplog):
    mp = MainParser()
    cfg = """
[hello
"""
    io = StringIO(cfg)
    assert mp.parse_ini_config(io) is None
    assert caplog.record_tuples == [
        (
            "config",
            logging.ERROR,
            "???: ini parser failed: File contains no section headers.  file: '<???>', line: 2  '[hello\\n'",
        )
    ]


def config_main_json_test():
    mp = MainParser()
    cfg = """
{ "hello": {
    "key": "value",
    "what": true,
    "number": 12
  },
  "more": {
    "sys": "/home/me"
  }
}
"""
    io = StringIO(cfg)
    res = mp.parse_json_config(io)
    assert res == {
        "hello": {"key": "value", "what": True, "number": 12},
        "more": {"sys": "/home/me"},
    }


def config_main_json_error_test(caplog):
    mp = MainParser()
    cfg = """
{ "hello": {
    "key": "value",
"""
    io = StringIO(cfg)
    assert mp.parse_json_config(io) is None
    assert caplog.record_tuples == [
        (
            "config",
            logging.ERROR,
            "???: json parser failed: Expecting property name enclosed in double quotes: "
            "line 4 column 1 (char 34)",
        )
    ]


def config_main_auto_ini_test():
    mp = MainParser()
    cfg = """
[hello]
key=value
what=on
number=12

[more]
sys=/home/me
"""
    io = StringIO(cfg)
    res = mp.parse_config_auto(io)
    assert res == {
        "hello": {"key": "value", "what": "on", "number": "12"},
        "more": {"sys": "/home/me"},
    }


def config_main_auto_json_test():
    mp = MainParser()
    cfg = """
{ "hello": {
    "key": "value",
    "what": true,
    "number": 12
  },
  "more": {
    "sys": "/home/me"
  }
}
"""
    io = StringIO(cfg)
    res = mp.parse_config_auto(io)
    assert res == {
        "hello": {"key": "value", "what": True, "number": 12},
        "more": {"sys": "/home/me"},
    }


def config_main_add_file_arg_test():
    mp = MainParser()
    mp.add_file_arg()
    assert mp.pre_parse_args([]) == (True, None, False)
    assert mp.pre_parse_args(["-c", "bla"]) == (True, "bla", False)
    assert mp.pre_parse_args(["--config-file", "bla"]) == (True, "bla", False)


def config_main_add_skip_arg_test():
    mp = MainParser()
    mp.add_skip_arg()
    assert mp.pre_parse_args([]) == (True, None, False)
    assert mp.pre_parse_args(["-S"]) == (True, None, True)
    assert mp.pre_parse_args(["--skip-configs"]) == (True, None, True)


def config_main_parse_test(tmpdir):
    tmpdir.join("cfg1").write("[hello]\na=1")
    tmpdir.join("cfg2").write("[hello]\nb=1")
    cfg1 = str(tmpdir.join("cfg1"))
    cfg2 = str(tmpdir.join("cfg2"))
    paths = [cfg1, cfg2]
    mp = MainParser()
    assert mp.parse(paths, args=[])
    mp = MainParser()
    assert mp.parse(paths, args=["-S"])
    mp = MainParser()
    assert mp.parse(paths, args=["-c", cfg2])


def config_main_parse_fail_test(tmpdir):
    tmpdir.join("cfg1").write("[hello\na=1")
    tmpdir.join("cfg2").write("[hello\nb=1")
    cfg1 = str(tmpdir.join("cfg1"))
    cfg2 = str(tmpdir.join("cfg2"))
    paths = [cfg1, cfg2]
    mp = MainParser()
    assert not mp.parse(paths, args=[])
    mp = MainParser()
    assert mp.parse(paths, args=["-S"])
    mp = MainParser()
    assert not mp.parse(paths, args=["-c", cfg2])


def config_main_parse_skip_nonexist_test(tmpdir):
    cfg1 = str(tmpdir.join("cfg1"))
    cfg2 = str(tmpdir.join("cfg2"))
    paths = [cfg1, cfg2]
    mp = MainParser()
    assert mp.parse(paths, args=[])
    mp = MainParser()
    assert mp.parse(paths, args=["-S"])
    mp = MainParser()
    assert not mp.parse(paths, args=["-c", cfg2])


def config_main_parse_custom_args_test(tmpdir):
    mp = MainParser()
    p = mp.get_arg_parser()
    p.add_argument("--fusel", action="store")
    assert mp.parse(args=["--fusel", "bla"])
    args = mp.get_args()
    assert args.fusel == "bla"


def gen_parser(list_sections=None):
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
        "c": Argument("-C"),
    }
    return Parser("parser", def_cfg, arg_cfg, ini_list_sections=list_sections)


def config_main_parser_config_test(tmpdir):
    mp = MainParser()
    p = gen_parser()
    mp.add_parser(p)
    tmpdir.join("cfg1").write("[a]\nv=3")
    cfg1 = str(tmpdir.join("cfg1"))
    paths = [cfg1]
    # run without args
    assert mp.parse(paths, args=[])
    assert p.get_cfg_dict() == {
        "a": {"v": 3, "w": None, "x": True},  # from config
        "b": "hello",
        "c": None,
    }


def config_main_parser_config_fail_test(tmpdir, caplog):
    mp = MainParser()
    p = gen_parser()
    mp.add_parser(p)
    tmpdir.join("cfg1").write("[a]\nv=hallo")
    cfg1 = str(tmpdir.join("cfg1"))
    paths = [cfg1]
    # run without args
    assert not mp.parse(paths, args=[])
    assert caplog.record_tuples == [
        (
            "config",
            logging.ERROR,
            "parser: failed: invalid literal for int() with base 10: 'hallo'",
        )
    ]


def config_main_parser_args_test(tmpdir):
    mp = MainParser()
    p = gen_parser()
    mp.add_parser(p)
    tmpdir.join("cfg1").write("[a]\nv=3")
    cfg1 = str(tmpdir.join("cfg1"))
    paths = [cfg1]
    # run with args
    assert mp.parse(paths, args=["-v"])
    assert p.get_cfg_dict() == {
        "a": {"v": 2, "w": None, "x": True},  # from args
        "b": "hello",
        "c": None,
    }


def config_main_parser_args_fail_test(tmpdir, caplog):
    mp = MainParser()
    p = gen_parser()
    mp.add_parser(p)
    tmpdir.join("cfg1").write("[a]\nv=3")
    cfg1 = str(tmpdir.join("cfg1"))
    paths = [cfg1]
    # run with args
    assert not mp.parse(paths, args=["--blubber"])
    assert caplog.record_tuples == [
        ("config", logging.ERROR, "args: unrecognized arguments: --blubber")
    ]


def config_main_parser_args_fail2_test(tmpdir, caplog):
    mp = MainParser()
    p = gen_parser()
    mp.add_parser(p)
    tmpdir.join("cfg1").write("[a]\nv=3")
    cfg1 = str(tmpdir.join("cfg1"))
    paths = [cfg1]
    # run with args
    assert not mp.parse(paths, args=["-C", "a:hugo"])
    assert caplog.record_tuples == [
        (
            "config",
            logging.ERROR,
            "args: parser failed: invalid literal for int() with base 10: 'hugo'",
        )
    ]


def config_main_parser_dict_test(tmpdir):
    mp = MainParser()
    p = gen_parser()
    mp.add_parser(p)
    # run with dict
    d = {"a": {"v": 2}}
    assert mp.parse(args=[], cfg_dict=d)
    assert p.get_cfg_dict() == {
        "a": {"v": 2, "w": None, "x": True},  # from dict
        "b": "hello",
        "c": None,
    }


def config_main_parser_dict_fail_test(tmpdir, caplog):
    mp = MainParser()
    p = gen_parser()
    mp.add_parser(p)
    # run with dict
    d = {"a": {"v": "blubber"}}
    assert not mp.parse(args=[], cfg_dict=d)
    assert caplog.record_tuples == [
        (
            "config",
            logging.ERROR,
            "parser: failed: invalid literal for int() with base 10: 'blubber'",
        )
    ]
