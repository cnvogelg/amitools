from amitools.vamos.cfg import ScheduleParser
import argparse


def cfg_schedule_dict_test():
    lp = ScheduleParser()
    input_dict = {
        "schedule": {
            "slice_cycles": 2000,
        }
    }
    lp.parse_config(input_dict, "dict")
    assert lp.get_cfg_dict() == input_dict


def cfg_schedule_ini_test():
    lp = ScheduleParser("vamos")
    ini_dict = {"vamos": {"slice_cycles": 2000}}
    lp.parse_config(ini_dict, "ini")
    assert lp.get_cfg_dict() == {
        "schedule": {
            "slice_cycles": 2000,
        }
    }


def cfg_schedule_args_test():
    lp = ScheduleParser()
    ap = argparse.ArgumentParser()
    lp.setup_args(ap)
    args = ap.parse_args(
        [
            "--slice-cycles",
            "2000",
        ]
    )
    lp.parse_args(args)
    assert lp.get_cfg_dict() == {
        "schedule": {
            "slice_cycles": 2000,
        }
    }
