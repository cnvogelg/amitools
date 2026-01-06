import pytest

from amitools.vamos.error import VamosInternalError
from amitools.vamos.machine import InvalidMemoryAccessError


def test_raise_invalid_test(vamos):
    retcode, stdout, stderr = vamos.run_prog("test_raise", "bla")
    assert retcode == 0
    assert stdout == ["VamosTest: Invalid Error: bla"]
    assert stderr == []


def test_raise_runtime_error_test(vamos):
    with pytest.raises(RuntimeError):
        vamos.run_prog("test_raise", "RuntimeError")


def test_raise_vamos_internal_error_test(vamos):
    with pytest.raises(VamosInternalError):
        vamos.run_prog("test_raise", "VamosInternalError")
