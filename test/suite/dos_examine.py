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
    # show dir
    rc, stdout, stderr = vamos.run_prog("dos_examine", "root:" + str(test_dir)[1:])
    assert rc == 0
    assert stderr == []
    assert stdout == [
        'Examine: bla',
        '   14 foo',
        '<DIR> bar',
        'ok'
    ]
