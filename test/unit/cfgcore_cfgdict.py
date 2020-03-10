from amitools.vamos.cfgcore import ConfigDict


def cfgcore_cfgdict_default_test():
    cd = ConfigDict()
    cd["a"] = 10
    assert cd.a == 10


def cfgcore_cfgdict_data_test():
    rd = ConfigDict({"a": 10, "b": 20})
    assert rd.a == 10
    assert rd.b == 20
    rd.a = "hello"
    assert rd.a == "hello"
    assert rd["a"] == "hello"
    del rd.b
    assert rd == {"a": "hello"}


def cfgcore_cfgdict_clone_test():
    cfg = {"a": {"x": 10}, "b": {"y": 20}}
    cd = ConfigDict(cfg)
    assert cd.a.x == 10
    assert cd.b.y == 20
