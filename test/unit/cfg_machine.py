from amitools.vamos.cfg import MachineParser
import argparse


def cfg_machine_dict_test():
    lp = MachineParser()
    input_dict = {
        "machine": {
            "backend": {},
            "cpu": "68020",
            "ram_size": 512,
            "hw_exc": {},
        },
        "memmap": {"hw_access": "abort", "old_dos_guard": True},
    }
    lp.parse_config(input_dict, "dict")
    assert lp.get_cfg_dict() == input_dict


def cfg_machine_ini_test():
    lp = MachineParser("vamos")
    ini_dict = {
        "vamos": {
            "backend": "name:rmachine68k,host:localhost,port:1112",
            "cpu": "68020",
            "ram_size": 512,
            "hw_access": "abort",
            "old_dos_guard": True,
            "hw_exc": "zero_div:abort,bus:ignore",
        }
    }
    lp.parse_config(ini_dict, "ini")
    assert lp.get_cfg_dict() == {
        "machine": {
            "backend": {
                "name": "rmachine68k",
                "host": "localhost",
                "port": "1112",
            },
            "cpu": "68020",
            "ram_size": 512,
            "hw_exc": {"zero_div": "abort", "bus": "ignore"},
        },
        "memmap": {"hw_access": "abort", "old_dos_guard": True},
    }


def cfg_machine_args_test():
    lp = MachineParser()
    ap = argparse.ArgumentParser()
    lp.setup_args(ap)
    args = ap.parse_args(
        [
            "-C",
            "68020",
            "--old-dos-guard",
            "-m",
            "512",
            "-H",
            "abort",
            "-e",
            "bus:ignore",
            "-b",
            "name:rmachine68k,host:localhost,port:1112",
        ]
    )
    lp.parse_args(args)
    assert lp.get_cfg_dict() == {
        "machine": {
            "backend": {
                "name": "rmachine68k",
                "host": "localhost",
                "port": "1112",
            },
            "cpu": "68020",
            "ram_size": 512,
            "hw_exc": {"bus": "ignore"},
        },
        "memmap": {"hw_access": "abort", "old_dos_guard": True},
    }
