import pytest


def exec_makefuncs_test(vamos):
    if vamos.flavor == "agcc":
        pytest.skip("math not supported")
    vamos.run_prog_checked("exec_makelib")
