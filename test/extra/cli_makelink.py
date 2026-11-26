"""Run the original AmigaOS 3.2.3 ``MakeLink`` command (see test/cli/README.md).

``MakeLink <from> <to>`` creates a hard link and ``MakeLink <from> <to> SOFT``
a soft link.  Neither works under vamos (``ERROR_OBJECT_NOT_FOUND`` for the
hard link, ``ERROR_OBJECT_EXISTS`` for the soft one); both tests assert the
intended behaviour and are ``xfail``.
"""

import os

import pytest

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

MAKELINK_SHA1 = "f1d8d6e57c3942cc61a6603038084abc1d3652e1"


@pytest.mark.xfail(reason="MakeLink cannot create a hard link", strict=True)
def cli_makelink_hard_test(vrun, tmp_path):
    """``MakeLink <from> <to>`` creates a hard link to the source."""
    skip_if_cmd_missing(vrun, "MakeLink", MAKELINK_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "MakeLink", "work:in.txt", "work:link", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []
    assert (tmp_path / "link").read_text() == "hello\nworld\n"


@pytest.mark.xfail(reason="MakeLink cannot create a soft link", strict=True)
def cli_makelink_soft_test(vrun, tmp_path):
    """``MakeLink <from> <to> SOFT`` creates a soft link to the source."""
    skip_if_cmd_missing(vrun, "MakeLink", MAKELINK_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun,
        "MakeLink",
        "work:in.txt",
        "work:soft",
        "SOFT",
        vargs=work_vargs(tmp_path),
    )
    assert stdout == []
    assert stderr == []
    assert os.path.islink(str(tmp_path / "soft"))
