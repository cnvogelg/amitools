import pytest


def dos_setmode_cooked_test(vamos, tmpdir):
    # run setmode in mode 0 (cooked)
    rc, stdout, stderr = vamos.run_prog(
        "dos_setmode",
        "0",
        stdin="hello\r",
        use_pty=True,
    )
    assert rc == 0
    # expect to read all 6 bytes of input
    assert stdout == ["mode=0", "hello", "read=6"]


def dos_setmode_raw_test(vamos, tmpdir):
    # run setmode in mode 1 (raw)
    rc, stdout, stderr = vamos.run_prog(
        "dos_setmode",
        "1",
        stdin="hello",
        use_pty=True,
    )
    assert rc == 0
    # even without newline it returns data
    assert stdout == ["mode=1", "read=5"]
