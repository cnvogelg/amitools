from amitools.vamos.config import *
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
  assert mp.parse(paths, args=[]) == cfg1
  mp = MainParser()
  assert mp.parse(paths, args=['-S']) is None
  mp = MainParser()
  assert mp.parse(paths, args=['-c', cfg2]) == cfg2
