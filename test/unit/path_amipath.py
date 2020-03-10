import pytest
from amitools.vamos.path import AmiPath, AmiPathError


def path_amipath_eq_ne_test():
    assert AmiPath() == AmiPath()
    assert AmiPath("foo:bar") == AmiPath("foo:bar")
    # case insensitive
    assert AmiPath("Foo:BAR") == AmiPath("foo:bar")
    # ne
    assert AmiPath() != AmiPath("bla")
    assert AmiPath("Foo:BAR") != AmiPath("foo:baz")


def path_amipath_abs_rel_test():
    # cur dir "" is default and assumed to be local
    p = AmiPath()
    assert p.is_local()
    assert not p.is_absolute()
    assert not p.is_parent_local()
    assert not p.is_prefix_local()
    assert not p.is_name_only()
    assert not p.ends_with_name()
    # abs
    p = AmiPath("foo:bar")
    assert not p.is_local()
    assert p.is_absolute()
    assert not p.is_parent_local()
    assert not p.is_prefix_local()
    assert not p.is_name_only()
    assert p.ends_with_name()
    # abs2
    p = AmiPath("foo:")
    assert not p.is_local()
    assert p.is_absolute()
    assert not p.is_parent_local()
    assert not p.is_prefix_local()
    assert not p.is_name_only()
    assert not p.ends_with_name()
    # local
    p = AmiPath("foo/bar")
    assert p.is_local()
    assert not p.is_absolute()
    assert not p.is_parent_local()
    assert not p.is_prefix_local()
    assert not p.is_name_only()
    assert p.ends_with_name()
    # local name
    p = AmiPath("foo")
    assert p.is_local()
    assert not p.is_absolute()
    assert not p.is_parent_local()
    assert not p.is_prefix_local()
    assert p.is_name_only()
    assert p.ends_with_name()
    # special local
    p = AmiPath(":bla")
    assert p.is_local()
    assert not p.is_absolute()
    assert not p.is_parent_local()
    assert p.is_prefix_local()
    assert not p.is_name_only()
    assert p.ends_with_name()
    # parent local
    p = AmiPath("/bla")
    assert p.is_local()
    assert not p.is_absolute()
    assert p.is_parent_local()
    assert not p.is_prefix_local()
    assert not p.is_name_only()
    assert p.ends_with_name()
    # parent local
    p = AmiPath("/bla/")
    assert p.is_local()
    assert not p.is_absolute()
    assert p.is_parent_local()
    assert not p.is_prefix_local()
    assert not p.is_name_only()
    assert not p.ends_with_name()


def path_amipath_prefix_postfix_test():
    p = AmiPath()
    assert p.prefix() is None
    assert p.postfix() == ""
    assert p.postfix(True) == ""
    assert AmiPath.build(p.prefix(), p.postfix()) == p
    p = AmiPath("foo:bar/")
    assert p.prefix() == "foo"
    assert p.postfix() == "bar"
    assert p.postfix(True) == "bar"
    assert p.postfix(skip_trailing=False) == "bar/"
    assert AmiPath.build(p.prefix(), p.postfix(skip_trailing=False)) == p
    p = AmiPath("foo/bar/")
    assert p.prefix() is None
    assert p.postfix() == "foo/bar"
    assert p.postfix(True) == "foo/bar"
    assert p.postfix(skip_trailing=False)
    assert AmiPath.build(p.prefix(), p.postfix(skip_trailing=False)) == p
    p = AmiPath(":bla")
    assert p.prefix() is None
    assert p.postfix() == ":bla"
    assert p.postfix(True) == "bla"
    assert AmiPath.build(p.prefix(), p.postfix()) == p
    p = AmiPath("/bla")
    assert p.prefix() is None
    assert p.postfix() == "/bla"
    assert p.postfix(True) == "bla"
    assert AmiPath.build(p.prefix(), p.postfix()) == p
    p = AmiPath("/")
    assert p.prefix() is None
    assert p.postfix() == "/"
    assert p.postfix(True) == ""
    assert AmiPath.build(p.prefix(), p.postfix()) == p


def path_amipath_valid_syntax_test():
    assert AmiPath().is_syntax_valid()
    assert AmiPath("foo:bar/").is_syntax_valid()
    assert AmiPath("foo/bar/").is_syntax_valid()
    assert AmiPath(":bla").is_syntax_valid()
    assert AmiPath("/bla").is_syntax_valid()
    # invalid
    assert not AmiPath("//").is_syntax_valid()
    assert not AmiPath(":/").is_syntax_valid()
    assert not AmiPath("bla/foo:").is_syntax_valid()
    assert not AmiPath("bla:foo:").is_syntax_valid()


def path_amipath_parent_test():
    assert AmiPath("foo/bar").parent() == AmiPath("foo")
    assert AmiPath("foo:bar/baz").parent() == AmiPath("foo:bar")
    assert AmiPath("foo:bar").parent() == AmiPath("foo:")
    assert AmiPath("foo:").parent() is None
    assert AmiPath("/bar").parent() == AmiPath("/")
    assert AmiPath("/bar/").parent() == AmiPath("/")
    assert AmiPath("/").parent() is None
    assert AmiPath(":").parent() is None
    assert AmiPath(":bar").parent() == AmiPath(":")
    assert AmiPath("bar").parent() == AmiPath()


def path_amipath_names_test():
    assert AmiPath("foo/bar").names() == ["foo", "bar"]
    assert AmiPath("foo:bar/baz").names() == ["bar", "baz"]
    assert AmiPath("foo:bar").names() == ["bar"]
    assert AmiPath("foo:").names() == []
    assert AmiPath("/bar").names() == ["bar"]
    assert AmiPath("/bar/").names() == ["bar"]
    assert AmiPath("/").names() == []
    assert AmiPath(":").names() == []
    assert AmiPath(":bar").names() == ["bar"]
    assert AmiPath("bar").names() == ["bar"]
    # with special name
    assert AmiPath("foo/bar").names(True) == ["foo", "bar"]
    assert AmiPath("foo:bar/baz").names(True) == ["bar", "baz"]
    assert AmiPath("foo:bar").names(True) == ["bar"]
    assert AmiPath("foo:").names(True) == []
    assert AmiPath("/bar").names(True) == ["/", "bar"]
    assert AmiPath("/bar/").names(True) == ["/", "bar"]
    assert AmiPath("/").names(True) == ["/"]
    assert AmiPath(":").names(True) == [":"]
    assert AmiPath(":bar").names(True) == [":", "bar"]
    assert AmiPath("bar").names(True) == ["bar"]


def path_amipath_filename_test():
    assert AmiPath("foo/bar").filename() == "bar"
    assert AmiPath("foo:bar/baz").filename() == "baz"
    assert AmiPath("foo:bar").filename() == "bar"
    assert AmiPath("foo:").filename() is None
    assert AmiPath("/bar").filename() == "bar"
    assert AmiPath("/bar/").filename() == "bar"
    assert AmiPath("/").filename() is None
    assert AmiPath(":").filename() is None
    assert AmiPath(":bar").filename() == "bar"
    assert AmiPath("bar").filename() == "bar"


def path_amipath_dirname_test():
    assert AmiPath("foo/bar").dirname() == "foo"
    assert AmiPath("foo:bar/baz").dirname() == "bar"
    assert AmiPath("foo:bar/baz").dirname() == "bar"
    assert AmiPath("foo:bar").dirname() is None
    assert AmiPath("foo:").dirname() is None
    assert AmiPath("/bar").dirname() == "/"
    assert AmiPath("/bar/").dirname() == "/"
    assert AmiPath("/").dirname() == "/"
    assert AmiPath(":").dirname() == ":"
    assert AmiPath(":bar").dirname() == ":"
    assert AmiPath("bar").dirname() is None


def path_amipath_absdirname_test():
    assert AmiPath("foo/bar").absdirname() == "foo"
    assert AmiPath("foo:bar/baz").absdirname() == "foo:bar"
    assert AmiPath("foo:bar").absdirname() == "foo:"
    assert AmiPath("foo:").absdirname() == "foo:"
    assert AmiPath("/bar").absdirname() == "/"
    assert AmiPath("/bar/").absdirname() == "/"
    assert AmiPath("/").absdirname() == "/"
    assert AmiPath(":").absdirname() == ":"
    assert AmiPath(":bar").absdirname() == ":"
    assert AmiPath("bar").absdirname() is None


def path_amipath_join_abs_test():
    # abs join abs
    assert AmiPath("foo:bar").join(AmiPath("baz:boo")) == AmiPath("baz:boo")
    # abs join parent local
    assert AmiPath("foo:bar").join(AmiPath("/baz")) == AmiPath("foo:baz")
    assert AmiPath("foo:bar/boo").join(AmiPath("/baz")) == AmiPath("foo:bar/baz")
    assert AmiPath("foo:bar/boo").join(AmiPath("/")) == AmiPath("foo:bar")
    with pytest.raises(AmiPathError):
        print((AmiPath("foo:").join(AmiPath("/baz"))))
    # abs join prefix local
    assert AmiPath("foo:bar").join(AmiPath(":baz")) == AmiPath("foo:baz")
    assert AmiPath("foo:bar/boo").join(AmiPath(":baz")) == AmiPath("foo:baz")
    assert AmiPath("foo:bar").join(AmiPath(":")) == AmiPath("foo:")
    # abs join local
    assert AmiPath("foo:").join(AmiPath()) == AmiPath("foo:")
    assert AmiPath("foo:").join(AmiPath("bar")) == AmiPath("foo:bar")
    assert AmiPath("foo:baz").join(AmiPath()) == AmiPath("foo:baz")
    assert AmiPath("foo:baz").join(AmiPath("bar")) == AmiPath("foo:baz/bar")


def path_amipath_join_local_test():
    # local join abs
    assert AmiPath("bar").join(AmiPath("baz:boo")) == AmiPath("baz:boo")
    # local join parent local
    assert AmiPath("bar").join(AmiPath("/baz")) == AmiPath("baz")
    assert AmiPath("bar/boo").join(AmiPath("/baz")) == AmiPath("bar/baz")
    assert AmiPath("bar/boo").join(AmiPath("/")) == AmiPath("bar")
    with pytest.raises(AmiPathError):
        print((AmiPath().join(AmiPath("/baz"))))
    # local join prefix local
    assert AmiPath("bar").join(AmiPath(":baz")) == AmiPath(":baz")
    assert AmiPath("bar/boo").join(AmiPath(":baz")) == AmiPath(":baz")
    assert AmiPath("bar").join(AmiPath(":")) == AmiPath(":")
    # local join local
    assert AmiPath().join(AmiPath()) == AmiPath()
    assert AmiPath().join(AmiPath("bar")) == AmiPath("bar")
    assert AmiPath("baz").join(AmiPath("bar")) == AmiPath("baz/bar")
    assert AmiPath("foo/baz").join(AmiPath("bar")) == AmiPath("foo/baz/bar")


def path_amipath_join_parent_local_test():
    # parent local join abs
    assert AmiPath("/bar").join(AmiPath("baz:boo")) == AmiPath("baz:boo")
    # parent local join parent local
    with pytest.raises(AmiPathError):
        AmiPath("/bar").join(AmiPath("/baz"))
    # parent local join prefix local
    assert AmiPath("/bar").join(AmiPath(":baz")) == AmiPath(":baz")
    assert AmiPath("/bar/boo").join(AmiPath(":baz")) == AmiPath(":baz")
    assert AmiPath("/bar").join(AmiPath(":")) == AmiPath(":")
    # parent local join local
    assert AmiPath("/").join(AmiPath()) == AmiPath("/")
    assert AmiPath("/").join(AmiPath("bar")) == AmiPath("/bar")
    assert AmiPath("/baz").join(AmiPath("bar")) == AmiPath("/baz/bar")
    assert AmiPath("/foo/baz").join(AmiPath("bar")) == AmiPath("/foo/baz/bar")


def path_amipath_join_prefix_local_test():
    # prefix local join abs
    assert AmiPath(":bar").join(AmiPath("baz:boo")) == AmiPath("baz:boo")
    # prefix local join parent local
    with pytest.raises(AmiPathError):
        AmiPath(":").join(AmiPath("/baz"))
    assert AmiPath(":bar").join(AmiPath("/baz")) == AmiPath(":baz")
    assert AmiPath(":foo/bar").join(AmiPath("/baz")) == AmiPath(":foo/baz")
    # prefix local join prefix local
    assert AmiPath(":bar").join(AmiPath(":baz")) == AmiPath(":baz")
    assert AmiPath(":bar/boo").join(AmiPath(":baz")) == AmiPath(":baz")
    assert AmiPath(":bar").join(AmiPath(":")) == AmiPath(":")
    # prefix local join local
    assert AmiPath(":").join(AmiPath()) == AmiPath(":")
    assert AmiPath(":").join(AmiPath("bar")) == AmiPath(":bar")
    assert AmiPath(":baz").join(AmiPath("bar")) == AmiPath(":baz/bar")
    assert AmiPath(":foo/baz").join(AmiPath("bar")) == AmiPath(":foo/baz/bar")
