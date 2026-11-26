"""Run the original AmigaOS 3.2.3 ``Protect`` command (see test/cli/README.md).

Setting the flags is mapped onto the host file mode.  Displaying the flags
(``Protect <file>`` without flags) is broken: it prints nothing and clears the
host protection, so that test is ``xfail``.
"""

import os

import pytest

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

PROTECT_SHA1 = "9b26a63513e5b8c9ec1c2408e8d079c9b7b1040f"


def _mode(path):
    return os.stat(str(path)).st_mode & 0o777


def cli_protect_set_test(vrun, tmp_path):
    """``Protect <file> +rwed`` sets all protection bits."""
    skip_if_cmd_missing(vrun, "Protect", PROTECT_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Protect", "work:in.txt", "+rwed", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []
    assert _mode(tmp_path / "in.txt") == 0o744


def cli_protect_clear_test(vrun, tmp_path):
    """``Protect <file> -w`` clears the write bit."""
    skip_if_cmd_missing(vrun, "Protect", PROTECT_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Protect", "work:in.txt", "-w", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []
    assert _mode(tmp_path / "in.txt") == 0o444


def cli_protect_missing_test(vrun, tmp_path):
    """A missing file is reported."""
    skip_if_cmd_missing(vrun, "Protect", PROTECT_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun,
        "Protect",
        "work:missing.txt",
        "+rwed",
        expect_rc=20,
        vargs=work_vargs(tmp_path),
    )
    assert stdout == ["PROTECT: ERROR_OBJECT_NOT_FOUND"]
    assert stderr == []


@pytest.mark.xfail(
    reason="Protect display prints nothing and clears the host protection",
    strict=True,
)
def cli_protect_display_test(vrun, tmp_path):
    """``Protect <file>`` displays the current protection flags."""
    skip_if_cmd_missing(vrun, "Protect", PROTECT_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Protect", "work:in.txt", vargs=work_vargs(tmp_path)
    )
    assert stdout == ["----rw-d"]
    assert stderr == []
    # displaying must not change the protection
    assert _mode(tmp_path / "in.txt") == 0o644
