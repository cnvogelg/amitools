import os
import pytest


def dos_examine_test(vamos, tmpdir):
    test_dir = tmpdir / "bla"
    os.mkdir(str(test_dir))
    # create some content
    fh = open(str(test_dir / "foo"), "w")
    fh.write("hello, world!\n")
    fh.close()
    os.mkdir(str(test_dir / "bar"))
    # show dir with Examine()/ExNext(), then again with ExAll()
    rc, stdout, stderr = vamos.run_prog("dos_examine", "root:" + str(test_dir)[1:])
    assert rc == 0
    assert stderr == []
    assert len(stdout) == 7
    assert stdout[0] == "Examine: bla"
    assert stdout[3] == "ExAll:"
    assert stdout[6] == "ok"
    # allow any order of foo or bar in both listings
    entries = {"   14 foo", "<DIR> bar"}
    assert set(stdout[1:3]) == entries
    assert set(stdout[4:6]) == entries
