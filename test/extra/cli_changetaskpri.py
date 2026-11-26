"""Run the original AmigaOS 3.2.3 ``ChangeTaskPri`` command (see test/cli/README.md).

``ChangeTaskPri <priority>`` changes the priority of the current task.
"""

from cli_util import run_cli_rc, skip_if_cmd_missing

CHANGETASKPRI_SHA1 = "cfde61b5d9a94d6b77238c8ea9498a8a2826239b"


def cli_changetaskpri_test(vrun):
    """``ChangeTaskPri 0`` sets the task priority."""
    skip_if_cmd_missing(vrun, "ChangeTaskPri", CHANGETASKPRI_SHA1)
    stdout, stderr = run_cli_rc(vrun, "ChangeTaskPri", "0")
    assert stdout == []
    assert stderr == []


def cli_changetaskpri_missing_test(vrun):
    """The required priority argument is enforced."""
    skip_if_cmd_missing(vrun, "ChangeTaskPri", CHANGETASKPRI_SHA1)
    stdout, stderr = run_cli_rc(vrun, "ChangeTaskPri", expect_rc=20, vargs=())
    assert stdout == ["ERROR_REQUIRED_ARG_MISSING"]
    assert stderr == []
