from amitools.vamos.path import AssignManager, VolumeManager
from amitools.vamos.cfgcore import ConfigDict


def setup_am(my_path):
    v = VolumeManager()
    v.add_volume("bla:" + my_path)
    a = AssignManager(v)
    return a


def path_assign_add_del_test(tmpdir):
    my_path = str(tmpdir)
    a = setup_am(my_path)
    a.setup()
    # invalid
    assert not a.add_assign("")
    assert not a.add_assign("foo")
    assert not a.add_assign("foo:")
    # volume of same name
    assert not a.add_assign("bla:foo:")
    assert not a.add_assign("BLA:foo:")
    # ok
    assert a.add_assign("foo:bla:")
    assert a.is_assign("foo")
    assert a.is_assign("FOO")
    assert a.is_assign("Foo")
    assert a.get_all_names() == ["foo"]
    assert a.get_assign("Foo").get_assigns() == ["bla:"]
    # ok
    assert a.add_assign("Baz:foo:bla/blup")
    assert a.is_assign("baz")
    assert a.is_assign("BAZ")
    assert a.get_all_names() == ["foo", "Baz"]
    assert a.get_assign("baz").get_assigns() == ["foo:bla/blup"]
    # invalid path
    assert not a.add_assign("bar:bla")
    # duplicate
    assert not a.add_assign("foo:blub:")
    assert not a.add_assign("FOO:blub:")
    # del foo
    assert a.del_assign("foo")
    # not found
    assert not a.del_assign("bar")
    a.shutdown()


def path_assign_add_multi_test(tmpdir):
    my_path = str(tmpdir)
    a = setup_am(my_path)
    # add multiple assigns
    a1 = a.add_assign("foo:bla:+bla:tmp")
    assert a1
    assert a1.get_assigns() == ["bla:", "bla:tmp"]
    # replace foo
    a2 = a.add_assign("foo:bla:pop")
    assert a2
    assert a2.get_assigns() == ["bla:pop"]
    # append
    a3 = a.add_assign("foo:+bla:pip")
    assert a3
    assert a2 is a3
    assert a3.get_assigns() == ["bla:pop", "bla:pip"]
    # try setup
    assert a.setup()
    a.shutdown()


def path_assign_resolve_test(tmpdir):
    my_path = str(tmpdir)
    a = setup_am(my_path)
    a.setup()
    a.add_assign("Foo:blA:blub")
    a.add_assign("Baz:foo:bla/plop")
    a.add_assign("multi:foo:tmp+baz:")
    ar = a.resolve_assigns
    # relative paths
    assert ar("rel/path") == "rel/path"
    assert ar(":rel/path") == ":rel/path"
    # volume path
    assert ar("Bla:abs/path") == "Bla:abs/path"
    assert ar("BLA:abs/path") == "BLA:abs/path"
    assert ar("bla:abs/path") == "bla:abs/path"
    # single assign
    assert ar("Foo:my/path") == "blA:blub/my/path"
    assert ar("foo:my/path") == "blA:blub/my/path"
    # single assign recursive
    assert ar("baz:my/path") == "blA:blub/bla/plop/my/path"
    # multi assign
    assert ar("multi:my/path") == ["blA:blub/tmp/my/path", "blA:blub/bla/plop/my/path"]
    # not an assign
    assert ar("what:is/here") == "what:is/here"
    # non recursive
    assert ar("Baz:", False) == "foo:bla/plop"
    assert ar("MULTI:", False) == ["foo:tmp", "baz:"]
    a.shutdown()


def path_assign_resolve_as_list_test(tmpdir):
    my_path = str(tmpdir)
    a = setup_am(my_path)
    a.setup()
    a.add_assign("Foo:blA:blub")
    a.add_assign("Baz:foo:bla/plop")
    a.add_assign("multi:foo:tmp+baz:")

    def ar(path, recursive=True):
        return a.resolve_assigns(path, recursive, as_list=True)

    # relative paths
    assert ar("rel/path") == ["rel/path"]
    assert ar(":rel/path") == [":rel/path"]
    # volume path
    assert ar("Bla:abs/path") == ["Bla:abs/path"]
    assert ar("BLA:abs/path") == ["BLA:abs/path"]
    assert ar("bla:abs/path") == ["bla:abs/path"]
    # single assign
    assert ar("Foo:my/path") == ["blA:blub/my/path"]
    assert ar("foo:my/path") == ["blA:blub/my/path"]
    # single assign recursive
    assert ar("baz:my/path") == ["blA:blub/bla/plop/my/path"]
    # multi assign
    assert ar("multi:my/path") == ["blA:blub/tmp/my/path", "blA:blub/bla/plop/my/path"]
    # not an assign
    assert ar("what:is/here") == ["what:is/here"]
    # non recursive
    assert ar("Baz:", False) == ["foo:bla/plop"]
    assert ar("MULTI:", False) == ["foo:tmp", "baz:"]
    a.shutdown()


def path_assign_config_test(tmpdir):
    my_path = str(tmpdir)
    a = setup_am(my_path)
    cfg = ConfigDict(
        {"assigns": ["Foo:blA:blub", "Baz:foo:bla/plop", "multi:foo:tmp+baz:"]}
    )
    assert a.parse_config(cfg)
    a.setup()
    ar = a.resolve_assigns
    # relative paths
    assert ar("rel/path") == "rel/path"
    assert ar(":rel/path") == ":rel/path"
    # volume path
    assert ar("Bla:abs/path") == "Bla:abs/path"
    assert ar("BLA:abs/path") == "BLA:abs/path"
    assert ar("bla:abs/path") == "bla:abs/path"
    # single assign
    assert ar("Foo:my/path") == "blA:blub/my/path"
    assert ar("foo:my/path") == "blA:blub/my/path"
    # single assign recursive
    assert ar("baz:my/path") == "blA:blub/bla/plop/my/path"
    # multi assign
    assert ar("multi:my/path") == ["blA:blub/tmp/my/path", "blA:blub/bla/plop/my/path"]
    # not an assign
    assert ar("what:is/here") == "what:is/here"
    a.shutdown()


def path_assign_cfg_create_test(tmpdir):
    my_path = str(tmpdir)
    a = setup_am(my_path)
    a.setup()
    # no dir created
    assert a.add_assign("foo:bla:blub")
    assert not tmpdir.join("blub").check(dir=1)
    # dir created
    assert a.add_assign("bar:bla:blub?create")
    assert tmpdir.join("blub").check(dir=1)
    a.shutdown()
