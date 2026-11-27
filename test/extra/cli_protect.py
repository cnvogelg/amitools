"""Run the original AmigaOS 3.2.3 ``Protect`` command (see test/cli/README.md).

Setting the flags is mapped onto the host file mode.  ``Protect`` has no
display mode: ``Protect <file>`` without flags clears the owner protection bits
(use ``List`` to show them).  A wildcard pattern reports each entry because
``MatchFirst`` sets ``APF_ITSWILD``.
"""

import os

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


def cli_protect_no_flags_test(vrun, tmp_path):
    """``Protect <file>`` without flags clears the owner protection bits.

    ``Protect`` is not a display command (the 3.2.3 binary has no such path);
    an empty flags field clears every owner bit.  Use ``List`` to show the
    protection bits.
    """
    skip_if_cmd_missing(vrun, "Protect", PROTECT_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Protect", "work:in.txt", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []
    # owner r/w/e cleared, group/other read bits kept from the host mode
    assert _mode(tmp_path / "in.txt") == 0o044


def cli_protect_wildcard_test(vrun, tmp_path):
    """A wildcard pattern reports every entry it touches (APF_ITSWILD)."""
    skip_if_cmd_missing(vrun, "Protect", PROTECT_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(vrun, "Protect", "work:#?", vargs=work_vargs(tmp_path))
    assert stderr == []
    # the listing order is host dependent, so compare as a set
    assert sorted(stdout) == sorted(
        [
            "   a.txt...Done",
            "   b.txt...Done",
            "   del.txt...Done",
            "   in.txt...Done",
            "   nested.txt...Done",
            "   ren.txt...Done",
            "sub (dir)...Done",
        ]
    )
