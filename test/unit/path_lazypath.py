import pytest
from amitools.vamos.path import *


def lp_with_resolver(path):
    def path_resolver(path):
        if path == "foo:":
            return AmiPath("bar:")
        elif path == "bar:":
            raise AmiPathError(path, "not wanted!")
        else:
            return path

    return LazyPath(path=path, path_resolver=path_resolver)


def path_lazypath_default_test():
    lp = LazyPath("")
    assert lp.get() == ""
    assert str(lp) == "(!)"
    assert not lp.is_resolved()
    assert lp.get_resolved() == ""
    assert lp.is_resolved()
    assert str(lp) == ""
    lp = LazyPath(AmiPath("foo:"))
    assert lp.get() == AmiPath("foo:")
    assert lp.get_resolved() == AmiPath("foo:")
    assert str(lp) == "foo:"
    assert repr(lp) == "LazyPath(path=foo:, resolved_path=foo:)"


def path_lazypath_eq_test():
    lp = LazyPath("bla:")
    assert lp == lp
    lp2 = LazyPath("")
    assert lp != lp2
    lp3 = LazyPath("")
    assert lp3 == lp2
    lp3.resolve()
    assert lp3 != lp2


def path_lazypath_resolver_test():
    lp = lp_with_resolver("")
    assert lp.get() == ""
    assert lp.get_resolved() == ""
    lp = lp_with_resolver(AmiPath("foo:"))
    assert lp.get() == AmiPath("foo:")
    # resolver transforms
    assert lp.get_resolved() == AmiPath("bar:")
    lp = lp_with_resolver(AmiPath("bar:"))
    assert lp.get() == AmiPath("bar:")
    # resolver raises AmiPathError
    with pytest.raises(AmiPathError):
        lp.get_resolved()


def path_lazypath_set_test():
    lp = LazyPath("")
    assert lp.get() == ""
    assert lp.get_resolved() == ""
    lp.set("foo:")
    assert not lp.is_resolved()
    assert lp.get() == "foo:"
    assert lp.get_resolved() == "foo:"


def path_lazypath_set_resolver_test():
    lp = lp_with_resolver("")
    assert lp.get() == ""
    assert lp.get_resolved() == ""
    lp.set("foo:")
    assert not lp.is_resolved()
    assert lp.get() == "foo:"
    assert lp.get_resolved() == "bar:"


def path_lazypath_list_test():
    lpl = LazyPathList()
    assert lpl.get() == []
    assert lpl.get_resolved() == []
    lpl = LazyPathList(["foo:"])
    assert lpl.get() == ["foo:(!)"]
    assert not lpl.is_resolved()
    assert lpl.get_resolved() == ["foo:"]
    assert lpl.is_resolved()


def path_lazypath_list_eq_test():
    lpl = LazyPathList()
    assert lpl == lpl
    lpl2 = LazyPathList()
    assert lpl == lpl2
    lpl3 = LazyPathList(["foo:"])
    assert lpl != lpl3


def path_lazypath_list_set_test():
    lpl = LazyPathList()
    assert lpl.get() == []
    assert lpl.get_resolved() == []
    lpl.set(["foo:"])
    assert lpl.get() == ["foo:(!)"]
    assert not lpl.is_resolved()
    assert lpl.get_resolved() == ["foo:"]
    assert lpl.is_resolved()
    # append
    lpl.append("bar:")
    assert lpl.get() == ["foo:", "bar:(!)"]
    assert not lpl.is_resolved()
    assert lpl.get_resolved() == ["foo:", "bar:"]
    assert lpl.is_resolved()
    # prepend
    lpl.prepend("baz:")
    assert lpl.get() == ["baz:(!)", "foo:", "bar:"]
    assert not lpl.is_resolved()
    assert lpl.get_resolved() == ["baz:", "foo:", "bar:"]
    assert lpl.is_resolved()


def path_lazypath_list_resolver_test():
    lp = lp_with_resolver("bla:")
    resolver = lp.get_path_resolver()
    lpl = LazyPathList(path_resolver=resolver)
    assert lpl.get() == []
    assert lpl.get_resolved() == []
    lpl.set(["foo:"])
    assert lpl.get() == ["foo:(!)"]
    assert not lpl.is_resolved()
    assert lpl.get_resolved() == ["bar:"]
    assert lpl.is_resolved()
    # append
    lpl.append("bar:")
    assert lpl.get() == ["bar:", "bar:(!)"]
    assert not lpl.is_resolved()
    with pytest.raises(AmiPathError):
        lpl.get_resolved()
    assert not lpl.is_resolved()
    lpl.remove("bar:(!)")
    # prepend
    lpl.prepend("baz:")
    assert lpl.get() == ["baz:(!)", "bar:"]
    assert not lpl.is_resolved()
    assert lpl.get_resolved() == ["baz:", "bar:"]
    assert lpl.is_resolved()
    assert str(lpl) == "[baz:,bar:]"
    assert (
        repr(lpl)
        == "LazyPathList(paths=[LazyPath(path=baz:, resolved_path=baz:), LazyPath(path=foo:, resolved_path=bar:)])"
    )
