import pytest


def dos_waitforchar_wait_test(vamos, tmpdir):
    # run waitforchar without input
    rc, stdout, stderr = vamos.run_prog(
        "dos_waitforchar",
        use_pty=True,
    )
    # timeout detected
    assert rc == 1
    # expect to read all 6 bytes of input
    assert stdout == ["timeout=100000", "result=0"]


def dos_waitforchar_char_test(vamos, tmpdir):
    # run waitforchar with input
    rc, stdout, stderr = vamos.run_prog(
        "dos_waitforchar",
        stdin="h",
        use_pty=True,
    )
    assert rc == 0
    # even without newline it returns data
    assert stdout == ["timeout=100000", "result=-1"]
