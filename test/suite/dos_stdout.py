import pytest


def dos_stdout_test(vamos):
    rc, stdout, stderr = vamos.run_prog("dos_stdout")
    assert rc == 0
    assert stderr == []
    assert stdout == ["Hello, world!?", "Hello, world!?"]
