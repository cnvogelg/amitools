"""Run the original AmigaOS 3.2.3 ``Mount`` command (see test/cli/README.md).

``Mount`` mounts a device described in ``DEVS:MountList``.  The fixture does not
provide a ``DEVS:MountList``, so the command fails; the test asserts the
intended behaviour and is ``xfail``.
"""

import pytest

from cli_util import run_cli_rc, skip_if_cmd_missing, work_vargs

MOUNT_SHA1 = "2d0a52eea75b0014ec88303947ebebf658e50a2d"


@pytest.mark.xfail(
    reason="Mount needs a DEVS:MountList the CLI fixture does not provide",
    strict=True,
)
def cli_mount_test(vrun, tmp_path):
    """``Mount <device>`` mounts the device."""
    skip_if_cmd_missing(vrun, "Mount", MOUNT_SHA1)
    stdout, stderr = run_cli_rc(vrun, "Mount", "work:", vargs=work_vargs(tmp_path))
    assert stdout == []
    assert stderr == []
