"""Native handler volume config (HANDLER.md step 24a).

A ``?handler=native`` volume names the handler binary and the ``--disk``
partition it mounts. The options are validated once by :class:`NativeConfig`,
so the tests cover the defaults, the key aliases, the spec round-trip and the
rejection of unknown or non-numeric options.
"""

import pytest

from amitools.vamos.handler import HandlerError, HandlerManager
from amitools.vamos.handler.base import ERROR_BAD_NUMBER
from amitools.vamos.handler.native import NativeConfig, NativeHandler, native_factory
from amitools.vamos.path import Spec, VamosPathManager


def handler_native_config_defaults_test():
    cfg = NativeConfig({})
    assert cfg.binary is None
    assert cfg.device is None
    assert cfg.unit is None
    assert cfg.part is None
    # a C handler and a plain 4k stack at priority 0
    assert cfg.globvec == -1
    assert cfg.stack == 4096
    assert cfg.priority == 0


def handler_native_config_values_test():
    cfg = NativeConfig(
        {
            "handler": "native",
            "binary": "/path/pfs3aio",
            "device": "scsi.device",
            "unit": "2",
            "part": "DH0",
            "globvec": "-2",
            "stack": "0x2000",
            "priority": 5,
        }
    )
    assert cfg.binary == "/path/pfs3aio"
    assert cfg.device == "scsi.device"
    assert cfg.unit == 2
    assert cfg.part == "DH0"
    assert cfg.globvec == -2
    assert cfg.stack == 0x2000
    assert cfg.priority == 5


def handler_native_config_alias_test():
    cfg = NativeConfig({"handler_binary": "/path/aroffs", "partition": "DH1"})
    assert cfg.binary == "/path/aroffs"
    assert cfg.part == "DH1"
    # the explicit ``binary`` wins over ``handler_binary``
    cfg = NativeConfig({"binary": "a", "handler_binary": "b"})
    assert cfg.binary == "a"


def handler_native_config_unknown_key_test():
    with pytest.raises(HandlerError) as exc:
        NativeConfig({"handler": "native", "nope": 1})
    assert exc.value.code == ERROR_BAD_NUMBER


def handler_native_config_bad_number_test():
    with pytest.raises(HandlerError) as exc:
        NativeConfig({"globvec": "asm"})
    assert exc.value.code == ERROR_BAD_NUMBER
    # a bare ``?stack`` parses as a bool, which is not a number
    with pytest.raises(HandlerError) as exc:
        NativeConfig({"stack": True})
    assert exc.value.code == ERROR_BAD_NUMBER


def handler_native_config_factory_detached_test():
    cfg = {"handler": "native", "binary": "/path/pfs3aio", "globvec": "-2"}
    handler = native_factory("work", None, cfg, None)
    assert isinstance(handler, NativeHandler)
    assert handler.is_native
    # the factory does not touch the machine: the handler is started later
    assert handler.manager is None
    assert handler.exec_lib is None
    assert handler.binary == "/path/pfs3aio"
    assert handler.config.globvec == -2


def handler_native_config_volume_spec_test(tmp_path):
    pm = VamosPathManager(vols_base_dir=str(tmp_path), auto_volumes=[], auto_assigns=[])
    vm = pm.get_vol_mgr()
    spec = "WORK:?handler=native,binary=/path/pfs3aio,device=DH0,globvec=-2"
    vol = vm.add_volume(spec)
    assert vol is not None
    # a native handler has no host directory of its own
    assert vol.get_path() is None
    assert vol.get_cfg()["handler"] == "native"
    # the spec keeps the values as strings; the config converts them
    assert vol.get_cfg()["globvec"] == "-2"
    assert pm.setup()

    mgr = HandlerManager(pm)
    handler = mgr.bind_volume(vol)
    assert isinstance(handler, NativeHandler)
    assert handler.is_native
    assert handler.binary == "/path/pfs3aio"
    assert handler.config.device == "DH0"
    assert handler.config.globvec == -2
    assert mgr.get_handler("work") is handler


def handler_native_config_spec_parse_test():
    spec = Spec.parse("WORK:?handler=native,binary=x,globvec=-1")
    cfg = NativeConfig(spec.get_cfg())
    assert cfg.binary == "x"
    assert cfg.globvec == -1
