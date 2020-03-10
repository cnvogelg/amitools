import pytest


def dos_runcmd_test(vamos):
    if vamos.flavor == "agcc":
        pytest.skip("needs stdlib")
    vamos.make_prog("proc_args")
    cmd_name = vamos.get_prog_bin_name("proc_args")
    vamos.run_prog_checked("dos_runcmd", cmd_name, "hello!")
