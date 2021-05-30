import logging
from amitools.vamos.profiler import MainProfiler, Profiler
from amitools.vamos.cfgcore import ConfigDict


def profiler_main_disabled_test(caplog):
    caplog.set_level(logging.DEBUG, "prof")
    mp = MainProfiler()
    assert mp.parse_config(None)
    assert not mp.add_profiler(Profiler())
    mp.setup()
    mp.shutdown()
    assert caplog.record_tuples == []


def profiler_main_config_test(caplog, tmpdir):
    caplog.set_level(logging.INFO, "prof")
    path = str(tmpdir.join("prof.json"))
    mp = MainProfiler()
    cfg = ConfigDict(
        {"enabled": True, "output": {"dump": True, "file": path, "append": True}}
    )
    assert mp.parse_config(cfg)
    assert mp.enabled
    assert mp.file == path
    assert mp.append
    mp.setup()
    mp.shutdown()
    assert caplog.record_tuples == [
        ("prof", logging.INFO, "---------- Profiling Results ----------"),
    ]


def profiler_main_def_profiler_test(caplog):
    caplog.set_level(logging.INFO, "prof")
    p = Profiler()
    mp = MainProfiler(enabled=True)
    cfg = ConfigDict(
        {"enabled": True, "output": {"dump": True, "file": None, "append": True}}
    )
    assert mp.parse_config(cfg)
    assert mp.add_profiler(p)
    mp.setup()
    mp.shutdown()
    assert caplog.record_tuples == [
        ("prof", logging.INFO, "---------- Profiling Results ----------"),
        ("prof", logging.INFO, "----- profiler 'foo' -----"),
    ]


def profiler_main_file_test(caplog, tmpdir):
    caplog.set_level(logging.DEBUG, "prof")
    path = str(tmpdir.join("prof.json"))
    p = Profiler()
    mp = MainProfiler(enabled=True)
    cfg = ConfigDict(
        {"enabled": True, "output": {"dump": False, "file": path, "append": True}}
    )
    assert mp.parse_config(cfg)
    assert mp.add_profiler(p)
    mp.setup()
    mp.shutdown()
    assert caplog.record_tuples == [
        ("prof", logging.DEBUG, "added profiler 'foo'"),
        ("prof", logging.DEBUG, "saving profile data to '%s'" % path),
        ("prof", logging.DEBUG, "done saving."),
    ]
    caplog.clear()
    # now repeat setup to test appending
    p = Profiler()
    mp = MainProfiler(enabled=True)
    assert mp.parse_config(cfg)
    assert mp.add_profiler(p)
    mp.setup()
    mp.shutdown()
    assert caplog.record_tuples == [
        ("prof", logging.DEBUG, "added profiler 'foo'"),
        ("prof", logging.DEBUG, "loading profile data from '%s'" % path),
        ("prof", logging.DEBUG, "done loading."),
        ("prof", logging.DEBUG, "saving profile data to '%s'" % path),
        ("prof", logging.DEBUG, "done saving."),
    ]


class MyProfiler(Profiler):
    def __init__(self):
        self.foo = 0
        self.bar = "baz"
        self.got_setup = False
        self.got_shutdown = False

    def get_name(self):
        return "test"

    def parse_config(self, cfg):
        self.foo = cfg.foo
        self.bar = cfg.bar
        return True

    def set_data(self, data_dict):
        self.foo = data_dict.foo
        self.bar = data_dict.bar

    def get_data(self):
        return {"foo": self.foo, "bar": self.bar}

    def setup(self):
        self.got_setup = True

    def shutdown(self):
        self.got_shutdown = True

    def dump(self, write):
        write("foo=%d, bar='%s'", self.foo, self.bar)


def profiler_main_test_prof_cfg_test():
    p = MyProfiler()
    mp = MainProfiler(enabled=True)
    cfg = ConfigDict(
        {
            "enabled": True,
            "output": {"dump": True, "file": None, "append": True},
            "test": {"foo": 42, "bar": "hello"},
        }
    )
    assert mp.parse_config(cfg)
    assert mp.add_profiler(p)
    assert p.foo == 42
    assert p.bar == "hello"


def profiler_main_test_prof_load_test(tmpdir):
    path = str(tmpdir.join("prof.json"))
    cfg = ConfigDict(
        {"enabled": True, "output": {"dump": True, "file": path, "append": True}}
    )
    p = MyProfiler()
    mp = MainProfiler(enabled=True)
    assert mp.parse_config(cfg)
    assert mp.add_profiler(p)
    mp.setup()
    assert p.foo == 0
    assert p.bar == "baz"
    p.foo = 42
    p.bar = "hello"
    mp.shutdown()
    # load again
    p = MyProfiler()
    mp = MainProfiler(enabled=True)
    assert mp.parse_config(cfg)
    assert mp.add_profiler(p)
    mp.setup()
    assert p.foo == 42
    assert p.bar == "hello"
    mp.shutdown()


def profiler_main_test_prof_dump_test(caplog):
    caplog.set_level(logging.INFO, "prof")
    cfg = ConfigDict(
        {"enabled": True, "output": {"dump": True, "file": None, "append": True}}
    )
    p = MyProfiler()
    mp = MainProfiler(enabled=True)
    assert mp.parse_config(cfg)
    assert mp.add_profiler(p)
    mp.setup()
    assert p.foo == 0
    assert p.bar == "baz"
    p.foo = 42
    p.bar = "hello"
    mp.shutdown()
    assert caplog.record_tuples == [
        ("prof", logging.INFO, "---------- Profiling Results ----------"),
        ("prof", logging.INFO, "----- profiler 'test' -----"),
        ("prof", logging.INFO, "foo=42, bar='hello'"),
    ]
