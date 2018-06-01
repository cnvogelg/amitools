from amitools.vamos.config import *


def config_parser_default_empty_test():
  p = Parser()
  assert p.get_default_cfg() == {}
  assert p.get_cfg_dict() == {}


def config_parser_default_test():
  setup_cfg = {"a": {"v": 1,
                     "w": ValueList(str),
                     "x": True},
               "b": "hello",
               "c": ValueDict(int)}
  p = Parser(setup_cfg)
  # check internal default
  def_cfg = p.get_default_cfg()
  assert def_cfg == {
      "a": {"v": Value(int, 1),
            "w": ValueList(str),
            "x": Value(bool, True)},
      "b": Value(str, "hello"),
      "c": ValueDict(int)
  }
  # get initial config from parser
  cfg = p.get_cfg_dict()
  assert cfg == {
      "a": {"v": 1, "w": None, "x": True},
      "b": "hello",
      "c": None
  }
