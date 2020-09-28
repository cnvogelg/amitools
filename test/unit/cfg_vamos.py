from amitools.vamos.cfg import VamosMainParser


def cfg_vamos_log_ini_test():
    vmp = VamosMainParser()
    cfg = {
        "vamos": {
            "logging": "main:info,exec:debug",
            "log_file": "/foo/bar",
            "verbose": True,
            "quiet": True,
        }
    }
    vmp.parse_dict_config(cfg, "ini")
    assert vmp.get_log_dict() == {
        "logging": {
            "levels": {"main": "info", "exec": "debug"},
            "file": "/foo/bar",
            "verbose": True,
            "quiet": True,
            "timestamps": True,
        }
    }


def cfg_vamos_log_dict_test():
    vmp = VamosMainParser()
    cfg = {
        "logging": {
            "levels": {"main": "info", "exec": "debug"},
            "file": "bla",
            "verbose": True,
            "quiet": True,
            "timestamps": False,
        }
    }
    vmp.parse_dict_config(cfg)
    assert vmp.get_log_dict() == {
        "logging": {
            "levels": {"main": "info", "exec": "debug"},
            "file": "bla",
            "verbose": True,
            "quiet": True,
            "timestamps": False,
        }
    }


def cfg_vamos_log_args_test():
    vmp = VamosMainParser()
    args = ["--no-ts", "-v", "-q", "-L", "bla", "-l", "main:info,exec:debug", "bin"]
    vmp.parse(args=args)
    assert vmp.get_log_dict() == {
        "logging": {
            "levels": {"main": "info", "exec": "debug"},
            "file": "bla",
            "verbose": True,
            "quiet": True,
            "timestamps": False,
        }
    }
