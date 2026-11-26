"""Run the original AmigaOS 3.2.3 ``Assign`` command (see test/cli/README.md).

``Assign`` lists or creates logical assignments.  Every ``run_cli`` is a fresh
in-process ``vamos`` run, so an assignment made in one test does not leak into
another.
"""

from cli_util import run_cli_rc, skip_if_cmd_missing, work_vargs

ASSIGN_SHA1 = "7160378f7ab1a8d01dd023dc20318a0b1d11ae71"


def cli_assign_list_test(vrun, tmp_path):
    """``Assign LIST`` prints the volumes and assignments."""
    skip_if_cmd_missing(vrun, "Assign", ASSIGN_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Assign", "LIST", vargs=work_vargs(tmp_path))
    assert "Volumes:" in stdout
    assert "work [Mounted]" in stdout
    assert "Directories:" in stdout
    assert "Devices:" in stdout
    assert stderr == []


def cli_assign_add_test(vrun, tmp_path):
    """``Assign FOO: work:`` creates an assignment."""
    skip_if_cmd_missing(vrun, "Assign", ASSIGN_SHA1)
    stdout, stderr = run_cli_rc(
        vrun, "Assign", "FOO:", "work:", vargs=work_vargs(tmp_path)
    )
    assert stdout == []
    assert stderr == []


def cli_assign_exists_test(vrun, tmp_path):
    """``Assign FOO: EXISTS`` reports that a fresh assignment does not exist."""
    skip_if_cmd_missing(vrun, "Assign", ASSIGN_SHA1)
    stdout, stderr = run_cli_rc(
        vrun, "Assign", "FOO:", "EXISTS", expect_rc=5, vargs=work_vargs(tmp_path)
    )
    assert stdout == ["FOO: not assigned"]
    assert stderr == []
