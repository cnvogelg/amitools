"""Run the original AmigaOS 3.2.3 ``Group`` command (see test/cli/README.md).

``Group <file> <gid>`` sets a file's group.  A hostfs volume cannot store an
AmigaDOS group, so the command fails with ``ERROR_NOT_IMPLEMENTED``; the test
asserts the intended behaviour and is ``xfail``.
"""

import pytest

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

GROUP_SHA1 = "6451090722636d3d9e69a975b8c8d1455cc7b0b0"


@pytest.mark.xfail(reason="hostfs cannot store an AmigaDOS file group", strict=True)
def cli_group_test(vrun, tmp_path):
    """``Group work:in.txt 0`` sets the file group."""
    skip_if_cmd_missing(vrun, "Group", GROUP_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Group", "work:in.txt", "0", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []
