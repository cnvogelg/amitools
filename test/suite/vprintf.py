import pytest


def vprintf_test(vamos):
    if vamos.flavor == "agcc":
        pytest.skip("vprintf not supported")
    vamos.run_prog_check_data("vprintf")
