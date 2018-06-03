import pytest
from amitools.vamos.cfgcore.value import *


def config_value_parse_str_test():
  assert parse_scalar(str, "hello") == "hello"
  with pytest.raises(ValueError):
    parse_scalar(str, None)
  assert parse_scalar(str, None, True) is None


def config_valuse_parse_int_test():
  assert parse_scalar(int, 12) == 12
  assert parse_scalar(int, "12") == 12
  with pytest.raises(ValueError):
    parse_scalar(int, None)
  assert parse_scalar(int, None, True) is None


def config_valuse_parse_bool_test():
  assert parse_scalar(bool, True)
  assert parse_scalar(bool, "On")
  assert parse_scalar(bool, "TRUE")
  assert not parse_scalar(bool, "Off")
  assert not parse_scalar(bool, "FALSE")
  with pytest.raises(ValueError):
    parse_scalar(bool, None)
  assert parse_scalar(bool, None, True) is None
