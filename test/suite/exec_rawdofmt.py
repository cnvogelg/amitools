import pytest


def exec_rawdofmt_test(vamos):
    if vamos.flavor == "agcc":
        pytest.skip("bstr problem")
    vamos.run_prog_check_data("exec_rawdofmt")
