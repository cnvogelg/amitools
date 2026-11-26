import argparse

from amitools.vamos.cfg import CommandParser


def cfg_command_dict_test():
    cp = CommandParser()
    input_dict = {
        "command": {
            "resident_dir": ["/one", "/two"],
            "no_internal_commands": True,
        }
    }
    cp.parse_config(input_dict, "dict")
    assert cp.get_cfg_dict() == input_dict


def cfg_command_defaults_test():
    cp = CommandParser()
    assert cp.get_cfg_dict() == {
        "command": {"resident_dir": None, "no_internal_commands": False}
    }


def cfg_command_args_test():
    cp = CommandParser()
    ap = argparse.ArgumentParser()
    cp.setup_args(ap)
    args = ap.parse_args(
        [
            "--resident-dir",
            "/one",
            "--resident-dir",
            "/two",
            "--no-internal-commands",
        ]
    )
    cp.parse_args(args)
    assert cp.get_cfg_dict() == {
        "command": {
            "resident_dir": ["/one", "/two"],
            "no_internal_commands": True,
        }
    }
