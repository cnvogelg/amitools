"""Run the original AmigaOS 3.2.3 ``SetPatch`` command (see test/cli/README.md).

``SetPatch`` applies Kickstart patches.  Under ``vamos`` there is nothing to
patch, so it reports an empty patch list and succeeds.  ``QUIET`` suppresses the
message and ``CONTENTS`` only prints the header of the patch list.
"""

from cli_util import run_cli_rc, skip_if_cmd_missing

SETPATCH_SHA1 = "93dfc11808dcec0aaa0a8fc164c7cbb6f3cd7466"


def cli_setpatch_test(vrun):
    """``SetPatch`` reports the (empty) list of installed patches."""
    skip_if_cmd_missing(vrun, "SetPatch", SETPATCH_SHA1)
    stdout, stderr = run_cli_rc(vrun, "SetPatch")
    assert stdout[-2] == "SetPatch (V47.4) has been installed.  Patch list:"
    assert stdout[-1] == "\tNone."
    assert stderr == []


def cli_setpatch_quiet_test(vrun):
    """``SetPatch QUIET`` applies the patches without printing anything."""
    skip_if_cmd_missing(vrun, "SetPatch", SETPATCH_SHA1)
    stdout, stderr = run_cli_rc(vrun, "SetPatch", "QUIET")
    assert stdout == []
    assert stderr == []


def cli_setpatch_contents_test(vrun):
    """``SetPatch CONTENTS`` lists the patches it *would* apply."""
    skip_if_cmd_missing(vrun, "SetPatch", SETPATCH_SHA1)
    stdout, stderr = run_cli_rc(vrun, "SetPatch", "CONTENTS", expect_rc=20)
    assert stdout[0] == "SetPatch (V47.4) contains the following patches:"
    assert stderr == []
