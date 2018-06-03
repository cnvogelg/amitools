from amitools.vamos.cfgcore import *
from StringIO import StringIO
import logging
import os


def config_main_logging_test(caplog):
  mp = MainParser(debug=True)
  assert caplog.record_tuples == [
      ('config', logging.DEBUG, 'logging setup')
  ]


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
      "hello": {
          "key": "value",
          "what": "on",
          "number": "12"
      },
      "more": {
          "sys": "/home/me"
      }}


def config_main_ini_error_test(caplog):
  mp = MainParser()
  cfg = """
[hello
"""
  io = StringIO(cfg)
  assert mp.parse_ini_config(io) is None
  assert caplog.record_tuples == [
      ('config', logging.ERROR,
       "???: ini parser failed: File contains no section headers.  file: <???>, line: 2  '[hello\\n'")
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
      "hello": {
          "key": "value",
          "what": True,
          "number": 12
      },
      "more": {
          "sys": "/home/me"
      }}


def config_main_json_error_test(caplog):
  mp = MainParser()
  cfg = """
{ "hello": {
    "key": "value",
"""
  io = StringIO(cfg)
  assert mp.parse_json_config(io) is None
  assert caplog.record_tuples == [
      ('config', logging.ERROR,
       "???: json parser failed: Expecting object: line 3 column 20 (char 33)")
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
      "hello": {
          "key": "value",
          "what": "on",
          "number": "12"
      },
      "more": {
          "sys": "/home/me"
      }}


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
      "hello": {
          "key": "value",
          "what": True,
          "number": 12
      },
      "more": {
          "sys": "/home/me"
      }}


def config_main_add_file_arg_test():
  mp = MainParser()
  mp.add_file_arg()
  assert mp.pre_parse_args([]) == (None, False)
  assert mp.pre_parse_args(['-c', 'bla']) == ('bla', False)
  assert mp.pre_parse_args(['--config-file', 'bla']) == ('bla', False)


def config_main_add_skip_arg_test():
  mp = MainParser()
  mp.add_skip_arg()
  assert mp.pre_parse_args([]) == (None, False)
  assert mp.pre_parse_args(['-S']) == (None, True)
  assert mp.pre_parse_args(['--skip-configs']) == (None, True)


def config_main_parse_test(tmpdir):
  tmpdir.join("cfg1").write("[hello]\na=1")
  tmpdir.join("cfg2").write("[hello]\nb=1")
  cfg1 = str(tmpdir.join("cfg1"))
  cfg2 = str(tmpdir.join("cfg2"))
  paths = [cfg1, cfg2]
  mp = MainParser()
  assert mp.parse(paths, args=[]) == (cfg1, True)
  mp = MainParser()
  assert mp.parse(paths, args=['-S']) == (None, True)
  mp = MainParser()
  assert mp.parse(paths, args=['-c', cfg2]) == (cfg2, True)


def config_main_parse_fail_test(tmpdir):
  tmpdir.join("cfg1").write("[hello\na=1")
  tmpdir.join("cfg2").write("[hello\nb=1")
  cfg1 = str(tmpdir.join("cfg1"))
  cfg2 = str(tmpdir.join("cfg2"))
  paths = [cfg1, cfg2]
  mp = MainParser()
  assert mp.parse(paths, args=[]) == (cfg1, False)
  mp = MainParser()
  assert mp.parse(paths, args=['-S']) == (None, True)
  mp = MainParser()
  assert mp.parse(paths, args=['-c', cfg2]) == (cfg2, False)


def gen_parser():
  def_cfg = {"a": {"v": 1,
                   "w": ValueList(str),
                   "x": True},
             "b": "hello",
             "c": ValueDict(int)}
  arg_cfg = {"a": {"v": Argument("-v", action='store_const', const=2),
                   "w": Argument("-w"),
                   "x": Argument("-x", action='store_false')},
             "b": Argument("-b"),
             "c": Argument("-C")}
  return Parser(def_cfg, arg_cfg)


def config_main_parser_config_test(tmpdir):
  mp = MainParser()
  p = gen_parser()
  mp.add_parser(p)
  tmpdir.join("cfg1").write("[a]\nv=3")
  cfg1 = str(tmpdir.join("cfg1"))
  paths = [cfg1]
  # run without args
  assert mp.parse(paths, args=[]) == (cfg1, True)
  assert p.get_cfg_dict() == {
      "a": {"v": 3, # from config
            "w": None,
            "x": True},
      "b": "hello",
      "c": None
  }


def config_main_parser_args_test(tmpdir):
  mp = MainParser()
  p = gen_parser()
  mp.add_parser(p)
  tmpdir.join("cfg1").write("[a]\nv=3")
  cfg1 = str(tmpdir.join("cfg1"))
  paths = [cfg1]
  # run with args
  assert mp.parse(paths, args=['-v']) == (cfg1, True)
  assert p.get_cfg_dict() == {
      "a": {"v": 2, # from args
            "w": None,
            "x": True},
      "b": "hello",
      "c": None
  }
