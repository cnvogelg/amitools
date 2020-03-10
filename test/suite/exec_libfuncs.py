import pytest


def exec_libfuncs_test(vamos):
    if vamos.flavor == "agcc":
        pytest.skip("math not supported")
    vamos.run_prog_checked("exec_libfuncs")
