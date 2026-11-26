"""Run the original AmigaOS 3.2.3 ``Search`` command (see test/cli/README.md).

``Search <dir> <string>`` should print the lines of the files in ``dir`` that
contain ``string``.  Under vamos it prints its progress lines and then returns
5 without ever reporting a match, so the test is ``xfail``.
"""

import pytest

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

SEARCH_SHA1 = "72a6bbd06f4acca369ad01da2daadc5b940d744f"


@pytest.mark.xfail(
    reason="Search returns 5 without reporting the matching line", strict=True
)
def cli_search_test(vrun, tmp_path):
    """``Search work: hello`` finds ``hello`` in ``work:in.txt``."""
    skip_if_cmd_missing(vrun, "Search", SEARCH_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Search", "work:", "hello", vargs=work_vargs(tmp_path)
    )
    assert any("hello" in line for line in stdout)
    assert stderr == []
