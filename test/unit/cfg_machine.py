from amitools.vamos.cfg import MachineParser
import argparse


def cfg_machine_dict_test():
    lp = MachineParser()
    input_dict = {
        "machine": {
            "cpu": "68020",
            "max_cycles": 23,
            "cycles_per_run": 42,
            "ram_size": 512,
        },
        "memmap": {"hw_access": "abort", "old_dos_guard": True},
    }
    lp.parse_config(input_dict, "dict")
    assert lp.get_cfg_dict() == input_dict


def cfg_machine_ini_test():
    lp = MachineParser("vamos")
    ini_dict = {
        "vamos": {
            "cpu": "68020",
            "max_cycles": 23,
            "cycles_per_run": 42,
            "ram_size": 512,
            "hw_access": "abort",
            "old_dos_guard": True,
        }
    }
    lp.parse_config(ini_dict, "ini")
    assert lp.get_cfg_dict() == {
        "machine": {
            "cpu": "68020",
            "max_cycles": 23,
            "cycles_per_run": 42,
            "ram_size": 512,
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
            "--max-cycles",
            "23",
            "--cycles-per-block",
            "42",
            "--old-dos-guard",
            "-m",
            "512",
            "-H",
            "abort",
        ]
    )
    lp.parse_args(args)
    assert lp.get_cfg_dict() == {
        "machine": {
            "cpu": "68020",
            "max_cycles": 23,
            "cycles_per_run": 42,
            "ram_size": 512,
        },
        "memmap": {"hw_access": "abort", "old_dos_guard": True},
    }
