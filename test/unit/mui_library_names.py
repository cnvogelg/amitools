import argparse

import pytest

from amitools.fd import generate_fd, get_base_name, get_fd_name, read_lib_fd
from amitools.vamos.cfg import LibsParser
from amitools.vamos.libmgr import LibCfg, LibMgrCfg


@pytest.mark.parametrize("suffix", ["mui", "mcc", "mcp"])
def mui_library_names_test(suffix, tmp_path):
    name = "Example." + suffix
    parser = LibsParser()
    args = argparse.ArgumentParser()
    parser.setup_args(args)
    parser.parse_args(args.parse_args(["-O", name + "=mode:amiga"]))
    cfg = LibMgrCfg.from_dict(parser.get_cfg_dict())
    assert cfg.get_cfg(name).get_create_mode() == LibCfg.CREATE_MODE_AMIGA
    parser = LibsParser()
    parser.parse_config({name: {"mode": "off"}}, "ini")
    cfg = LibMgrCfg.from_dict(parser.get_cfg_dict())
    assert cfg.get_cfg(name).get_create_mode() == LibCfg.CREATE_MODE_OFF
    assert get_fd_name(name) == "Example_lib.fd"
    assert get_base_name(name) == "_ExampleBase"
    assert read_lib_fd(name, str(tmp_path)) is None
    fd = generate_fd(name)
    assert not fd.is_device
    assert fd.get_func_by_index(0).get_name() == "_OpenLib"


def mui_library_unknown_suffix_test():
    parser = LibsParser()
    args = argparse.ArgumentParser()
    parser.setup_args(args)
    with pytest.raises(ValueError):
        parser.parse_args(args.parse_args(["-O", "Example.unknown=mode:amiga"]))
