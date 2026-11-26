"""Run the original AmigaOS 3.2.3 ``Install`` command (see test/cli/README.md).

``Install DRIVE`` creates a bootable disk from the install script on the given
volume.  A plain file or a hostfs volume is not an installable disk, so the
command reports the wrong object type and fails.
"""

from cli_util import make_work_tree, run_cli_rc, skip_if_cmd_missing, work_vargs

INSTALL_SHA1 = "5af5975ef92ec650bf6648cce9697a9a51d5fe42"


def cli_install_file_test(vrun, tmp_path):
    """``Install <file>`` rejects a plain file as the install drive."""
    skip_if_cmd_missing(vrun, "Install", INSTALL_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Install", "work:in.txt", expect_rc=20, vargs=work_vargs(tmp_path)
    )
    assert stdout == ["ERROR_OBJECT_WRONG_TYPE", "Install failed"]
    assert stderr == []


def cli_install_volume_test(vrun, tmp_path):
    """``Install <volume>`` rejects a volume without an install script."""
    skip_if_cmd_missing(vrun, "Install", INSTALL_SHA1)
    make_work_tree(tmp_path)
    stdout, stderr = run_cli_rc(
        vrun, "Install", "work:", expect_rc=20, vargs=work_vargs(tmp_path)
    )
    assert stdout == ["ERROR_OBJECT_WRONG_TYPE", "Install failed"]
    assert stderr == []
