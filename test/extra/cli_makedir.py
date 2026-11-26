"""Run the original AmigaOS 3.2.3 ``MakeDir`` command (see test/cli/README.md)."""

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

MAKEDIR_SHA1 = "95ac383e94c1d20ea9a1df1cf0f2ded219d8d12d"


def cli_makedir_test(vrun, tmp_path):
    """``MakeDir <dir>`` creates a directory."""
    skip_if_cmd_missing(vrun, "MakeDir", MAKEDIR_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "MakeDir", "work:newdir", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []
    assert (tmp_path / "newdir").is_dir()


def cli_makedir_existing_test(vrun, tmp_path):
    """``MakeDir`` on an existing directory reports it."""
    skip_if_cmd_missing(vrun, "MakeDir", MAKEDIR_SHA1)
    make_work_tree(tmp_path)
    run_cli_rc(vrun, "MakeDir", "work:newdir", vargs=work_vargs(tmp_path))
    stdout, stderr = run_cli_rc(
        vrun, "MakeDir", "work:newdir", expect_rc=10, vargs=work_vargs(tmp_path)
    )
    assert stdout == ["work:newdir already exists"]
    assert stderr == []


def cli_makedir_multiple_test(vrun, tmp_path):
    """``MakeDir`` accepts several names (``DIR/A``)."""
    skip_if_cmd_missing(vrun, "MakeDir", MAKEDIR_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "MakeDir", "work:d1", "work:d2", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []
    assert (tmp_path / "d1").is_dir()
    assert (tmp_path / "d2").is_dir()


def cli_makedir_all_test(vrun, tmp_path):
    """``ALL`` creates the missing parent directories too."""
    skip_if_cmd_missing(vrun, "MakeDir", MAKEDIR_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "MakeDir", "work:a/b/c", "ALL", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []
    assert (tmp_path / "a" / "b" / "c").is_dir()


def cli_makedir_missing_parent_test(vrun, tmp_path):
    """Without ``ALL`` a missing parent is reported as not found."""
    skip_if_cmd_missing(vrun, "MakeDir", MAKEDIR_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "MakeDir", "work:a/b/c", expect_rc=10, vargs=work_vargs(tmp_path)
    )
    assert stdout == [
        "Can't create directory work:a/b/c",
        "ERROR_OBJECT_NOT_FOUND",
    ]
    assert stderr == []
