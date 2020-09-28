import pytest


def math_fast_trans_test(vamos):
    if vamos.flavor in ("sc", "agcc"):
        pytest.skip("math not supported")
    vamos.run_prog_check_data("math_fast_trans")
