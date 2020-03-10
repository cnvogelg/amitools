import pytest
from amitools.vamos.libmgr import LibCfg, LibMgrCfg
from amitools.vamos.cfgcore import ConfigDict


def libmgr_cfg_lib_default_test():
    lc = LibCfg()
    assert lc.get_create_mode() == LibCfg.CREATE_MODE_AUTO
    assert lc.get_force_version() is None
    assert lc.get_expunge_mode() == LibCfg.EXPUNGE_MODE_LAST_CLOSE
    assert lc.get_num_fake_funcs() == 0
    txt = str(lc)
    assert (
        txt
        == "LibCfg(create_mode=auto, force_version=None, expunge_mode=last_close, num_fake_funcs=0)"
    )


def libmgr_cfg_lib_custom_test():
    lc = LibCfg(LibCfg.CREATE_MODE_OFF, 1, LibCfg.EXPUNGE_MODE_NO_MEM, 42)
    assert lc.get_create_mode() == LibCfg.CREATE_MODE_OFF
    assert lc.get_force_version() is 1
    assert lc.get_expunge_mode() == LibCfg.EXPUNGE_MODE_NO_MEM
    assert lc.get_num_fake_funcs() == 42
    txt = str(lc)
    assert (
        txt
        == "LibCfg(create_mode=off, force_version=1, expunge_mode=no_mem, num_fake_funcs=42)"
    )


def libmgr_cfg_lib_fail_test():
    with pytest.raises(ValueError):
        lc = LibCfg(create_mode="bla")
    with pytest.raises(ValueError):
        lc = LibCfg(expunge_mode="foo")


def libmgr_cfg_lib_eq_test():
    lc1 = LibCfg()
    lc2 = LibCfg()
    assert lc1 == lc2
    lc3 = LibCfg(force_version=1)
    assert lc1 != lc3


def libmgr_cfg_mgr_lib_test():
    lmc = LibMgrCfg()
    lc = LibCfg(LibCfg.CREATE_MODE_OFF, 1, LibCfg.EXPUNGE_MODE_NO_MEM)
    lmc.add_lib_cfg("bla.library", lc)
    assert lmc.get_lib_cfg("bla.library") == lc
    assert lmc.get_lib_cfg("foo.library") == LibCfg()
    lc2 = LibCfg(LibCfg.CREATE_MODE_AMIGA, 11, LibCfg.EXPUNGE_MODE_NO_MEM)
    lmc.add_lib_cfg("foo.library", lc2)
    assert lmc.get_lib_cfg("foo.library") == lc2


def libmgr_cfg_mgr_dev_test():
    lmc = LibMgrCfg()
    lc = LibCfg(LibCfg.CREATE_MODE_OFF, 1, LibCfg.EXPUNGE_MODE_NO_MEM)
    lmc.add_dev_cfg("bla.device", lc)
    assert lmc.get_dev_cfg("bla.device") == lc
    assert lmc.get_dev_cfg("foo.device") == LibCfg()
    lc2 = LibCfg(LibCfg.CREATE_MODE_AMIGA, 11, LibCfg.EXPUNGE_MODE_NO_MEM)
    lmc.add_dev_cfg("foo.device", lc2)
    assert lmc.get_dev_cfg("foo.device") == lc2


def libmgr_cfg_mgr_lib_default_test():
    lcd = LibCfg(LibCfg.CREATE_MODE_OFF, 1, LibCfg.EXPUNGE_MODE_NO_MEM)
    lmc = LibMgrCfg(lib_default=lcd)
    assert lmc.get_lib_cfg("bla.library") == lcd
    lc = LibCfg(LibCfg.CREATE_MODE_OFF, 1, LibCfg.EXPUNGE_MODE_NO_MEM)
    lmc.add_lib_cfg("bla.library", lc)
    assert lmc.get_lib_cfg("bla.library") == lc


def libmgr_cfg_mgr_dev_default_test():
    lcd = LibCfg(LibCfg.CREATE_MODE_OFF, 1, LibCfg.EXPUNGE_MODE_NO_MEM)
    lmc = LibMgrCfg(dev_default=lcd)
    assert lmc.get_dev_cfg("bla.device") == lcd
    lc = LibCfg(LibCfg.CREATE_MODE_OFF, 1, LibCfg.EXPUNGE_MODE_NO_MEM)
    lmc.add_dev_cfg("bla.device", lc)
    assert lmc.get_dev_cfg("bla.device") == lc


def libmgr_cfg_mgr_from_dict_default_test():
    cfg = ConfigDict(
        {
            "libs": ConfigDict(
                {
                    "*.library": ConfigDict(
                        {
                            "mode": "fake",
                            "version": 23,
                            "expunge": "shutdown",
                            "num_fake_funcs": 1,
                        }
                    )
                }
            ),
            "devs": ConfigDict(
                {
                    "*.device": ConfigDict(
                        {
                            "mode": "amiga",
                            "version": 42,
                            "expunge": "last_close",
                            "num_fake_funcs": 2,
                        }
                    )
                }
            ),
        }
    )
    mgr = LibMgrCfg.from_dict(cfg)
    assert mgr
    lib_default = mgr.get_lib_default()
    assert lib_default
    assert lib_default.get_create_mode() == LibCfg.CREATE_MODE_FAKE
    assert lib_default.get_force_version() == 23
    assert lib_default.get_expunge_mode() == LibCfg.EXPUNGE_MODE_SHUTDOWN
    assert lib_default.get_num_fake_funcs() == 1
    dev_default = mgr.get_dev_default()
    assert dev_default
    assert dev_default.get_create_mode() == LibCfg.CREATE_MODE_AMIGA
    assert dev_default.get_force_version() == 42
    assert dev_default.get_expunge_mode() == LibCfg.EXPUNGE_MODE_LAST_CLOSE
    assert dev_default.get_num_fake_funcs() == 2


def get_custom_cfg():
    return ConfigDict(
        {
            "libs": ConfigDict(
                {
                    "*.library": ConfigDict(
                        {
                            "mode": "fake",
                            "version": 23,
                            "expunge": "shutdown",
                            "num_fake_funcs": 1,
                        }
                    ),
                    "foo.library": ConfigDict(
                        {
                            "mode": "amiga",
                            "version": 42,
                            "expunge": "last_close",
                            "num_fake_funcs": 2,
                        }
                    ),
                    "libs/foo.library": ConfigDict(
                        {
                            "mode": "vamos",
                            "version": 43,
                            "expunge": "last_close",
                            "num_fake_funcs": 10,
                        }
                    ),
                }
            ),
            "devs": ConfigDict(
                {
                    "*.device": ConfigDict(
                        {
                            "mode": "amiga",
                            "version": 42,
                            "expunge": "last_close",
                            "num_fake_funcs": 3,
                        }
                    ),
                    "bar.device": ConfigDict(
                        {
                            "mode": "fake",
                            "version": 23,
                            "expunge": "shutdown",
                            "num_fake_funcs": 4,
                        }
                    ),
                    "devs/bar.device": ConfigDict(
                        {
                            "mode": "vamos",
                            "version": 43,
                            "expunge": "last_close",
                            "num_fake_funcs": 11,
                        }
                    ),
                }
            ),
        }
    )


def libmgr_cfg_mgr_from_dict_custom_test():
    cfg = get_custom_cfg()
    mgr = LibMgrCfg.from_dict(cfg)
    assert mgr
    lib_cfg = mgr.get_lib_cfg("foo.library")
    assert lib_cfg
    assert lib_cfg.get_create_mode() == LibCfg.CREATE_MODE_AMIGA
    assert lib_cfg.get_force_version() == 42
    assert lib_cfg.get_expunge_mode() == LibCfg.EXPUNGE_MODE_LAST_CLOSE
    assert lib_cfg.get_num_fake_funcs() == 2
    dev_cfg = mgr.get_dev_cfg("bar.device")
    assert dev_cfg
    assert dev_cfg.get_create_mode() == LibCfg.CREATE_MODE_FAKE
    assert dev_cfg.get_force_version() == 23
    assert dev_cfg.get_expunge_mode() == LibCfg.EXPUNGE_MODE_SHUTDOWN
    assert dev_cfg.get_num_fake_funcs() == 4


def libmgr_cfg_mgr_auto_test():
    cfg = get_custom_cfg()
    mgr = LibMgrCfg.from_dict(cfg)
    assert mgr
    lib_cfg = mgr.get_cfg("foo.library")
    assert lib_cfg
    assert lib_cfg.get_create_mode() == LibCfg.CREATE_MODE_AMIGA
    assert lib_cfg.get_force_version() == 42
    assert lib_cfg.get_expunge_mode() == LibCfg.EXPUNGE_MODE_LAST_CLOSE
    assert lib_cfg.get_num_fake_funcs() == 2
    lib_default = mgr.get_cfg(["bla.library"])
    assert lib_default
    assert lib_default.get_create_mode() == LibCfg.CREATE_MODE_FAKE
    assert lib_default.get_force_version() == 23
    assert lib_default.get_expunge_mode() == LibCfg.EXPUNGE_MODE_SHUTDOWN
    assert lib_default.get_num_fake_funcs() == 1
    dev_cfg = mgr.get_cfg("bar.device")
    assert dev_cfg
    assert dev_cfg.get_create_mode() == LibCfg.CREATE_MODE_FAKE
    assert dev_cfg.get_force_version() == 23
    assert dev_cfg.get_expunge_mode() == LibCfg.EXPUNGE_MODE_SHUTDOWN
    assert dev_cfg.get_num_fake_funcs() == 4
    dev_default = mgr.get_cfg(["bla.device"])
    assert dev_default
    assert dev_default.get_create_mode() == LibCfg.CREATE_MODE_AMIGA
    assert dev_default.get_force_version() == 42
    assert dev_default.get_expunge_mode() == LibCfg.EXPUNGE_MODE_LAST_CLOSE
    assert dev_default.get_num_fake_funcs() == 3


def libmgr_cfg_mgr_base_name_test():
    cfg = get_custom_cfg()
    mgr = LibMgrCfg.from_dict(cfg)
    assert mgr
    # fall back to 'foo.library' not the default
    lib_cfg = mgr.get_cfg("bla/foo.library")
    assert lib_cfg
    assert lib_cfg.get_create_mode() == LibCfg.CREATE_MODE_AMIGA
    assert lib_cfg.get_force_version() == 42
    assert lib_cfg.get_expunge_mode() == LibCfg.EXPUNGE_MODE_LAST_CLOSE
    assert lib_cfg.get_num_fake_funcs() == 2
    # use exact match
    lib_cfg = mgr.get_cfg("libs/foo.library")
    assert lib_cfg
    assert lib_cfg.get_create_mode() == LibCfg.CREATE_MODE_VAMOS
    assert lib_cfg.get_force_version() == 43
    assert lib_cfg.get_expunge_mode() == LibCfg.EXPUNGE_MODE_LAST_CLOSE
    assert lib_cfg.get_num_fake_funcs() == 10
    # fall back to 'bar.device' not the default
    dev_cfg = mgr.get_cfg("baz/bar.device")
    assert dev_cfg
    assert dev_cfg.get_create_mode() == LibCfg.CREATE_MODE_FAKE
    assert dev_cfg.get_force_version() == 23
    assert dev_cfg.get_expunge_mode() == LibCfg.EXPUNGE_MODE_SHUTDOWN
    assert dev_cfg.get_num_fake_funcs() == 4
    # use exact match
    dev_cfg = mgr.get_cfg("devs/bar.device")
    assert dev_cfg
    assert dev_cfg.get_create_mode() == LibCfg.CREATE_MODE_VAMOS
    assert dev_cfg.get_force_version() == 43
    assert dev_cfg.get_expunge_mode() == LibCfg.EXPUNGE_MODE_LAST_CLOSE
    assert dev_cfg.get_num_fake_funcs() == 11


def libmgr_cfg_dump_test(capsys):
    cfg = get_custom_cfg()
    mgr = LibMgrCfg.from_dict(cfg)
    mgr.dump()
    captured = capsys.readouterr()
    assert captured.out.splitlines() == [
        "libs config:",
        "  default: LibCfg(create_mode=fake, force_version=23, expunge_mode=shutdown, num_fake_funcs=1)",
        "  lib 'foo.library': LibCfg(create_mode=amiga, force_version=42, expunge_mode=last_close, num_fake_funcs=2)",
        "  lib 'libs/foo.library': LibCfg(create_mode=vamos, force_version=43, expunge_mode=last_close, num_fake_funcs=10)",
        "devs config:",
        "  default: LibCfg(create_mode=amiga, force_version=42, expunge_mode=last_close, num_fake_funcs=3)",
        "  dev 'bar.device': LibCfg(create_mode=fake, force_version=23, expunge_mode=shutdown, num_fake_funcs=4)",
        "  dev 'devs/bar.device': LibCfg(create_mode=vamos, force_version=43, expunge_mode=last_close, num_fake_funcs=11)",
    ]
