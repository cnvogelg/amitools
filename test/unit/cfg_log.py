from amitools.vamos.cfg import LogParser
import argparse


def cfg_log_ini_test():
    lp = LogParser("vamos")
    ini_dict = {
        "vamos": {
            "logging": "main:info,exec:debug",
            "log_file": "/foo/bar",
            "verbose": True,
            "quiet": True,
        }
    }
    lp.parse_config(ini_dict, "ini")
    assert lp.get_cfg_dict() == {
        "logging": {
            "levels": {"main": "info", "exec": "debug"},
            "file": "/foo/bar",
            "verbose": True,
            "quiet": True,
            "timestamps": True,
        }
    }


def cfg_log_args_test():
    lp = LogParser("vamos")
    ap = argparse.ArgumentParser()
    lp.setup_args(ap)
    args = ap.parse_args(["-v", "-q", "-L", "/foo/bar", "-l", "main:info,exec:debug"])
    lp.parse_args(args)
    assert lp.get_cfg_dict() == {
        "logging": {
            "levels": {"main": "info", "exec": "debug"},
            "file": "/foo/bar",
            "verbose": True,
            "quiet": True,
            "timestamps": True,
        }
    }


def cfg_log_ini_no_args_test():
    lp = LogParser("vamos")
    ini_dict = {
        "vamos": {
            "logging": "main:info,exec:debug",
            "log_file": "/foo/bar",
            "verbose": True,
            "quiet": True,
        }
    }
    lp.parse_config(ini_dict, "ini")
    ap = argparse.ArgumentParser()
    lp.setup_args(ap)
    args = ap.parse_args([])
    lp.parse_args(args)
    assert lp.get_cfg_dict() == {
        "logging": {
            "levels": {"main": "info", "exec": "debug"},
            "file": "/foo/bar",
            "verbose": True,
            "quiet": True,
            "timestamps": True,
        }
    }
