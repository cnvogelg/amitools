"""Run the original AmigaOS 3.2.3 ``DiskChange`` command (see test/cli/README.md).

``DiskChange <device>`` marks a device as changed.  A hostfs volume accepts it
without reporting anything.
"""

from cli_util import run_cli_rc, skip_if_cmd_missing, work_vargs

DISKCHANGE_SHA1 = "650836abbddba51990ccb58cf847473c3ff85c99"


def cli_diskchange_test(vrun, tmp_path):
    """``DiskChange work:`` marks the volume as changed."""
    skip_if_cmd_missing(vrun, "DiskChange", DISKCHANGE_SHA1)
    stdout, stderr = run_cli_rc(vrun, "DiskChange", "work:", vargs=work_vargs(tmp_path))
    assert stdout == []
    assert stderr == []
