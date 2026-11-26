"""Run the original AmigaOS 3.2.3 ``Owner`` command (see test/cli/README.md).

``Owner <file> <uid>`` sets a file's owner.  A hostfs volume cannot store an
AmigaDOS owner, so the command fails with ``ERROR_NOT_IMPLEMENTED``; the test
asserts the intended behaviour and is ``xfail``.
"""

import pytest

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

OWNER_SHA1 = "54bafce8ee40e8bafa6dd3f11215cd1063745ecf"


@pytest.mark.xfail(reason="hostfs cannot store an AmigaDOS file owner", strict=True)
def cli_owner_test(vrun, tmp_path):
    """``Owner work:in.txt 0`` sets the file owner."""
    skip_if_cmd_missing(vrun, "Owner", OWNER_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Owner", "work:in.txt", "0", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []
