from amitools.vamos.cfg import ProcessParser
import argparse


def cfg_proc_dict_test():
    lp = ProcessParser()
    input_dict = {
        "process": {
            "command": {
                "binary": "foo",
                "args": ["a", "b", "c,d", "(e)", "*f"],
                "shell": True,
                "pure_ami_path": True,
                "raw_arg": True,
            },
            "stack": 4,
        }
    }
    lp.parse_config(input_dict, "dict")
    assert lp.get_cfg_dict() == input_dict


def cfg_proc_ini_test():
    lp = ProcessParser("vamos")
    ini_dict = {
        "vamos": {
            "shell": True,
            "pure_ami_paths": True,
            "raw_arg": True,
            "stack_size": 4,
        }
    }
    lp.parse_config(ini_dict, "ini")
    assert lp.get_cfg_dict() == {
        "process": {
            "command": {
                "binary": None,
                "args": None,
                "shell": True,
                "pure_ami_path": True,
                "raw_arg": True,
            },
            "stack": 4,
        }
    }


def cfg_proc_args_test():
    lp = ProcessParser()
    ap = argparse.ArgumentParser()
    lp.setup_args(ap)
    args = ap.parse_args(
        ["-x", "-P", "-R", "-s", "4", "foo", "a", "b", "c,d", "(e)", "*f"]
    )
    lp.parse_args(args)
    assert lp.get_cfg_dict() == {
        "process": {
            "command": {
                "binary": "foo",
                "args": ["a", "b", "c,d", "(e)", "*f"],
                "shell": True,
                "pure_ami_path": True,
                "raw_arg": True,
            },
            "stack": 4,
        }
    }
