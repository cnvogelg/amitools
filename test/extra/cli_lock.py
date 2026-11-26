"""Run the original AmigaOS 3.2.3 ``Lock`` command (see test/cli/README.md).

``Lock <volume>`` reports whether the volume is locked; ``ON``/``OFF`` change
the state for the duration of the run.
"""

from cli_util import run_cli_rc, skip_if_cmd_missing, work_vargs

LOCK_SHA1 = "4194a3b434eded744a9a441c88379e7d284d0685"


def cli_lock_query_test(vrun, tmp_path):
    """``Lock <volume>`` reports the current state (unlocked by default)."""
    skip_if_cmd_missing(vrun, "Lock", LOCK_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Lock", "work:", vargs=work_vargs(tmp_path))
    assert stdout == ["work: unlocked"]
    assert stderr == []


def cli_lock_on_test(vrun, tmp_path):
    """``Lock <volume> ON`` locks the volume."""
    skip_if_cmd_missing(vrun, "Lock", LOCK_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Lock", "work:", "ON", vargs=work_vargs(tmp_path))
    assert stdout == ["work: locked"]
    assert stderr == []


def cli_lock_off_test(vrun, tmp_path):
    """``Lock <volume> OFF`` unlocks the volume."""
    skip_if_cmd_missing(vrun, "Lock", LOCK_SHA1)
    stdout, stderr = run_cli_rc(
        vrun, "Lock", "work:", "OFF", vargs=work_vargs(tmp_path)
    )
    assert stdout == ["work: unlocked"]
    assert stderr == []
