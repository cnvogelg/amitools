import pytest

from amitools.vamos.lib.dos.Printf import printf_parse_string


def test_printf_width_padding_regression():
    assert printf_parse_string("%8.8lx").elements[0].gen_sys_printf_format() == "%8X"
    assert printf_parse_string("%08.8lx").elements[0].gen_sys_printf_format() == "%08X"
    assert printf_parse_string("%-8lx").elements[0].gen_sys_printf_format() == "%-8X"


def exec_rawdofmt_test(vamos):
    if vamos.flavor == "agcc":
        pytest.skip("bstr problem")
    vamos.run_prog_check_data("exec_rawdofmt")
