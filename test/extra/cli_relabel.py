"""Run the original AmigaOS 3.2.3 ``Relabel`` command (see test/cli/README.md).

``Relabel <volume> <name>`` renames a volume.  On a hostfs volume the rename is
only kept for the duration of the run (the host directory is not renamed), so
only the exit code is asserted.
"""

from cli_util import run_cli_rc, skip_if_cmd_missing, work_vargs

RELABEL_SHA1 = "b1ddad5f18df7c6abb81e77d17ee6159cccf4bf6"


def cli_relabel_test(vrun, tmp_path):
    """``Relabel <volume> <name>`` succeeds."""
    skip_if_cmd_missing(vrun, "Relabel", RELABEL_SHA1)
    stdout, stderr = run_cli_rc(
        vrun, "Relabel", "work:", "newname", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []
