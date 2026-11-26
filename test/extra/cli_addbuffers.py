"""Run the original AmigaOS 3.2.3 ``AddBuffers`` command (see test/cli/README.md).

``AddBuffers <device>`` queries or sets the number of file system buffers.  A
hostfs volume accepts both without reporting anything.
"""

from cli_util import run_cli_rc, skip_if_cmd_missing, work_vargs

ADDBUFFERS_SHA1 = "b8bae93dc109c0bc18f87b372361cf44eb8046c2"


def cli_addbuffers_query_test(vrun, tmp_path):
    """``AddBuffers <device>`` queries the buffer count."""
    skip_if_cmd_missing(vrun, "AddBuffers", ADDBUFFERS_SHA1)
    stdout, stderr = run_cli_rc(vrun, "AddBuffers", "work:", vargs=work_vargs(tmp_path))
    assert stdout == []
    assert stderr == []


def cli_addbuffers_set_test(vrun, tmp_path):
    """``AddBuffers <device> <n>`` sets the buffer count."""
    skip_if_cmd_missing(vrun, "AddBuffers", ADDBUFFERS_SHA1)
    stdout, stderr = run_cli_rc(
        vrun, "AddBuffers", "work:", "10", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []
