import pytest


def dos_seek_test(vamos, tmpdir):
    test_file = str(tmpdir / "test")
    rc, stdout, stderr = vamos.run_prog("dos_seek", "root:" + test_file[1:])
    assert rc == 0
    assert stderr == []
    assert stdout == [
        "old_pos=14, io_err=0, num_read=5, buf='Hello'",
        "old_pos=5, io_err=0, num_read=5, buf='rld!?'",
        "old_pos=14, io_err=219",
    ]
