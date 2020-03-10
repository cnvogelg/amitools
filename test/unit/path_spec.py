import pytest
from amitools.vamos.path import Spec


def path_spec_parse_name_only_test():
    # invalid is empty spec
    with pytest.raises(ValueError):
        Spec.parse("")
    # name only
    s = Spec.parse("foo")
    assert s.get_name() == "foo"
    assert s.get_src_list() == []
    assert not s.get_append()
    # name only 2
    s = Spec.parse("foo:")
    assert s.get_name() == "foo"
    assert s.get_src_list() == []
    assert not s.get_append()


def path_spec_parse_src_test():
    # name + src
    s = Spec.parse("foo:bar")
    assert s.get_name() == "foo"
    assert s.get_src_list() == ["bar"]
    assert not s.get_append()
    # name + src
    s = Spec.parse("foo:bar+baz")
    assert s.get_name() == "foo"
    assert s.get_src_list() == ["bar", "baz"]
    assert not s.get_append()
    # name + only is invalid
    with pytest.raises(ValueError):
        Spec.parse("foo:+")
    # name + append list
    s = Spec.parse("foo:+bar+baz")
    assert s.get_name() == "foo"
    assert s.get_src_list() == ["bar", "baz"]
    assert s.get_append()


def path_spec_parse_cfg_test():
    # invalid only cfg
    with pytest.raises(ValueError):
        Spec.parse("?key=val")
    # no cfg
    with pytest.raises(ValueError):
        Spec.parse("foo?")
    # ok
    s = Spec.parse("foo?key=val")
    assert s.get_name() == "foo"
    assert s.get_cfg() == {"key": "val"}
    assert s.get_src_list() == []
    assert not s.get_append()
    # ok
    s = Spec.parse("foo?key=val,key2=True,key3=False")
    assert s.get_name() == "foo"
    assert s.get_cfg() == {"key": "val", "key2": True, "key3": False}
    assert s.get_src_list() == []
    assert not s.get_append()
    # ok: 'key' is short for key=True
    s = Spec.parse("foo?key")
    assert s.get_name() == "foo"
    assert s.get_cfg() == {"key": True}
    assert s.get_src_list() == []
    assert not s.get_append()
