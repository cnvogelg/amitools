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


@pytest.mark.parametrize("input_delay", [0, 0.25], ids=["immediate", "delayed"])
def dos_waitforchar_char_test(vamos, tmpdir, input_delay):
    # A native callback enters raw mode, consumes a marker, then checks
    # the next queued byte. Delaying the host past the 100 ms timeout
    # must not turn an input-readiness test into a scheduling race.
    rc, stdout, stderr = vamos.run_prog(
        "test_execpy",
        "-c",
        "helper/waitforchar.py",
        "wait_for_input",
        stdin="hh",
        use_pty=True,
        stdin_delay=input_delay,
    )
    assert rc == 0
    assert stdout == ["timeout=100000", "result=-1"]
