import pytest
from amitools.vamos.cfgcore.value import *


def config_value_parse_str_test():
  assert parse_scalar(str, "hello") == "hello"
  with pytest.raises(ValueError):
    parse_scalar(str, None)
  assert parse_scalar(str, None, True) is None


def config_value_parse_int_test():
  assert parse_scalar(int, 12) == 12
  assert parse_scalar(int, "12") == 12
  with pytest.raises(ValueError):
    parse_scalar(int, None)
  assert parse_scalar(int, None, True) is None


def config_value_parse_bool_test():
  assert parse_scalar(bool, True)
  assert parse_scalar(bool, "On")
  assert parse_scalar(bool, "TRUE")
  assert not parse_scalar(bool, "Off")
  assert not parse_scalar(bool, "FALSE")
  with pytest.raises(ValueError):
    parse_scalar(bool, None)
  assert parse_scalar(bool, None, True) is None


def config_value_split_nest_test():
  assert split_nest("") == []
  assert split_nest("bla") == ["bla"]
  assert split_nest("foo,bar") == ["foo", "bar"]
  assert split_nest("foo,(bar,baz)") == ["foo", "bar,baz"]
  assert split_nest("foo,(bar,(baz,foo))") == ["foo", "bar,(baz,foo)"]
  assert split_nest("foo,{bar,(baz,foo)}", nest_pair='{}') == [
      "foo", "bar,(baz,foo)"]


def config_value_list_test():
  l = ValueList(str)
  assert l.parse("bla") == ["bla"]
  assert l.parse("a,b") == ["a", "b"]
  assert l.parse(["a", "b"]) == ["a", "b"]
  assert l.parse(["a,b", "c"]) == ["a", "b", "c"]
  # old value and append
  assert l.parse(["a,b", "c"], ["x", "y"]) == ["a", "b", "c"]
  assert l.parse("+a,b", ["x", "y"]) == ["x", "y", "a", "b"]


def config_value_list_int_test():
  l = ValueList(int)
  assert l.parse("12") == [12]
  assert l.parse("1,2") == [1, 2]
  assert l.parse(["1", "2"]) == [1, 2]
  assert l.parse([1, 2]) == [1, 2]
  assert l.parse(["1,2", "3"]) == [1, 2, 3]
  assert l.parse(["1,2", 3]) == [1, 2, 3]


def config_value_list_nest_value_test():
  l = ValueList(Value(str))
  assert l.parse("bla") == ["bla"]
  assert l.parse("a,b") == ["a", "b"]
  assert l.parse(["a", "b"]) == ["a", "b"]


def config_value_list_nest_list_test():
  l = ValueList(ValueList(str, sep='+'))
  assert l.parse("bla") == [["bla"]]
  assert l.parse("a,b") == [["a"], ["b"]]
  assert l.parse("a+b") == [["a", "b"]]
  assert l.parse(["a", "b"]) == [["a"], ["b"]]
  assert l.parse([["a"], ["b"]]) == [["a"], ["b"]]
  l = ValueList(ValueList(str))
  assert l.parse("(a,b)") == [["a", "b"]]


def config_value_list_nest_dict_rest():
  l = ValueList(ValueDict(str, sep='+'))
  assert l.parse("a:b") == [{'a': 'b'}]
  assert l.parse("a:b,c:d") == [{'a': 'b'}, {'c': 'd'}]
  assert l.parse("a:b+c:d,e:f") == [{'a': 'b', 'c': 'd'}, {'e': 'f'}]
  l = ValueList(ValueDict(str))
  assert l.parse("{a:b,c:d},e:f") == [{'a': 'b', 'c': 'd'}, {'e': 'f'}]


def config_value_dict_test():
  d = ValueDict(str)
  assert d.parse("a:b") == {'a': 'b'}
  assert d.parse("a:b,c:d") == {'a': 'b', 'c': 'd'}
  assert d.parse({'a': 'b', 'c': 'd'}) == {'a': 'b', 'c': 'd'}
  # allow list of partial dicts
  assert d.parse(['a:b', 'c:d']) == {'a': 'b', 'c': 'd'}
  assert d.parse(['a:b', {'c': 'd'}]) == {'a': 'b', 'c': 'd'}
  # last one wins in list
  assert d.parse(['a:b', 'a:d']) == {'a': 'd'}
  # old value and append
  assert d.parse("a:b", {"x": "y"}) == {'a': 'b'}
  assert d.parse("+a:b", {"x": "y"}) == {'a': 'b', 'x': 'y'}


def config_value_dict_int_test():
  d = ValueDict(int)
  assert d.parse("a:1") == {'a': 1}
  assert d.parse("a:1,c:2") == {'a': 1, 'c': 2}
  assert d.parse({'a': 1, 'c': 2}) == {'a': 1, 'c': 2}
  # allow list of partial dicts
  assert d.parse(['a:1', 'c:2']) == {'a': 1, 'c': 2}
  assert d.parse(['a:1', {'c': '2'}]) == {'a': 1, 'c': 2}
  # last one wins in list
  assert d.parse(['a:1', 'a:2']) == {'a': 2}


def config_value_dict_nest_value_test():
  d = ValueDict(Value(str))
  assert d.parse("a:b") == {'a': 'b'}
  assert d.parse("a:b,c:d") == {'a': 'b', 'c': 'd'}
  assert d.parse({'a': 'b', 'c': 'd'}) == {'a': 'b', 'c': 'd'}


def config_value_dict_nest_list_test():
  d = ValueDict(ValueList(str, sep='+'))
  assert d.parse("a:b") == {'a': ['b']}
  assert d.parse("a:b+c") == {'a': ['b', 'c']}
  assert d.parse({'a': ['b', 'c']}) == {'a': ['b', 'c']}
  d = ValueDict(ValueList(str))
  assert d.parse("a:(b,c)") == {'a': ['b', 'c']}
  # allow to omit ()) if sub string has no key:value pair
  assert d.parse("a:b,c") == {'a': ['b', 'c']}
  assert d.parse("a:b,c,z:x") == {'a': ['b', 'c'], 'z': ['x']}
  with pytest.raises(ValueError):
    d.parse("a,b")
  # append to list
  assert d.parse("a:(b,c)", {'a': ['x']}) == {'a': ['b', 'c']}
  assert d.parse("a:(+b,c)", {'a': ['x'], 'z': []}) == {'a': ['x', 'b', 'c']}
  assert d.parse("+a:(b,c)", {'a': ['x'], 'z': []}
                 ) == {'a': ['b', 'c'], 'z': []}


def config_value_dict_nest_dict_test():
  d = ValueDict(ValueDict(str))
  assert d.parse("a:{b:c}") == {'a': {'b': 'c'}}
  # append
  assert d.parse("a:{b:c}", {'a': {'z': 'oi'}, 'b': {'x': 'hu'}}) == {
      'a': {'b': 'c'}}
  assert d.parse("+a:{b:c}", {'a': {'z': 'oi'}, 'b': {'x': 'hu'}}) == {
      'a': {'b': 'c'}, 'b': {'x': 'hu'}}
  assert d.parse("a:{+b:c}", {'a': {'z': 'oi'}, 'b': {'x': 'hu'}}) == {
      'a': {'b': 'c', 'z': 'oi'}}
