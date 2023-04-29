import pytest
import platform


def math_double_trans_test(vamos):
    if platform.system() == "Linux":
        pytest.skip("some math trans ops differ in one bit")
    if vamos.flavor in ("sc", "agcc"):
        pytest.skip("math not supported")
    vamos.run_prog_check_data("math_double_trans", regex=True)
