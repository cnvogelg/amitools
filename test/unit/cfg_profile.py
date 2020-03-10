from amitools.vamos.cfg import ProfileParser
import argparse


def cfg_profile_dict_test():
    lp = ProfileParser()
    input_dict = {
        "profile": {
            "enabled": True,
            "libs": {"names": ["exec.library", "dos.library"], "calls": True},
            "output": {"file": "foo/bar", "append": True, "dump": True},
        }
    }
    lp.parse_config(input_dict, "dict")
    assert lp.get_cfg_dict() == input_dict


def cfg_profile_args_test():
    lp = ProfileParser()
    ap = argparse.ArgumentParser()
    lp.setup_args(ap)
    args = ap.parse_args(
        [
            "--profile",
            "--profile-libs",
            "exec.library,dos.library",
            "--profile-lib-calls",
            "--profile-file",
            "foo/bar",
            "--profile-file-append",
            "--profile-dump",
        ]
    )
    lp.parse_args(args)
    assert lp.get_cfg_dict() == {
        "profile": {
            "enabled": True,
            "libs": {"names": ["exec.library", "dos.library"], "calls": True},
            "output": {"file": "foo/bar", "append": True, "dump": True},
        }
    }
