import logging
from amitools.vamos.cfgcore import ConfigDict
from amitools.vamos.log import *


def do_log():
    log_main.debug("debug")
    log_main.info("info")
    log_main.warning("warn")
    log_main.error("error")

    log_mem.debug("debug")
    log_mem.info("info")
    log_mem.warning("warn")
    log_mem.error("error")


def vamos_log_setup_default_test(caplog):
    log_cfg = ConfigDict(
        {
            "file": None,
            "quiet": False,
            "verbose": False,
            "timestamps": True,
            "levels": None,
        }
    )
    assert log_setup(log_cfg)
    do_log()
    assert caplog.record_tuples == [
        ("main", logging.WARNING, "warn"),
        ("main", logging.ERROR, "error"),
        ("mem", logging.WARNING, "warn"),
        ("mem", logging.ERROR, "error"),
    ]


def vamos_log_setup_verbose_test(caplog):
    log_cfg = ConfigDict(
        {
            "file": None,
            "quiet": False,
            "verbose": True,  # verbose sets main to info
            "timestamps": True,
            "levels": None,
        }
    )
    assert log_setup(log_cfg)
    do_log()
    assert caplog.record_tuples == [
        ("main", logging.INFO, "info"),
        ("main", logging.WARNING, "warn"),
        ("main", logging.ERROR, "error"),
        ("mem", logging.WARNING, "warn"),
        ("mem", logging.ERROR, "error"),
    ]


def vamos_log_setup_quiet_test(caplog):
    log_cfg = ConfigDict(
        {
            "file": None,
            "quiet": True,  # set all levels to error
            "verbose": False,
            "timestamps": True,
            "levels": None,
        }
    )
    assert log_setup(log_cfg)
    do_log()
    assert caplog.record_tuples == [
        ("main", logging.ERROR, "error"),
        ("mem", logging.ERROR, "error"),
    ]


def vamos_log_setup_levels_test(caplog):
    log_cfg = ConfigDict(
        {
            "file": None,
            "quiet": False,
            "verbose": False,
            "timestamps": True,
            "levels": {"mem": "info"},
        }
    )
    assert log_setup(log_cfg)
    do_log()
    assert caplog.record_tuples == [
        ("main", logging.WARN, "warn"),
        ("main", logging.ERROR, "error"),
        ("mem", logging.INFO, "info"),
        ("mem", logging.WARN, "warn"),
        ("mem", logging.ERROR, "error"),
    ]


def vamos_log_setup_levels_fail_test(caplog):
    log_cfg = ConfigDict(
        {
            "file": None,
            "quiet": False,
            "verbose": False,
            "timestamps": True,
            "levels": {"foo": "info"},
        }
    )
    assert not log_setup(log_cfg)
    assert caplog.record_tuples == [("config", logging.ERROR, "invalid logger: foo")]


def vamos_log_setup_levels_fail2_test(caplog):
    log_cfg = ConfigDict(
        {
            "file": None,
            "quiet": False,
            "verbose": False,
            "timestamps": True,
            "levels": {"mem": "foo"},
        }
    )
    assert not log_setup(log_cfg)
    assert caplog.record_tuples == [("config", logging.ERROR, "invalid log level: foo")]
