"""Run the original AmigaOS 3.2.3 ``Info`` command (see test/cli/README.md).

``Info`` prints the mounted disks and the available volumes.  The exact set of
volumes depends on the ``vamos`` configuration, so only the requested volume is
asserted.
"""

from cli_util import run_cli_rc, skip_if_cmd_missing, work_vargs

INFO_SHA1 = "2c9c98a4b7a576eb50c4b2b8f32ea6eeaa9fcabb"


def cli_info_volume_test(vrun, tmp_path):
    """``Info <volume>`` lists that volume as mounted."""
    skip_if_cmd_missing(vrun, "Info", INFO_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Info", "work:", vargs=work_vargs(tmp_path))
    assert "Mounted disks:" in stdout
    assert "Volumes available:" in stdout
    assert "work [Mounted]" in stdout
    assert any(line.startswith("work") for line in stdout)
    assert stderr == []
