"""Run the original AmigaOS 3.2.3 ``Dir`` command (see test/cli/README.md).

``Dir`` prints directories first, then the files in two columns.  The plain
forms work; ``ALL`` (recursive) is marked ``xfail`` because vamos's incomplete
``AnchorPath`` chain makes the command report a bogus circular directory.
"""

import pytest

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

DIR_SHA1 = "9c4044d3e06697fdd68cd1add615c6e3ce8ff8fd"

_DIRS = "     sub (dir)"
_FILES = "  a.txt       b.txt       del.txt     in.txt      nested.txt  ren.txt"


def cli_dir_plain_test(vrun, tmp_path):
    """``Dir <dir>`` lists the subdirectories, then the files."""
    skip_if_cmd_missing(vrun, "Dir", DIR_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(vrun, "Dir", "work:", vargs=work_vargs(tmp_path))
    assert stdout == [_DIRS, _FILES]
    assert stderr == []


def cli_dir_dirs_test(vrun, tmp_path):
    """``DIRS`` only lists subdirectories."""
    skip_if_cmd_missing(vrun, "Dir", DIR_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Dir", "work:", "DIRS", vargs=work_vargs(tmp_path)
    )
    assert stdout == [_DIRS]
    assert stderr == []


def cli_dir_files_test(vrun, tmp_path):
    """``FILES`` only lists the files."""
    skip_if_cmd_missing(vrun, "Dir", DIR_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Dir", "work:", "FILES", vargs=work_vargs(tmp_path)
    )
    assert stdout == [_FILES]
    assert stderr == []


def cli_dir_subdir_test(vrun, tmp_path):
    """``Dir <subdir>`` lists a subdirectory."""
    skip_if_cmd_missing(vrun, "Dir", DIR_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(vrun, "Dir", "work:sub", vargs=work_vargs(tmp_path))
    assert stdout == ["  deep.txt"]
    assert stderr == []


@pytest.mark.xfail(
    reason="vamos' AnchorPath chain triggers a bogus 'circular directory' error",
    strict=True,
)
def cli_dir_all_test(vrun, tmp_path):
    """``ALL`` recurses into subdirectories."""
    skip_if_cmd_missing(vrun, "Dir", DIR_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(vrun, "Dir", "work:", "ALL", vargs=work_vargs(tmp_path))
    # the subdirectory and its contents must be listed
    assert "deep.txt" in "\n".join(stdout)
    assert stderr == []
