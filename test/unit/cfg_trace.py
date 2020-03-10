from amitools.vamos.cfg import TraceParser
import argparse


def cfg_trace_dict_test():
    lp = TraceParser()
    input_dict = {
        "trace": {
            "instr": True,
            "memory": True,
            "vamos_ram": True,
            "reg_dump": True,
            "labels": True,
        }
    }
    lp.parse_config(input_dict, "dict")
    assert lp.get_cfg_dict() == input_dict


def cfg_trace_ini_test():
    lp = TraceParser("vamos")
    ini_dict = {
        "vamos": {
            "instr_trace": True,
            "memory_trace": True,
            "internal_memory_trace": True,
            "reg_dump": True,
            "labels": True,
        }
    }
    lp.parse_config(ini_dict, "ini")
    assert lp.get_cfg_dict() == {
        "trace": {
            "instr": True,
            "memory": True,
            "vamos_ram": True,
            "reg_dump": True,
            "labels": True,
        }
    }


def cfg_trace_args_test():
    lp = TraceParser()
    ap = argparse.ArgumentParser()
    lp.setup_args(ap)
    args = ap.parse_args(["-I", "-t", "-T", "-r", "-B"])
    lp.parse_args(args)
    assert lp.get_cfg_dict() == {
        "trace": {
            "instr": True,
            "memory": True,
            "vamos_ram": True,
            "reg_dump": True,
            "labels": True,
        }
    }
