from amitools.vamos.cfgcore import DictTrafo


def cfgcore_dicttrafo_empty_test():
    dt = DictTrafo()
    data = {"A": 12, "B": "hello", "C": [1, 2, 3]}
    assert dt.transform(data) == {}


def cfgcore_dicttrafo_simple_test():
    cfg = {"a": {"x": "A", "y": "B"}, "b": "C"}
    dt = DictTrafo(cfg)
    data = {"A": 12, "B": "hello", "C": [1, 2, 3]}
    assert dt.transform(data) == {"a": {"x": 12, "y": "hello"}, "b": [1, 2, 3]}


def cfgcore_dicttrafo_prefix_test():
    cfg = {"a": {"x": "A", "y": "B"}, "b": "C"}
    dt = DictTrafo(cfg, prefix="tree")
    data = {"tree": {"A": 12, "B": "hello", "C": [1, 2, 3]}}
    assert dt.transform(data) == {"a": {"x": 12, "y": "hello"}, "b": [1, 2, 3]}


def cfgcore_dicttrafo_tuple_test():
    cfg = {"a": {"x": ("tree", "A"), "y": ("tree", "B")}, "b": ("tree", "C")}
    dt = DictTrafo(cfg)
    data = {"tree": {"A": 12, "B": "hello", "C": [1, 2, 3]}}
    assert dt.transform(data) == {"a": {"x": 12, "y": "hello"}, "b": [1, 2, 3]}


def cfgcore_dicttrafo_tuple_prefix_test():
    cfg = {"a": {"x": ("tree", "A"), "y": ("tree", "B")}, "b": ("tree", "C")}
    dt = DictTrafo(cfg, prefix=("x", "y"))
    data = {"x": {"y": {"tree": {"A": 12, "B": "hello", "C": [1, 2, 3]}}}}
    assert dt.transform(data) == {"a": {"x": 12, "y": "hello"}, "b": [1, 2, 3]}


def cfgcore_dicttrafo_callable_test():
    cfg = {
        "a": {
            "x": (lambda k, x: x * 2, ("tree", "A")),
            "y": (lambda k, x: x + " world", ("tree", "B")),
        },
        "b": (lambda k, x: sum(x), ("tree", "C")),
    }
    dt = DictTrafo(cfg, prefix=("x", "y"))
    data = {"x": {"y": {"tree": {"A": 12, "B": "hello", "C": [1, 2, 3]}}}}
    assert dt.transform(data) == {"a": {"x": 24, "y": "hello world"}, "b": 6}
