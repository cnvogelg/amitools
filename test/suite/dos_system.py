import pytest


def dos_system_test(vamos):
    vamos.make_prog("proc_args")
    cmd_name = vamos.get_prog_bin_name("proc_args")
    vamos.run_prog_checked("dos_system", cmd_name + " hello!")


def dos_system_not_found_test(vamos):
    rc, stdout, stderr = vamos.run_prog("dos_system", "bla hello!")
    assert rc == 255
